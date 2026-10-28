#ifndef SENSOR_MOCKS_H
#define SENSOR_MOCKS_H

#include "sensor_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// TEST & VERIFIERING: Mocks & Fault Injection
// Mockarna ändrar BARA mätvärden/flaggor. Larmkoden räknas fram av evaluate_alarm_limits(),
// så testet verifierar den riktiga larmlogiken (mocken sätter aldrig alarm_code själv).
// ============================================================================

/** @brief Friska normalvärden (5 NTU, 20 °C, båda sensorerna giltiga). */
void mock_normal_conditions(sensor_telemetry_t *data);

/** @brief Simulerar kraftigt grumligt vatten (45 NTU, över gränsen). */
void mock_simulate_turbidity_spike(sensor_telemetry_t *data);

/** @brief Simulerar överhettning av vattnet (28,5 °C, över gränsen). */
void mock_simulate_overheat_condition(sensor_telemetry_t *data);

/** @brief Simulerar sensorbortfall (frånkopplad / timeout). */
void mock_simulate_sensor_disconnect(sensor_telemetry_t *data);

#ifdef __cplusplus
}
#endif

#endif // SENSOR_MOCKS_H
