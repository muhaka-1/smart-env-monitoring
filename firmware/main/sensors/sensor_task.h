#ifndef SENSOR_TASK_H
#define SENSOR_TASK_H

#include "esp_err.h"
#include "sensor_types.h"
#include "sdkconfig.h"

#ifdef __cplusplus
extern "C" {
#endif

#define STATUS_LED_GPIO         CONFIG_BEACH_STATUS_LED_GPIO
#define SENSOR_SAMPLE_RATE_MS   CONFIG_BEACH_SAMPLE_INTERVAL_MS

/**
 * @brief Initierar all sensorhårdvara (status-LED, ADC, 1-Wire).
 */
esp_err_t init_sensor_hardware(void);

/**
 * @brief Läser alla sensorer en gång, stämplar tid och utvärderar larm. Används av sensor_task och självtester.
 */
void sensor_read_all(sensor_telemetry_t *data);

/**
 * @brief FreeRTOS Task (Core 1): kontinuerlig provtagning och köhantering.
 */
void sensor_task(void *pvParameters);

#ifdef __cplusplus
}
#endif

#endif // SENSOR_TASK_H
