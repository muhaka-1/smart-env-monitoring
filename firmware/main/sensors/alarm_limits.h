#ifndef ALARM_LIMITS_H
#define ALARM_LIMITS_H

#include "sensor_types.h"
#include "sdkconfig.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// GRÄNSVÄRDEN FÖR BADVATTENKVALITET (hålls lika med backendens ANOMALY_THRESHOLDS)
// ============================================================================
#define LIMIT_TURBIDITY_MAX_NTU   ((float)CONFIG_BEACH_LIMIT_TURBIDITY_NTU)  // Grumligt vatten = risk
#define LIMIT_WATER_TEMP_MAX_C    ((float)CONFIG_BEACH_LIMIT_WATER_TEMP_C)   // Varmt vatten gynnar algblomning

/**
 * @brief Utvärderar telemetri mot gränsvärden och sätter alarm_code.
 *        Prioritet: sensorfel > grumlighet > temperatur > NONE.
 * @param[in,out] telemetry Pekare till mätstruktur som uppdateras med alarm_code.
 */
void evaluate_alarm_limits(sensor_telemetry_t *telemetry);

#ifdef __cplusplus
}
#endif

#endif // ALARM_LIMITS_H
