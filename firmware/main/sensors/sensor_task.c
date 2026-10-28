#include "sensor_task.h"
#include <string.h>
#include <sys/time.h>
#include "alarm_limits.h"
#include "ds18b20_driver.h"
#include "time_sync.h"
#include "turbidity_driver.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "SENSOR_TASK";

esp_err_t init_sensor_hardware(void) {
    // 1. Status-LED
    gpio_reset_pin((gpio_num_t)STATUS_LED_GPIO);
    gpio_set_direction((gpio_num_t)STATUS_LED_GPIO, GPIO_MODE_OUTPUT);
    gpio_set_level((gpio_num_t)STATUS_LED_GPIO, 1);

    // 2. Turbiditet (ADC1)
    esp_err_t adc_err = turbidity_init();
    if (adc_err != ESP_OK) {
        ESP_LOGW(TAG, "Varning: ADC kunde inte initieras (%s)", esp_err_to_name(adc_err));
    }

    // 3. 1-Wire för DS18B20
    esp_err_t ds_err = ds18b20_init_pins();
    if (ds_err != ESP_OK) {
        ESP_LOGW(TAG, "Varning: 1-Wire GPIO kunde inte initieras (%s)", esp_err_to_name(ds_err));
    }

    ESP_LOGI(TAG, "Sensorhårdvara initierad!");
    return ESP_OK;
}

void sensor_read_all(sensor_telemetry_t *data) {
    memset(data, 0, sizeof(*data));

    // Tidsstämpel vid mätning (UTC, korrekt efter SNTP)
    struct timeval tv;
    gettimeofday(&tv, NULL);
    data->timestamp_sec = tv.tv_sec;
    data->timestamp_ms = (int)(tv.tv_usec / 1000);

    // 1. Grumlighet (ADC)
    esp_err_t err_turb = turbidity_read_ntu(&data->turbidity_ntu, &data->turbidity_quality);
    data->turbidity_valid = (err_turb == ESP_OK);
    if (!data->turbidity_valid) ESP_LOGW(TAG, "Turbiditet: %s", esp_err_to_name(err_turb));

    // 2. Vattentemperatur (DS18B20)
    esp_err_t err_water = ds18b20_read_water_temp(&data->temp_water_c, &data->temp_water_quality);
    data->ds18b20_water_valid = (err_water == ESP_OK);
    if (!data->ds18b20_water_valid) ESP_LOGW(TAG, "DS18B20: %s", esp_err_to_name(err_water));

    // 3. Drifttid och larmgränser
    data->uptime_seconds = (uint32_t)(esp_timer_get_time() / 1000000ULL);
    evaluate_alarm_limits(data);
}

void sensor_task(void *pvParameters) {
    ESP_LOGI(TAG, "SensorTask startad på FreeRTOS Core %d (Prioritet: 2)", xPortGetCoreID());
    sensor_telemetry_t data;
    TickType_t last_wake = xTaskGetTickCount();

    while (1) {
        sensor_read_all(&data);

        // Diagnostik direkt till serieporten
        ESP_LOGI(TAG, "[Mätning] Grumlighet: %.1f NTU | Vatten: %.1f°C | Larm: %s",
                 data.turbidity_ntu, data.temp_water_c, data.alarm_code);

        // Skicka telemetripaket till FreeRTOS-kön (för mqtt_task) - först när klockan är synkad
        if (!time_sync_is_synced()) {
            ESP_LOGW(TAG, "Tid ej synkad (SNTP) - mätvärde köas inte");
        } else if (s_sensor_queue != NULL) {
            if (xQueueSend(s_sensor_queue, &data, 0) != pdPASS) {
                ESP_LOGW(TAG, "SensorQueue full, hoppar över telemetripaket.");
            }
        }

        // Heartbeat LED-puls
        gpio_set_level((gpio_num_t)STATUS_LED_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level((gpio_num_t)STATUS_LED_GPIO, 0);

        // Jämnt mätintervall (tar hänsyn till tiden mätningen tog)
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(SENSOR_SAMPLE_RATE_MS));
    }
}
