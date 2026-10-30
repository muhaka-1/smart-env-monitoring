#pragma once
#include "esp_err.h"

void mqtt_publisher_start(void);
// Skickar QoS 1 och väntar på PUBACK. ESP_OK = bekräftad av broker.
esp_err_t mqtt_publisher_send(const char *topic, const char *payload, int timeout_ms);
