#ifndef DS18B20_DRIVER_H
#define DS18B20_DRIVER_H

#include "esp_err.h"
#include "sensor_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// MODUL 1: ESP32-sensor - DS18B20 vattentemperatur (1-Wire, bit-bangad)
// GPIO väljs i menuconfig (CONFIG_BEACH_TEMP_GPIO). Kräver 4,7 kΩ pull-up till 3,3 V.
// ============================================================================

/** @brief Initialiserar 1-Wire GPIO-pinnen för DS18B20. */
esp_err_t ds18b20_init_pins(void);

/**
 * @brief Läser vattentemperaturen (CRC-kontrollerad). Trådsäker (mutex).
 * @param[out] temp_water_c Temperatur (°C)
 * @param[out] quality      QUALITY_SUSPECT vid 85 °C (värdet efter strömpåslag)
 * @return ESP_OK vid giltig mätning, ESP_ERR_NOT_FOUND om sensorn saknas,
 *         ESP_ERR_INVALID_CRC vid dataskada
 */
esp_err_t ds18b20_read_water_temp(float *temp_water_c, quality_t *quality);

#ifdef __cplusplus
}
#endif

#endif // DS18B20_DRIVER_H
