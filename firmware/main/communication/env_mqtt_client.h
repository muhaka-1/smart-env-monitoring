#ifndef ENV_MQTT_CLIENT_H
#define ENV_MQTT_CLIENT_H

#include <stdbool.h>
#include "esp_err.h"
#include "sdkconfig.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// MODUL 2: Datakommunikation - MQTT-klient (Mosquitto, QoS 1)
// Topics: beach/<id>-<metric>/readings (mätdata) - hanteras av backendens run_mqtt_consumer
//         beach/<id>/status, beach/<id>/command (enhetsstatus och kommandon)
// ============================================================================

#define MQTT_BROKER_URI       CONFIG_BEACH_MQTT_BROKER_URI
#define MQTT_TOPIC_STATUS     "beach/" CONFIG_BEACH_SENSOR_BASE_ID "/status"
#define MQTT_TOPIC_COMMAND    "beach/" CONFIG_BEACH_SENSOR_BASE_ID "/command"

esp_err_t mqtt_client_module_start(void);

/** @brief Skickar QoS 1 och returnerar direkt (som HydroGreen). */
esp_err_t mqtt_client_module_publish(const char *topic, const char *payload);

/** @brief Skickar QoS 1 och väntar på PUBACK från brokern. ESP_OK = bekräftad. */
esp_err_t mqtt_client_module_publish_confirmed(const char *topic, const char *payload, int timeout_ms);

bool mqtt_client_module_is_connected(void);

#ifdef __cplusplus
}
#endif

#endif // ENV_MQTT_CLIENT_H
