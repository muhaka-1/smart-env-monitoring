#include "ds18b20_driver.h"
#include "esp_log.h"
#include "esp_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "sdkconfig.h"

#if !CONFIG_BEACH_SENSOR_SIMULATED
#include "driver/gpio.h"
#include "esp_rom_sys.h"
#define OW_PIN ((gpio_num_t)CONFIG_BEACH_TEMP_GPIO)
static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;
#endif

static const char *TAG = "DS18B20_DRIVER";
static SemaphoreHandle_t s_lock = NULL;   // sensor_task och självtester delar bussen

#if CONFIG_BEACH_SENSOR_SIMULATED

esp_err_t ds18b20_init_pins(void) {
    if (!s_lock) s_lock = xSemaphoreCreateMutex();
    ESP_LOGI(TAG, "Simulerad DS18B20");
    return ESP_OK;
}

esp_err_t ds18b20_read_water_temp(float *temp_water_c, quality_t *quality) {
    static const float curve[] = {19.2f, 19.5f, 20.1f, 21.0f, 22.4f, 23.8f, 25.5f, 26.1f, 24.0f, 22.0f, 20.5f, 19.8f};
    static unsigned idx;
    *temp_water_c = curve[idx++ % (sizeof(curve) / sizeof(curve[0]))] + (esp_random() % 100) / 100.0f;
    *quality = QUALITY_GOOD;
    return ESP_OK;
}

#else

/* ---- 1-Wire: Reset, Skip ROM (0xCC), Convert T (0x44), Read Scratchpad (0xBE) ---- */

static bool ow_reset(void) {
    gpio_set_level(OW_PIN, 0);
    esp_rom_delay_us(480);
    gpio_set_level(OW_PIN, 1);
    esp_rom_delay_us(70);
    bool present = gpio_get_level(OW_PIN) == 0;
    esp_rom_delay_us(410);
    return present;
}

static void ow_write_bit(int b) {
    portENTER_CRITICAL(&s_mux);
    gpio_set_level(OW_PIN, 0);
    esp_rom_delay_us(b ? 6 : 60);
    gpio_set_level(OW_PIN, 1);
    esp_rom_delay_us(b ? 64 : 10);
    portEXIT_CRITICAL(&s_mux);
}

static int ow_read_bit(void) {
    portENTER_CRITICAL(&s_mux);
    gpio_set_level(OW_PIN, 0);
    esp_rom_delay_us(6);
    gpio_set_level(OW_PIN, 1);
    esp_rom_delay_us(9);
    int b = gpio_get_level(OW_PIN);
    esp_rom_delay_us(55);
    portEXIT_CRITICAL(&s_mux);
    return b;
}

static void ow_write(uint8_t byte) { for (int i = 0; i < 8; i++) ow_write_bit((byte >> i) & 1); }

static uint8_t ow_read(void) {
    uint8_t v = 0;
    for (int i = 0; i < 8; i++) v |= ow_read_bit() << i;
    return v;
}

static uint8_t crc8(const uint8_t *d, int n) {
    uint8_t crc = 0;
    while (n--) {
        uint8_t in = *d++;
        for (int i = 0; i < 8; i++) {
            uint8_t mix = (crc ^ in) & 1;
            crc >>= 1;
            if (mix) crc ^= 0x8C;
            in >>= 1;
        }
    }
    return crc;
}

esp_err_t ds18b20_init_pins(void) {
    if (!s_lock) s_lock = xSemaphoreCreateMutex();
    esp_err_t err = gpio_reset_pin(OW_PIN);
    if (err == ESP_OK) err = gpio_set_direction(OW_PIN, GPIO_MODE_INPUT_OUTPUT_OD);  // open-drain + extern 4,7k
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Kunde inte konfigurera 1-Wire GPIO: %s", esp_err_to_name(err));
        return err;
    }
    gpio_set_level(OW_PIN, 1);
    ESP_LOGI(TAG, "1-Wire GPIO initierad: Vatten=GPIO%d", CONFIG_BEACH_TEMP_GPIO);
    return ESP_OK;
}

esp_err_t ds18b20_read_water_temp(float *temp_water_c, quality_t *quality) {
    xSemaphoreTake(s_lock, portMAX_DELAY);
    esp_err_t err = ESP_OK;
    uint8_t sp[9];

    if (!ow_reset()) {
        err = ESP_ERR_NOT_FOUND;                        // ingen sensor / saknad pull-up
    } else {
        ow_write(0xCC); ow_write(0x44);                 // starta konvertering
        vTaskDelay(pdMS_TO_TICKS(800));                 // 12-bit tar max 750 ms
        if (!ow_reset()) {
            err = ESP_ERR_NOT_FOUND;
        } else {
            ow_write(0xCC); ow_write(0xBE);             // läs scratchpad
            for (int i = 0; i < 9; i++) sp[i] = ow_read();
            if (crc8(sp, 8) != sp[8]) err = ESP_ERR_INVALID_CRC;
        }
    }
    xSemaphoreGive(s_lock);
    if (err != ESP_OK) return err;

    *temp_water_c = (int16_t)((sp[1] << 8) | sp[0]) / 16.0f;
    *quality = (*temp_water_c == 85.0f) ? QUALITY_SUSPECT : QUALITY_GOOD;  // 85 °C = värde efter strömpåslag
    return ESP_OK;
}

#endif
