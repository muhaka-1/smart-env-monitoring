#include "json_serializer.h"
#include <stdio.h>
#include <time.h>
#include "sdkconfig.h"

const char *metric_name(metric_t metric) {
    return metric == METRIC_TURBIDITY ? "turbidity" : "temperature";
}

// "\xc2\xb0" = '°' i UTF-8. Literalen delas eftersom 'C' annars tolkas som hex-siffra.
const char *metric_unit(metric_t metric) {
    return metric == METRIC_TURBIDITY ? "NTU" : "\xc2\xb0" "C";
}

const char *quality_name(quality_t quality) {
    return quality == QUALITY_GOOD ? "good" : quality == QUALITY_SUSPECT ? "suspect" : "bad";
}

bool telemetry_metric_valid(const sensor_telemetry_t *data, metric_t metric) {
    if (data == NULL) return false;
    return metric == METRIC_TURBIDITY ? data->turbidity_valid : data->ds18b20_water_valid;
}

bool serialize_reading_json(const sensor_telemetry_t *data, metric_t metric, char *output_buffer, size_t buffer_size) {
    if (data == NULL || output_buffer == NULL || metric >= METRIC_COUNT) return false;
    if (!telemetry_metric_valid(data, metric)) return false;

    float value = metric == METRIC_TURBIDITY ? data->turbidity_ntu : data->temp_water_c;
    quality_t quality = metric == METRIC_TURBIDITY ? data->turbidity_quality : data->temp_water_quality;

    struct tm tm;
    char ts[24];
    gmtime_r(&data->timestamp_sec, &tm);
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%S", &tm);

    int written = snprintf(
        output_buffer, buffer_size,
        "{\"sensor_id\":\"%s-%s\",\"metric\":\"%s\",\"timestamp\":\"%s.%03dZ\","
        "\"value\":%.2f,\"unit\":\"%s\",\"quality\":\"%s\"}",
        CONFIG_BEACH_SENSOR_BASE_ID, metric_name(metric), metric_name(metric),
        ts, data->timestamp_ms, value, metric_unit(metric), quality_name(quality));

    return (written > 0 && (size_t)written < buffer_size);
}

bool build_reading_topic(metric_t metric, char *output_buffer, size_t buffer_size) {
    if (output_buffer == NULL || metric >= METRIC_COUNT) return false;
    int written = snprintf(output_buffer, buffer_size, "beach/%s-%s/readings",
                           CONFIG_BEACH_SENSOR_BASE_ID, metric_name(metric));
    return (written > 0 && (size_t)written < buffer_size);
}
