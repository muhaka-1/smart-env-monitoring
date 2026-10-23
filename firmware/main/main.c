/*
 * Beach sensor firmware (ESP-IDF)
 *
 *  Core 1: sensor_task - mäter med jämna intervall -> FreeRTOS-kö
 *  Core 0: comm_task   - kö -> JSON -> MQTT (QoS 1) med retry/backoff
 *
 * Wi-Fi/LwIP körs som standard på core 0, därför ligger kommunikationen där.
 * På enkärniga chip (t.ex. ESP32-C3) hamnar båda tasks på core 0.
 */
#include <stdio.h>
#include <time.h>
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "mqtt_publisher.h"
#include "nvs_flash.h"
#include "sdkconfig.h"
#include "sensor.h"
#include "time_sync.h"
#include "wifi_manager.h"

#define COMM_CORE   0
#if CONFIG_FREERTOS_UNICORE
#define SENSOR_CORE 0
#else
#define SENSOR_CORE 1
#endif

static const char *TAG = "main";
static QueueHandle_t s_queue;

static void sensor_task(void *arg)
{
    TickType_t last = xTaskGetTickCount();
    for (;;) {
        sample_t s;
        if (sensor_read(&s) == ESP_OK) {
            if (xQueueSend(s_queue, &s, 0) != pdTRUE) {
                ESP_LOGW(TAG, "Kön full - mätvärde kasserat");  // sensorn blockeras aldrig
            }
        } else {
            ESP_LOGE(TAG, "Sensorläsning misslyckades");
        }
        vTaskDelayUntil(&last, pdMS_TO_TICKS(CONFIG_BEACH_SAMPLE_INTERVAL_MS));  // jämnt intervall
    }
}

static void format_json(const sample_t *s, char *buf, size_t len)
{
    struct tm tm;
    char ts[24];
    gmtime_r(&s->sec, &tm);
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%S", &tm);
    snprintf(buf, len,
             "{\"sensor_id\":\"%s\",\"timestamp\":\"%s.%03dZ\",\"value\":%.2f,\"unit\":\"NTU\",\"quality\":\"%s\"}",
             CONFIG_BEACH_SENSOR_ID, ts, s->ms, s->value, quality_str(s->quality));
}

static bool send_with_retry(const char *topic, const char *json)
{
    for (int attempt = 1; attempt <= CONFIG_BEACH_MAX_RETRIES; attempt++) {
        esp_err_t err = mqtt_publisher_send(topic, json, 5000);
        if (err == ESP_OK) return true;
        ESP_LOGW(TAG, "Försök %d/%d misslyckades: %s", attempt, CONFIG_BEACH_MAX_RETRIES, esp_err_to_name(err));
        if (attempt < CONFIG_BEACH_MAX_RETRIES) {
            vTaskDelay(pdMS_TO_TICKS(CONFIG_BEACH_RETRY_BASE_DELAY_MS << (attempt - 1)));  // exponentiell backoff
        }
    }
    return false;
}

static void comm_task(void *arg)
{
    char topic[96], json[256];
    snprintf(topic, sizeof(topic), "beach/%s/readings", CONFIG_BEACH_SENSOR_ID);
    sample_t s;
    for (;;) {
        if (xQueueReceive(s_queue, &s, portMAX_DELAY) != pdTRUE) continue;
        format_json(&s, json, sizeof(json));
        if (send_with_retry(topic, json)) {
            ESP_LOGI(TAG, "Skickade: %s", json);
        } else {
            ESP_LOGE(TAG, "Gav upp - datapunkt förlorad: %s", json);
        }
    }
}

void app_main(void)
{
    esp_err_t r = nvs_flash_init();
    if (r == ESP_ERR_NVS_NO_FREE_PAGES || r == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        r = nvs_flash_init();
    }
    ESP_ERROR_CHECK(r);

    wifi_start();
    wifi_wait_connected(portMAX_DELAY);
    time_sync_start();
    if (!time_sync_wait(30000)) {
        ESP_LOGE(TAG, "SNTP misslyckades - startar om");
        esp_restart();
    }
    mqtt_publisher_start();

    s_queue = xQueueCreate(CONFIG_BEACH_QUEUE_LENGTH, sizeof(sample_t));
    ESP_ERROR_CHECK(sensor_init());

    xTaskCreatePinnedToCore(comm_task, "comm", 8192, NULL, 5, NULL, COMM_CORE);
    xTaskCreatePinnedToCore(sensor_task, "sensor", 4096, NULL, 5, NULL, SENSOR_CORE);
    ESP_LOGI(TAG, "Igång: sensor på core %d, kommunikation på core %d", SENSOR_CORE, COMM_CORE);
}
