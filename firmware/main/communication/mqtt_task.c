#include "mqtt_task.h"
#include "env_mqtt_client.h"
#include "json_serializer.h"
#include "sensor_types.h"
#include "time_sync.h"
#include "wifi_manager.h"

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

static const char *TAG = "MQTT_TASK";

// Skickar med exponentiell backoff. Returnerar true om brokern bekräftade (PUBACK).
static bool publish_with_retry(const char *topic, const char *payload) {
    for (int attempt = 1; attempt <= CONFIG_BEACH_MAX_RETRIES; attempt++) {
        esp_err_t err = mqtt_client_module_publish_confirmed(topic, payload, 5000);
        if (err == ESP_OK) return true;

        ESP_LOGW(TAG, "Försök %d/%d misslyckades: %s", attempt, CONFIG_BEACH_MAX_RETRIES, esp_err_to_name(err));
        if (attempt < CONFIG_BEACH_MAX_RETRIES) {
            vTaskDelay(pdMS_TO_TICKS(CONFIG_BEACH_RETRY_BASE_DELAY_MS << (attempt - 1)));
        }
    }
    return false;
}

void mqtt_task(void *pvParameters) {
    ESP_LOGI(TAG, "MQTT Task startad på FreeRTOS Core %d", xPortGetCoreID());

    // ============================================================
    // 1. Wi-Fi (wifi_manager fortsätter försöka i bakgrunden)
    // ============================================================
    esp_err_t wifi_err = wifi_manager_init();
    if (wifi_err != ESP_OK && wifi_err != ESP_FAIL && wifi_err != ESP_ERR_TIMEOUT) {
        ESP_LOGE(TAG, "Wi-Fi kunde inte initieras: %s", esp_err_to_name(wifi_err));
        vTaskDelete(NULL);
        return;
    }
    while (!wifi_manager_is_connected()) {
        ESP_LOGI(TAG, "Väntar på Wi-Fi...");
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    ESP_LOGI(TAG, "Wi-Fi är anslutet. Synkar tid och startar MQTT...");

    // ============================================================
    // 2. Tid (SNTP) - sensor_task köar inga mätvärden före detta
    // ============================================================
    time_sync_start();
    while (!time_sync_wait(10000)) {
        ESP_LOGW(TAG, "Väntar på SNTP...");
    }

    // ============================================================
    // 3. MQTT
    // ============================================================
    esp_err_t mqtt_err = mqtt_client_module_start();
    if (mqtt_err != ESP_OK) {
        ESP_LOGE(TAG, "MQTT kunde inte startas: %s", esp_err_to_name(mqtt_err));
        vTaskDelete(NULL);
        return;
    }
    while (!mqtt_client_module_is_connected()) {
        ESP_LOGI(TAG, "Väntar på MQTT broker...");
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    ESP_LOGI(TAG, "MQTT anslutet!");

    mqtt_client_module_publish(MQTT_TOPIC_STATUS, "{\"device\":\"" CONFIG_BEACH_SENSOR_BASE_ID "\",\"status\":\"online\"}");

    // ============================================================
    // 4. Huvudloop: SensorTask -> Queue -> JSON -> MQTT
    // ============================================================
    sensor_telemetry_t received_data;
    char payload_buffer[320];
    char topic_buffer[96];

    while (1) {
        if (!mqtt_client_module_is_connected()) {
            ESP_LOGW(TAG, "MQTT inte anslutet - väntar på reconnect...");
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }
        if (s_sensor_queue == NULL) {
            ESP_LOGE(TAG, "s_sensor_queue är NULL!");
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }
        if (xQueueReceive(s_sensor_queue, &received_data, pdMS_TO_TICKS(1000)) != pdPASS) continue;

        for (int m = 0; m < METRIC_COUNT; m++) {
            metric_t metric = (metric_t)m;
            if (!telemetry_metric_valid(&received_data, metric)) {
                ESP_LOGW(TAG, "%s saknar giltigt värde - hoppar över", metric_name(metric));
                continue;
            }
            if (!serialize_reading_json(&received_data, metric, payload_buffer, sizeof(payload_buffer)) ||
                !build_reading_topic(metric, topic_buffer, sizeof(topic_buffer))) {
                ESP_LOGE(TAG, "Kunde inte skapa telemetry JSON");
                continue;
            }
            if (publish_with_retry(topic_buffer, payload_buffer)) {
                ESP_LOGI(TAG, "Telemetry publicerad: %s", payload_buffer);
            } else {
                ESP_LOGE(TAG, "Gav upp - datapunkt förlorad: %s", payload_buffer);
            }
        }
    }
}
