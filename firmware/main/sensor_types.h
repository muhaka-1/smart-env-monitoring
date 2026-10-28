#ifndef SENSOR_TYPES_H
#define SENSOR_TYPES_H

#include <stdint.h>
#include <stdbool.h>
#include <time.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// TYPDEFINITIONER FÖR SENSORDATA & TELEMETRI
// ============================================================================
typedef enum {
    METRIC_TURBIDITY = 0,   // Vattengrumlighet (NTU)
    METRIC_TEMPERATURE,     // Vattentemperatur (°C)
    METRIC_COUNT
} metric_t;

typedef enum {
    QUALITY_GOOD = 0,
    QUALITY_SUSPECT,
    QUALITY_BAD
} quality_t;

typedef struct {
    time_t   timestamp_sec;         // UTC-tid vid mätning (SNTP)
    int      timestamp_ms;          // Millisekunder 0-999

    float    turbidity_ntu;         // Vattengrumlighet (NTU)
    float    temp_water_c;          // Vattentemperatur (°C)

    bool     turbidity_valid;       // Statusflagga turbiditetssensor
    bool     ds18b20_water_valid;   // Statusflagga DS18B20 vatten
    quality_t turbidity_quality;    // good / suspect / bad
    quality_t temp_water_quality;

    uint32_t uptime_seconds;        // Systemets drifttid i sekunder
    char     alarm_code[32];        // "NONE", "ALARM_TURBIDITY_HIGH", ...
} sensor_telemetry_t;

// Global FreeRTOS-kö för att skicka mätdata från sensor_task (Core 1) till mqtt_task (Core 0)
extern QueueHandle_t s_sensor_queue;

#ifdef __cplusplus
}
#endif

#endif // SENSOR_TYPES_H
