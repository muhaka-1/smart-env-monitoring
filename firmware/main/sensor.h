#pragma once
#include <time.h>
#include "esp_err.h"

typedef enum { QUALITY_GOOD, QUALITY_SUSPECT, QUALITY_BAD } quality_t;

typedef struct {
    time_t sec;      // UTC-tid vid mätning
    int ms;
    float value;     // NTU
    quality_t quality;
} sample_t;

esp_err_t sensor_init(void);
esp_err_t sensor_read(sample_t *out);   // fyller värde + tidsstämpel
const char *quality_str(quality_t q);
