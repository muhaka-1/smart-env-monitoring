#include "env_mqtt_client.h"
#include <stdio.h>
#include <string.h>
#include "cJSON.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include <mqtt_client.h>   // ESP-IDF:s MQTT-komponent

#define MQTT_ACKED_BIT BIT0

static const char *TAG = "MQTT_CLIENT";

static esp_mqtt_client_handle_t s_mqtt_client = NULL;
static volatile bool s_mqtt_connected = false;
static EventGroupHandle_t s_ack_events = NULL;
static volatile int s_acked_msg_id = -1;

static void handle_command(const char *payload) {
    cJSON *root = cJSON_Parse(payload);
    if (root == NULL) {
        ESP_LOGW(TAG, "Ogiltig JSON command");
        return;
    }
    cJSON *command = cJSON_GetObjectItem(root, "command");
    if (cJSON_IsString(command) && strcmp(command->valuestring, "status") == 0) {
        const char *status_payload = "{\"device\":\"" CONFIG_BEACH_SENSOR_BASE_ID "\",\"status\":\"online\"}";
        esp_mqtt_client_publish(s_mqtt_client, MQTT_TOPIC_STATUS, status_payload, 0, 1, 0);
        ESP_LOGI(TAG, "Status response published");
    } else if (cJSON_IsString(command)) {
        ESP_LOGW(TAG, "Unknown command: %s", command->valuestring);
    } else {
        ESP_LOGW(TAG, "JSON saknar 'command'");
    }
    cJSON_Delete(root);
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base, int32_t event_id, void *event_data) {
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        s_mqtt_connected = true;
        ESP_LOGI(TAG, "MQTT connected successfully");
        if (esp_mqtt_client_subscribe(s_mqtt_client, MQTT_TOPIC_COMMAND, 1) >= 0) {  // körs även vid reconnect
            ESP_LOGI(TAG, "Subscribed to: %s", MQTT_TOPIC_COMMAND);
        }
        break;

    case MQTT_EVENT_DISCONNECTED:
        s_mqtt_connected = false;
        ESP_LOGW(TAG, "MQTT_EVENT_DISCONNECTED");
        break;

    case MQTT_EVENT_PUBLISHED:                       // PUBACK för QoS 1
        s_acked_msg_id = event->msg_id;
        xEventGroupSetBits(s_ack_events, MQTT_ACKED_BIT);
        break;

    case MQTT_EVENT_DATA: {
        if (event == NULL) break;
        char topic[128], payload[256];
        int topic_len = event->topic_len < (int)sizeof(topic) ? event->topic_len : (int)sizeof(topic) - 1;
        int data_len = event->data_len < (int)sizeof(payload) ? event->data_len : (int)sizeof(payload) - 1;
        memcpy(topic, event->topic, topic_len);
        topic[topic_len] = '\0';
        memcpy(payload, event->data, data_len);
        payload[data_len] = '\0';
        ESP_LOGI(TAG, "MQTT message received on %s: %s", topic, payload);
        if (strcmp(topic, MQTT_TOPIC_COMMAND) == 0) handle_command(payload);
        break;
    }

    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "MQTT_EVENT_ERROR");
        if (event != NULL && event->error_handle != NULL) {
            ESP_LOGE(TAG, "MQTT error type: %d", event->error_handle->error_type);
        }
        break;

    default:
        break;
    }
}

esp_err_t mqtt_client_module_start(void) {
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    static char client_id[48];
    snprintf(client_id, sizeof(client_id), "%s-%02x%02x%02x", CONFIG_BEACH_SENSOR_BASE_ID, mac[3], mac[4], mac[5]);
    ESP_LOGI(TAG, "MQTT client ID: %s", client_id);

    s_ack_events = xEventGroupCreate();
    if (s_ack_events == NULL) return ESP_ERR_NO_MEM;

    esp_mqtt_client_config_t mqtt_cfg = {
        .broker.address.uri = MQTT_BROKER_URI,
        .credentials.client_id = client_id,
    };
    s_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);   // klienten återansluter automatiskt
    if (s_mqtt_client == NULL) {
        ESP_LOGE(TAG, "Kunde inte initiera MQTT client");
        return ESP_FAIL;
    }

    esp_err_t err = esp_mqtt_client_register_event(s_mqtt_client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Kunde inte registrera MQTT event handler: %s", esp_err_to_name(err));
        return err;
    }
    err = esp_mqtt_client_start(s_mqtt_client);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Kunde inte starta MQTT client: %s", esp_err_to_name(err));
        return err;
    }
    ESP_LOGI(TAG, "MQTT client startad (%s)", MQTT_BROKER_URI);
    return ESP_OK;
}

esp_err_t mqtt_client_module_publish(const char *topic, const char *payload) {
    if (s_mqtt_client == NULL) return ESP_ERR_INVALID_STATE;
    if (!s_mqtt_connected) {
        ESP_LOGW(TAG, "MQTT är inte ansluten - publish avbruten");
        return ESP_ERR_INVALID_STATE;
    }
    if (topic == NULL || payload == NULL) return ESP_ERR_INVALID_ARG;

    int msg_id = esp_mqtt_client_publish(s_mqtt_client, topic, payload, 0, 1, 0);
    if (msg_id < 0) {
        ESP_LOGE(TAG, "MQTT publish misslyckades");
        return ESP_FAIL;
    }
    return ESP_OK;
}

esp_err_t mqtt_client_module_publish_confirmed(const char *topic, const char *payload, int timeout_ms) {
    if (s_mqtt_client == NULL) return ESP_ERR_INVALID_STATE;
    if (!s_mqtt_connected) return ESP_ERR_INVALID_STATE;
    if (topic == NULL || payload == NULL) return ESP_ERR_INVALID_ARG;

    xEventGroupClearBits(s_ack_events, MQTT_ACKED_BIT);
    int msg_id = esp_mqtt_client_publish(s_mqtt_client, topic, payload, 0, 1, 0);
    if (msg_id < 0) return ESP_FAIL;

    TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(timeout_ms);
    for (;;) {
        TickType_t now = xTaskGetTickCount();
        if (now >= deadline) return ESP_ERR_TIMEOUT;
        EventBits_t bits = xEventGroupWaitBits(s_ack_events, MQTT_ACKED_BIT, pdTRUE, pdFALSE, deadline - now);
        if (!(bits & MQTT_ACKED_BIT)) return ESP_ERR_TIMEOUT;
        if (s_acked_msg_id == msg_id) return ESP_OK;
    }
}

bool mqtt_client_module_is_connected(void) {
    return s_mqtt_connected;
}
