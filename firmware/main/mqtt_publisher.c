#include "mqtt_publisher.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "mqtt_client.h"
#include "sdkconfig.h"

#define CONNECTED_BIT BIT0
#define ACKED_BIT     BIT1
static const char *TAG = "mqtt";
static esp_mqtt_client_handle_t s_client;
static EventGroupHandle_t s_ev;
static volatile int s_acked_id = -1;

static void on_mqtt(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    esp_mqtt_event_handle_t e = data;
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "Ansluten till broker");
        xEventGroupSetBits(s_ev, CONNECTED_BIT);
        break;
    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "Bortkopplad från broker");
        xEventGroupClearBits(s_ev, CONNECTED_BIT);
        break;
    case MQTT_EVENT_PUBLISHED:
        s_acked_id = e->msg_id;
        xEventGroupSetBits(s_ev, ACKED_BIT);
        break;
    default:
        break;
    }
}

void mqtt_publisher_start(void)
{
    s_ev = xEventGroupCreate();
    esp_mqtt_client_config_t cfg = { .broker.address.uri = CONFIG_BEACH_MQTT_BROKER_URI };
    s_client = esp_mqtt_client_init(&cfg);  // klienten återansluter automatiskt
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID, on_mqtt, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_client));
}

esp_err_t mqtt_publisher_send(const char *topic, const char *payload, int timeout_ms)
{
    if (!(xEventGroupGetBits(s_ev) & CONNECTED_BIT)) return ESP_ERR_INVALID_STATE;
    xEventGroupClearBits(s_ev, ACKED_BIT);
    int id = esp_mqtt_client_publish(s_client, topic, payload, 0, 1 /*QoS*/, 0);
    if (id < 0) return ESP_FAIL;

    TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(timeout_ms);
    for (;;) {
        TickType_t now = xTaskGetTickCount();
        if (now >= deadline) return ESP_ERR_TIMEOUT;
        EventBits_t b = xEventGroupWaitBits(s_ev, ACKED_BIT, pdTRUE, pdFALSE, deadline - now);
        if (!(b & ACKED_BIT)) return ESP_ERR_TIMEOUT;
        if (s_acked_id == id) return ESP_OK;
    }
}
