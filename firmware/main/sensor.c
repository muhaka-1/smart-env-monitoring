#include "sensor.h"
#include <sys/time.h>
#include "esp_log.h"
#include "esp_random.h"
#include "sdkconfig.h"

#if !CONFIG_BEACH_SENSOR_SIMULATED
#include "esp_adc/adc_oneshot.h"
static adc_oneshot_unit_handle_t s_adc;
#endif

static const char *TAG = "sensor";

const char *quality_str(quality_t q)
{
    return q == QUALITY_GOOD ? "good" : q == QUALITY_SUSPECT ? "suspect" : "bad";
}

esp_err_t sensor_init(void)
{
#if CONFIG_BEACH_SENSOR_SIMULATED
    ESP_LOGI(TAG, "Simulerad sensor");
    return ESP_OK;
#else
    adc_oneshot_unit_init_cfg_t u = { .unit_id = ADC_UNIT_1 };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&u, &s_adc));
    adc_oneshot_chan_cfg_t c = { .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT };
    return adc_oneshot_config_channel(s_adc, CONFIG_BEACH_ADC_CHANNEL, &c);
#endif
}

esp_err_t sensor_read(sample_t *out)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    out->sec = tv.tv_sec;
    out->ms = tv.tv_usec / 1000;
    out->quality = QUALITY_GOOD;

#if CONFIG_BEACH_SENSOR_SIMULATED
    // Återspelar en realistisk kurva med en avvikelse (>30 NTU) + lite brus
    static const float curve[] = {2.1f, 2.4f, 3.0f, 2.8f, 4.2f, 3.9f, 5.5f, 12.0f, 35.2f, 41.0f, 18.3f, 6.1f};
    static unsigned idx;
    out->value = curve[idx++ % (sizeof(curve) / sizeof(curve[0]))] + (esp_random() % 100) / 100.0f;
    return ESP_OK;
#else
    int raw = 0;
    esp_err_t err = adc_oneshot_read(s_adc, CONFIG_BEACH_ADC_CHANNEL, &raw);
    if (err != ESP_OK) return err;
    out->value = (float)raw * CONFIG_BEACH_NTU_FULL_SCALE / 4095.0f;  // PLACEHOLDER-kalibrering
    if (raw <= 0 || raw >= 4095) out->quality = QUALITY_SUSPECT;      // mättad ingång
    return ESP_OK;
#endif
}
