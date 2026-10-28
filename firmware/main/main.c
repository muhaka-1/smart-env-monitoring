/**
 * ============================================================================
 * PROJEKT: Smart Environmental Monitoring Platform - ESP32-firmware
 * SPRÅK: Ren C (ESP-IDF v5.x / FreeRTOS, modulär arkitektur)
 *
 * MODULER (hela systemet):
 * 1. ESP32-sensor:       sensors/        (sensor_task, turbiditet, DS18B20, larmgränser)   - Muhammad
 * 2. Datakommunikation:  communication/  (mqtt_task, Wi-Fi, SNTP, MQTT, JSON)              - Muhammad
 * 3. Backend / API:      ../backend      (Django: validering, avvikelsedetektering, REST)  - Muhammad
 * 4. Databas:            ../backend/monitoring/models.py (SQLite, index, dubblettskydd)     - Pat
 * 5. Frontend:           ../backend/monitoring/templates, static (dashboard)                - Pat
 * Test & Verifiering:    testing/        (self-tests TC-01.., mocks)
 * ============================================================================
 */

#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_system.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

// Modulheaders
#include "sensor_types.h"
#include "sensors/sensor_task.h"
#include "communication/mqtt_task.h"
#include "testing/test_runner.h"

static const char *TAG = "MAIN_SYSTEM";

// Global FreeRTOS-kö för att transportera telemetridata mellan Core 1 och Core 0
QueueHandle_t s_sensor_queue = NULL;

#if CONFIG_FREERTOS_UNICORE
#define SENSOR_CORE 0
#else
#define SENSOR_CORE 1
#endif

void app_main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    esp_rom_printf("\r\n\r\n==================================================\r\n");
    esp_rom_printf("   SMART ENVIRONMENTAL MONITORING - ESP32 v1.0    \r\n");
    esp_rom_printf("==================================================\r\n\r\n");

    ESP_LOGI(TAG, "Initierar system och NVS Flash...");

    // 1. NVS (Non-Volatile Storage) - krävs av Wi-Fi-drivern
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        ret = nvs_flash_init();
    }
    ESP_LOGI(TAG, "NVS status: %s", esp_err_to_name(ret));

    // 2. Delad FreeRTOS-kö för sensortelemetri
    s_sensor_queue = xQueueCreate(CONFIG_BEACH_QUEUE_LENGTH, sizeof(sensor_telemetry_t));
    if (s_sensor_queue == NULL) {
        ESP_LOGE(TAG, "Kritiskt fel: Kunde inte skapa FreeRTOS sensor queue!");
        return;
    }
    ESP_LOGI(TAG, "FreeRTOS sensor queue skapad (Kapacitet: %d paket)", CONFIG_BEACH_QUEUE_LENGTH);

    // 3. Sensorhårdvara: ADC (turbiditet) och 1-Wire (DS18B20)
    init_sensor_hardware();

    // 4. SensorTask på Core 1 (Modul 1: ESP32-sensor)
    xTaskCreatePinnedToCore(sensor_task, "sensor_task", 4096, NULL, 2, NULL, SENSOR_CORE);
    ESP_LOGI(TAG, "[Core %d] SensorTask startad (Modul 1)", SENSOR_CORE);

    // 5. MQTT Task på Core 0 (Modul 2: Datakommunikation) - startar Wi-Fi, SNTP och MQTT
    xTaskCreatePinnedToCore(mqtt_task, "mqtt_task", 6144, NULL, 1, NULL, 0);
    ESP_LOGI(TAG, "[Core 0] MQTT Task startad (Modul 2)");

#if CONFIG_BEACH_RUN_SELFTEST
    // 6. Självtester (väntar på nätverket, kör sedan TC-01..)
    xTaskCreatePinnedToCore(self_test_task, "self_test", 8192, NULL, 1, NULL, 0);
    ESP_LOGI(TAG, "[Core 0] Självtester schemalagda");
#endif

    ESP_LOGI(TAG, "Systemet körs med modul 1 och 2 aktiva!");
}
