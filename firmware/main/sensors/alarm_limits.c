#include "alarm_limits.h"
#include <stdio.h>

static void set_alarm(sensor_telemetry_t *t, const char *code) {
    snprintf(t->alarm_code, sizeof(t->alarm_code), "%s", code);  // alltid nollterminerad
}

void evaluate_alarm_limits(sensor_telemetry_t *telemetry) {
    if (telemetry == NULL) return;

    if (!telemetry->turbidity_valid || !telemetry->ds18b20_water_valid) {
        set_alarm(telemetry, "ERR_SENSOR_DISCONNECTED");
    } else if (telemetry->turbidity_ntu > LIMIT_TURBIDITY_MAX_NTU) {
        set_alarm(telemetry, "ALARM_TURBIDITY_HIGH");
    } else if (telemetry->temp_water_c > LIMIT_WATER_TEMP_MAX_C) {
        set_alarm(telemetry, "ALARM_WATER_OVERHEAT");
    } else {
        set_alarm(telemetry, "NONE");
    }
}
