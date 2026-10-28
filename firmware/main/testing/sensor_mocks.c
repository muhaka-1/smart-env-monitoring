#include "sensor_mocks.h"
#include <string.h>

void mock_normal_conditions(sensor_telemetry_t *data) {
    if (!data) return;
    memset(data, 0, sizeof(*data));
    data->timestamp_sec = 1767225600;   // 2026-01-01T00:00:00Z
    data->timestamp_ms = 123;
    data->turbidity_ntu = 5.0f;
    data->temp_water_c = 20.0f;
    data->turbidity_valid = true;
    data->ds18b20_water_valid = true;
    data->turbidity_quality = QUALITY_GOOD;
    data->temp_water_quality = QUALITY_GOOD;
}

void mock_simulate_turbidity_spike(sensor_telemetry_t *data) {
    if (!data) return;
    mock_normal_conditions(data);
    data->turbidity_ntu = 45.0f;        // över gränsen 30 NTU
}

void mock_simulate_overheat_condition(sensor_telemetry_t *data) {
    if (!data) return;
    mock_normal_conditions(data);
    data->temp_water_c = 28.5f;         // över gränsen 25 °C
}

void mock_simulate_sensor_disconnect(sensor_telemetry_t *data) {
    if (!data) return;
    mock_normal_conditions(data);
    data->ds18b20_water_valid = false;
    data->turbidity_valid = false;
}
