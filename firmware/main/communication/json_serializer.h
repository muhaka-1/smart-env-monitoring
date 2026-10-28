#ifndef JSON_SERIALIZER_H
#define JSON_SERIALIZER_H

#include <stdbool.h>
#include <stddef.h>
#include "sensor_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// MODUL 2: Datakommunikation - JSON Serializer
// Ett meddelande per mätstorhet, enligt backendens API-kontrakt:
//   {"sensor_id","metric","timestamp","value","unit","quality"}
// ============================================================================

const char *metric_name(metric_t metric);     // "turbidity" / "temperature"
const char *metric_unit(metric_t metric);     // "NTU" / "°C" (UTF-8)
const char *quality_name(quality_t quality);  // "good" / "suspect" / "bad"

/** @brief true om mätstorheten har ett giltigt värde i paketet. */
bool telemetry_metric_valid(const sensor_telemetry_t *data, metric_t metric);

/** @brief Serialiserar en mätstorhet till JSON. false om bufferten är för liten eller data saknas. */
bool serialize_reading_json(const sensor_telemetry_t *data, metric_t metric, char *output_buffer, size_t buffer_size);

/** @brief Bygger MQTT-topic "beach/<base-id>-<metric>/readings". */
bool build_reading_topic(metric_t metric, char *output_buffer, size_t buffer_size);

#ifdef __cplusplus
}
#endif

#endif // JSON_SERIALIZER_H
