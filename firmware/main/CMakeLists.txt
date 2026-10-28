idf_component_register(
    SRCS
        "main.c"
        # 1. ESP32-sensor (Ansvar: Muhammad)
        "sensors/turbidity_driver.c"
        "sensors/ds18b20_driver.c"
        "sensors/alarm_limits.c"
        "sensors/sensor_task.c"
        # 2. Datakommunikation (Ansvar: Muhammad)
        "communication/wifi_manager.c"
        "communication/time_sync.c"
        "communication/env_mqtt_client.c"
        "communication/json_serializer.c"
        "communication/mqtt_task.c"
        # Test & Verifiering (tvärgående)
        "testing/sensor_mocks.c"
        "testing/test_runner.c"
    INCLUDE_DIRS
        "."
        "sensors"
        "communication"
        "testing"
    REQUIRES
        nvs_flash
        driver
        esp_timer
        esp_event
        esp_adc
        esp_rom
        esp_wifi
        esp_netif
        mqtt
        json
)
