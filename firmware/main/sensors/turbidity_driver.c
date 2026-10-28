#include "turbidity_driver.h"
#include "esp_log.h"
#include "esp_random.h"
#include "sdkconfig.h"

#if !CONFIG_BEACH_SENSOR_SIMULATED
#include "esp_adc/adc_oneshot.h"
static adc_oneshot_unit_handle_t s_adc;
#endif

static const char *TAG = "TURBIDITY";

#if CONFIG_BEACH_SENSOR_SIMULATED

esp_err_t turbidity_init(void) {
    ESP_LOGI(TAG, "Simulerad turbiditetssensor");
    return ESP_OK;
}

esp_err_t turbidity_read_ntu(float *ntu, quality_t *quality) {
    // Återspelar en realistisk kurva med en avvikelse (> 30 NTU) + lite brus
    static const float curve[] = {2.1f, 2.4f, 3.0f, 2.8f, 4.2f, 3.9f, 5.5f, 12.0f, 35.2f, 41.0f, 18.3f, 6.1f};
    static unsigned idx;
    *ntu = curve[idx++ % (sizeof(curve) / sizeof(curve[0]))] + (esp_random() % 100) / 100.0f;
    *quality = QUALITY_GOOD;
    return ESP_OK;
}

#else

esp_err_t turbidity_init(void) {
    adc_oneshot_unit_init_cfg_t unit = { .unit_id = ADC_UNIT_1 };
    esp_err_t err = adc_oneshot_new_unit(&unit, &s_adc);
    if (err != ESP_OK) return err;
    adc_oneshot_chan_cfg_t chan = { .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_12 };
    err = adc_oneshot_config_channel(s_adc, CONFIG_BEACH_ADC_CHANNEL, &chan);
    if (err == ESP_OK) ESP_LOGI(TAG, "Turbiditet på ADC1 kanal %d", CONFIG_BEACH_ADC_CHANNEL);
    return err;
}

esp_err_t turbidity_read_ntu(float *ntu, quality_t *quality) {
    int sum = 0, raw = 0;
    for (int i = 0; i < 16; i++) {                    // medelvärde dämpar brus
        esp_err_t err = adc_oneshot_read(s_adc, CONFIG_BEACH_ADC_CHANNEL, &raw);
        if (err != ESP_OK) return err;
        sum += raw;
    }
    float avg = sum / 16.0f;
    float span = (float)(CONFIG_BEACH_ADC_RAW_CLEAR - CONFIG_BEACH_ADC_RAW_DIRTY);
    float v = (CONFIG_BEACH_ADC_RAW_CLEAR - avg) * CONFIG_BEACH_NTU_AT_DIRTY / span;  // linjär approximation
    *ntu = v < 0 ? 0 : v;
    *quality = (avg <= 50 || avg >= 4090) ? QUALITY_SUSPECT : QUALITY_GOOD;          // mättad/bruten ingång
    return ESP_OK;
}

#endif
