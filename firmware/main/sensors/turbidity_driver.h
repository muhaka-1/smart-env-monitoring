#ifndef TURBIDITY_DRIVER_H
#define TURBIDITY_DRIVER_H

#include "esp_err.h"
#include "sensor_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// MODUL 1: ESP32-sensor - Turbiditet (analog sensor på ADC1)
// ============================================================================

/** @brief Initierar ADC1 för turbiditetssensorn (gör inget i simulerat läge). */
esp_err_t turbidity_init(void);

/**
 * @brief Läser grumlighet i NTU. Spänningen SJUNKER när vattnet blir grumligare.
 * @param[out] ntu     Grumlighet (NTU, >= 0)
 * @param[out] quality QUALITY_SUSPECT om ADC-ingången är mättad
 * @return ESP_OK vid giltig mätning
 */
esp_err_t turbidity_read_ntu(float *ntu, quality_t *quality);

#ifdef __cplusplus
}
#endif

#endif // TURBIDITY_DRIVER_H
