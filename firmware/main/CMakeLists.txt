idf_component_register(
    SRCS "main.c" "wifi_manager.c" "time_sync.c" "mqtt_publisher.c" "sensor.c"
    INCLUDE_DIRS "."
    REQUIRES esp_wifi esp_netif esp_event nvs_flash mqtt esp_adc esp_timer
)
