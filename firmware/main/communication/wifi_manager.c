#include "wifi_manager.h"

#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"

#include <string.h>

static const char *TAG = "WIFI_MANAGER";

#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1
#define WIFI_MAX_RETRY     10

static EventGroupHandle_t s_wifi_event_group = NULL;
static bool s_is_connected = false;
static int s_retry_count = 0;

static void wifi_event_handler(
    void *arg,
    esp_event_base_t event_base,
    int32_t event_id,
    void *event_data)
{
    (void)arg;
    (void)event_data;

    if (event_base == WIFI_EVENT &&
        event_id == WIFI_EVENT_STA_START)
    {
        ESP_LOGI(TAG, "Wi-Fi STA startad");
        esp_wifi_connect();
    }
    else if (event_base == WIFI_EVENT &&
             event_id == WIFI_EVENT_STA_DISCONNECTED)
    {
        s_is_connected = false;
        s_retry_count++;
        esp_wifi_connect();  // försök alltid igen - en sensor ska återansluta själv

        if (s_retry_count < WIFI_MAX_RETRY)
        {
            ESP_LOGW(
                TAG,
                "Wi-Fi disconnected - försöker igen (%d/%d)",
                s_retry_count,
                WIFI_MAX_RETRY
            );
        }
        else if (s_retry_count == WIFI_MAX_RETRY)
        {
            // Släpp wifi_manager_init(), men fortsätt försöka i bakgrunden
            xEventGroupSetBits(
                s_wifi_event_group,
                WIFI_FAIL_BIT
            );

            ESP_LOGE(
                TAG,
                "Wi-Fi ansluter inte efter %d försök - fortsätter försöka",
                WIFI_MAX_RETRY
            );
        }
    }
    else if (event_base == IP_EVENT &&
             event_id == IP_EVENT_STA_GOT_IP)
    {
        ip_event_got_ip_t *event =
            (ip_event_got_ip_t *)event_data;

        s_retry_count = 0;
        s_is_connected = true;

        ESP_LOGI(
            TAG,
            "Wi-Fi ansluten! IP: "
            IPSTR,
            IP2STR(&event->ip_info.ip)
        );

        xEventGroupSetBits(
            s_wifi_event_group,
            WIFI_CONNECTED_BIT
        );
    }
}

esp_err_t wifi_manager_init(void)
{
    if (s_wifi_event_group != NULL)
    {
        return ESP_ERR_INVALID_STATE;
    }

    ESP_LOGI(
        TAG,
        "Startar Wi-Fi Manager för SSID: %s",
        WIFI_SSID_DEFAULT
    );

    s_wifi_event_group = xEventGroupCreate();

    if (s_wifi_event_group == NULL)
    {
        ESP_LOGE(
            TAG,
            "Kunde inte skapa Wi-Fi event group"
        );

        return ESP_ERR_NO_MEM;
    }

    esp_err_t err;

    // ------------------------------------------------------------------------
    // TCP/IP stack
    // ------------------------------------------------------------------------

    err = esp_netif_init();

    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE)
    {
        ESP_LOGE(
            TAG,
            "esp_netif_init() misslyckades: %s",
            esp_err_to_name(err)
        );

        return err;
    }

    // ------------------------------------------------------------------------
    // Default event loop
    // ------------------------------------------------------------------------

    err = esp_event_loop_create_default();

    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE)
    {
        ESP_LOGE(
            TAG,
            "esp_event_loop_create_default() misslyckades: %s",
            esp_err_to_name(err)
        );

        return err;
    }

    // ------------------------------------------------------------------------
    // Default Wi-Fi station interface
    // ------------------------------------------------------------------------

    esp_netif_create_default_wifi_sta();

    // ------------------------------------------------------------------------
    // Wi-Fi driver
    // ------------------------------------------------------------------------

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();

    err = esp_wifi_init(&cfg);

    if (err != ESP_OK)
    {
        ESP_LOGE(
            TAG,
            "esp_wifi_init() misslyckades: %s",
            esp_err_to_name(err)
        );

        return err;
    }

    // ------------------------------------------------------------------------
    // Event handlers
    // ------------------------------------------------------------------------

    err = esp_event_handler_register(
        WIFI_EVENT,
        ESP_EVENT_ANY_ID,
        &wifi_event_handler,
        NULL
    );

    if (err != ESP_OK)
    {
        ESP_LOGE(
            TAG,
            "Kunde inte registrera Wi-Fi event handler: %s",
            esp_err_to_name(err)
        );

        return err;
    }

    err = esp_event_handler_register(
        IP_EVENT,
        IP_EVENT_STA_GOT_IP,
        &wifi_event_handler,
        NULL
    );

    if (err != ESP_OK)
    {
        ESP_LOGE(
            TAG,
            "Kunde inte registrera IP event handler: %s",
            esp_err_to_name(err)
        );

        return err;
    }

    // ------------------------------------------------------------------------
    // Wi-Fi configuration
    // ------------------------------------------------------------------------

    wifi_config_t wifi_config = {
        .sta = {
            .ssid = WIFI_SSID_DEFAULT,
            .password = WIFI_PASS_DEFAULT,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };

    err = esp_wifi_set_mode(WIFI_MODE_STA);

    if (err != ESP_OK)
    {
        return err;
    }

    err = esp_wifi_set_config(
        WIFI_IF_STA,
        &wifi_config
    );

    if (err != ESP_OK)
    {
        ESP_LOGE(
            TAG,
            "esp_wifi_set_config() misslyckades: %s",
            esp_err_to_name(err)
        );

        return err;
    }

    // ------------------------------------------------------------------------
    // Start Wi-Fi
    // ------------------------------------------------------------------------

    err = esp_wifi_start();

    if (err != ESP_OK)
    {
        ESP_LOGE(
            TAG,
            "esp_wifi_start() misslyckades: %s",
            esp_err_to_name(err)
        );

        return err;
    }

    ESP_LOGI(
        TAG,
        "Wi-Fi Manager startad - väntar på IP-adress..."
    );

    // ------------------------------------------------------------------------
    // Wait until IP address is obtained
    // ------------------------------------------------------------------------

    EventBits_t bits = xEventGroupWaitBits(
        s_wifi_event_group,
        WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
        pdFALSE,
        pdFALSE,
        pdMS_TO_TICKS(20000)
    );

    if (bits & WIFI_CONNECTED_BIT)
    {
        ESP_LOGI(
            TAG,
            "Wi-Fi är redo för MQTT"
        );

        return ESP_OK;
    }

    if (bits & WIFI_FAIL_BIT)
    {
        ESP_LOGE(
            TAG,
            "Wi-Fi-anslutning misslyckades"
        );

        return ESP_FAIL;
    }

    ESP_LOGE(
        TAG,
        "Timeout: Wi-Fi fick ingen IP-adress inom 20 sekunder"
    );

    return ESP_ERR_TIMEOUT;
}

bool wifi_manager_is_connected(void)
{
    return s_is_connected;
}