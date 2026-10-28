#include "test_runner.h"
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include "alarm_limits.h"
#include "cJSON.h"
#include "env_mqtt_client.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "json_serializer.h"
#include "nvs.h"
#include "sdkconfig.h"
#include "sensor_mocks.h"
#include "sensor_task.h"
#include "sensor_types.h"
#include "time_sync.h"
#include "wifi_manager.h"

static const char *TAG = "TEST_RUNNER";
#define LINE_WIDTH 46
#define NUM_CORES (CONFIG_FREERTOS_UNICORE ? 1 : 2)

typedef bool (*test_fn)(char *why, size_t why_len);
typedef struct { const char *name; test_fn fn; } test_case_t;

#define FAIL(...) do { snprintf(why, why_len, __VA_ARGS__); return false; } while (0)

/* ======================= 1. ESP32-sensor ======================= */

static bool tc_turbidity(char *why, size_t why_len) {
    sensor_telemetry_t t;
    sensor_read_all(&t);
    if (!t.turbidity_valid) FAIL("turbiditetssensorn gav fel");
    if (!isfinite(t.turbidity_ntu) || t.turbidity_ntu < 0) FAIL("ogiltigt värde %.2f NTU", t.turbidity_ntu);
    return true;
}

static bool tc_water_temp(char *why, size_t why_len) {
    sensor_telemetry_t t;
    sensor_read_all(&t);
    if (!t.ds18b20_water_valid) FAIL("DS18B20 svarade inte (kontrollera 4,7 kΩ pull-up)");
    if (!isfinite(t.temp_water_c) || t.temp_water_c < -5.0f || t.temp_water_c > 50.0f) FAIL("orimligt värde %.2f C", t.temp_water_c);
    return true;
}

static bool tc_timestamp(char *why, size_t why_len) {
    sensor_telemetry_t t;
    sensor_read_all(&t);
    if (!time_sync_is_synced()) FAIL("klockan ej synkad via SNTP");
    if (t.timestamp_sec < 1700000000) FAIL("tidsstämpel ogiltig (sec=%lld)", (long long)t.timestamp_sec);
    if (t.timestamp_ms < 0 || t.timestamp_ms > 999) FAIL("ms utanför 0-999: %d", t.timestamp_ms);
    return true;
}

/* ======================= Larmlogik (mocks) ======================= */

static bool tc_alarm_turbidity(char *why, size_t why_len) {
    sensor_telemetry_t t;
    mock_simulate_turbidity_spike(&t);
    evaluate_alarm_limits(&t);
    if (strcmp(t.alarm_code, "ALARM_TURBIDITY_HIGH") != 0) FAIL("förväntade ALARM_TURBIDITY_HIGH, fick %s", t.alarm_code);
    return true;
}

static bool tc_alarm_temp(char *why, size_t why_len) {
    sensor_telemetry_t t;
    mock_simulate_overheat_condition(&t);
    evaluate_alarm_limits(&t);
    if (strcmp(t.alarm_code, "ALARM_WATER_OVERHEAT") != 0) FAIL("förväntade ALARM_WATER_OVERHEAT, fick %s", t.alarm_code);
    return true;
}

static bool tc_alarm_none(char *why, size_t why_len) {
    sensor_telemetry_t t;
    mock_normal_conditions(&t);
    evaluate_alarm_limits(&t);
    if (strcmp(t.alarm_code, "NONE") != 0) FAIL("normala värden gav falskt larm: %s", t.alarm_code);
    t.turbidity_ntu = LIMIT_TURBIDITY_MAX_NTU;   // exakt på gränsen = fortfarande OK
    evaluate_alarm_limits(&t);
    if (strcmp(t.alarm_code, "NONE") != 0) FAIL("värde exakt på gränsen gav larm: %s", t.alarm_code);
    return true;
}

static bool tc_sensor_failsafe(char *why, size_t why_len) {
    sensor_telemetry_t t;
    char buf[320];
    mock_simulate_sensor_disconnect(&t);
    evaluate_alarm_limits(&t);
    if (strcmp(t.alarm_code, "ERR_SENSOR_DISCONNECTED") != 0) FAIL("förväntade ERR_SENSOR_DISCONNECTED, fick %s", t.alarm_code);
    if (serialize_reading_json(&t, METRIC_TURBIDITY, buf, sizeof(buf))) FAIL("ogiltigt värde serialiserades ändå");
    return true;
}

/* ======================= 2. Datakommunikation: JSON ======================= */

static bool tc_json(char *why, size_t why_len) {
    sensor_telemetry_t t;
    char buf[320];
    mock_normal_conditions(&t);
    t.temp_water_c = 21.5f;
    if (!serialize_reading_json(&t, METRIC_TEMPERATURE, buf, sizeof(buf))) FAIL("serialize_reading_json misslyckades");

    cJSON *root = cJSON_Parse(buf);
    if (root == NULL) FAIL("ogiltig JSON: %s", buf);
    bool ok = true;
    cJSON *id = cJSON_GetObjectItem(root, "sensor_id");
    cJSON *metric = cJSON_GetObjectItem(root, "metric");
    cJSON *ts = cJSON_GetObjectItem(root, "timestamp");
    cJSON *value = cJSON_GetObjectItem(root, "value");
    cJSON *unit = cJSON_GetObjectItem(root, "unit");
    cJSON *quality = cJSON_GetObjectItem(root, "quality");
    if (!cJSON_IsString(id) || strcmp(id->valuestring, CONFIG_BEACH_SENSOR_BASE_ID "-temperature") != 0) { snprintf(why, why_len, "fel sensor_id"); ok = false; }
    else if (!cJSON_IsString(metric) || strcmp(metric->valuestring, "temperature") != 0) { snprintf(why, why_len, "fel metric"); ok = false; }
    else if (!cJSON_IsString(ts) || strcmp(ts->valuestring, "2026-01-01T00:00:00.123Z") != 0) { snprintf(why, why_len, "fel timestamp"); ok = false; }
    else if (!cJSON_IsNumber(value) || fabs(value->valuedouble - 21.5) > 0.01) { snprintf(why, why_len, "fel value"); ok = false; }
    else if (!cJSON_IsString(unit) || strcmp(unit->valuestring, "\xc2\xb0" "C") != 0) { snprintf(why, why_len, "fel unit"); ok = false; }
    else if (!cJSON_IsString(quality) || strcmp(quality->valuestring, "good") != 0) { snprintf(why, why_len, "fel quality"); ok = false; }
    cJSON_Delete(root);
    return ok;
}

static bool tc_json_overflow(char *why, size_t why_len) {
    sensor_telemetry_t t;
    char tiny[20];
    mock_normal_conditions(&t);
    if (serialize_reading_json(&t, METRIC_TURBIDITY, tiny, sizeof(tiny))) FAIL("för liten buffer avvisades inte");
    return true;
}

static bool tc_topic(char *why, size_t why_len) {
    char topic[96];
    if (!build_reading_topic(METRIC_TURBIDITY, topic, sizeof(topic))) FAIL("build_reading_topic misslyckades");
    if (strcmp(topic, "beach/" CONFIG_BEACH_SENSOR_BASE_ID "-turbidity/readings") != 0) FAIL("fel topic: %s", topic);
    return true;
}

/* ======================= FreeRTOS / minne ======================= */

static bool tc_queue(char *why, size_t why_len) {
    QueueHandle_t q = xQueueCreate(2, sizeof(sensor_telemetry_t));
    if (!q) FAIL("xQueueCreate misslyckades");
    sensor_telemetry_t in, out;
    mock_simulate_turbidity_spike(&in);
    memset(&out, 0, sizeof(out));
    bool ok = xQueueSend(q, &in, 0) == pdTRUE && xQueueReceive(q, &out, pdMS_TO_TICKS(100)) == pdTRUE
              && out.turbidity_ntu == in.turbidity_ntu && out.timestamp_sec == in.timestamp_sec;
    vQueueDelete(q);
    if (!ok) FAIL("data ändrades eller förlorades i kön");
    return true;
}

typedef struct { int actual_core; TaskHandle_t waiter; } core_probe_t;

static void core_probe_task(void *arg) {
    core_probe_t *p = arg;
    p->actual_core = xPortGetCoreID();
    xTaskNotifyGive(p->waiter);
    vTaskDelete(NULL);
}

static bool tc_cores(char *why, size_t why_len) {
    for (int core = 0; core < NUM_CORES; core++) {
        core_probe_t p = { .actual_core = -1, .waiter = xTaskGetCurrentTaskHandle() };
        if (xTaskCreatePinnedToCore(core_probe_task, "probe", 2048, &p, 5, NULL, core) != pdPASS) FAIL("kunde inte skapa task på core %d", core);
        if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(1000)) == 0) FAIL("task på core %d svarade inte", core);
        if (p.actual_core != core) FAIL("begärde core %d, körde på %d", core, p.actual_core);
    }
    return true;
}

static bool tc_nvs(char *why, size_t why_len) {
    nvs_handle_t h;
    esp_err_t e = nvs_open("selftest", NVS_READWRITE, &h);
    if (e != ESP_OK) FAIL("nvs_open: %s", esp_err_to_name(e));
    uint32_t magic = 0xBEAC4001u ^ (uint32_t)time(NULL), back = 0;
    e = nvs_set_u32(h, "magic", magic);
    if (e == ESP_OK) e = nvs_commit(h);
    if (e == ESP_OK) e = nvs_get_u32(h, "magic", &back);
    nvs_close(h);
    if (e != ESP_OK) FAIL("NVS-fel: %s", esp_err_to_name(e));
    if (back != magic) FAIL("läste tillbaka fel värde");
    return true;
}

/* ======================= 2. Datakommunikation: nätverk ======================= */

static bool tc_wifi(char *why, size_t why_len) {
    if (!wifi_manager_is_connected()) FAIL("Wi-Fi inte anslutet");
    return true;
}

static bool tc_mqtt_connected(char *why, size_t why_len) {
    for (int i = 0; i < 100 && !mqtt_client_module_is_connected(); i++) vTaskDelay(pdMS_TO_TICKS(100));  // max 10 s
    if (!mqtt_client_module_is_connected()) FAIL("ingen anslutning till %s", MQTT_BROKER_URI);
    return true;
}

static bool tc_mqtt_publish(char *why, size_t why_len) {
    // Topic utanför beach/+/readings, så backend ignorerar testmeddelandet.
    esp_err_t e = mqtt_client_module_publish_confirmed("beach/selftest/status", "{\"selftest\":true}", 5000);
    if (e != ESP_OK) FAIL("publicering ej bekräftad (PUBACK): %s", esp_err_to_name(e));
    return true;
}

static const test_case_t TESTS[] = {
    { "Test Turbiditet (ADC / simulerad)",      tc_turbidity },
    { "Test Vattentemperatur (1-Wire / sim.)",  tc_water_temp },
    { "Test Tidsstämpel (SNTP, UTC)",           tc_timestamp },
    { "Test Larmgräns Turbiditet (> 30 NTU)",   tc_alarm_turbidity },
    { "Test Larmgräns Vatten (> 25 C)",         tc_alarm_temp },
    { "Test Inget falsklarm (normalvärden)",    tc_alarm_none },
    { "Test Sensorbortfall & Failsafe",         tc_sensor_failsafe },
    { "Test cJSON Telemetristruktur",           tc_json },
    { "Test JSON Buffertskydd",                 tc_json_overflow },
    { "Test MQTT Topic-format",                 tc_topic },
    { "Test FreeRTOS Kö (dataintegritet)",      tc_queue },
    { "Test Task-affinitet (Core 0 / Core 1)",  tc_cores },
    { "Test NVS Flash Minneslagring",           tc_nvs },
    { "Test Wi-Fi Anslutning",                  tc_wifi },
    { "Test MQTT Anslutning",                   tc_mqtt_connected },
    { "Test MQTT Publicering (QoS 1 PUBACK)",   tc_mqtt_publish },
};
#define TEST_COUNT ((int)(sizeof(TESTS) / sizeof(TESTS[0])))

static int utf8_len(const char *s) {
    int n = 0;
    for (; *s; s++) if (((unsigned char)*s & 0xC0) != 0x80) n++;
    return n;
}

int run_system_self_tests(void) {
    int passed = 0;
    ESP_LOGI(TAG, "==================================================");
    ESP_LOGI(TAG, "   KÖR AUTOMATISERADE SYSTEMTESTER (TC-01 - TC-%02d)", TEST_COUNT);
    ESP_LOGI(TAG, "==================================================");

    for (int i = 0; i < TEST_COUNT; i++) {
        char why[96] = "";
        bool ok = TESTS[i].fn(why, sizeof(why));
        char dots[LINE_WIDTH + 1];
        int pad = LINE_WIDTH - utf8_len(TESTS[i].name);
        if (pad < 3) pad = 3;
        if (pad > LINE_WIDTH) pad = LINE_WIDTH;
        memset(dots, '.', pad);
        dots[pad] = '\0';
        if (ok) {
            passed++;
            ESP_LOGI(TAG, "[TC-%02d] %s %s [PASS]", i + 1, TESTS[i].name, dots);
        } else {
            ESP_LOGE(TAG, "[TC-%02d] %s %s [FAIL]", i + 1, TESTS[i].name, dots);
            ESP_LOGE(TAG, "        -> %s", why);
        }
    }

    ESP_LOGI(TAG, "==================================================");
    if (passed == TEST_COUNT) {
        ESP_LOGI(TAG, "   RESULTAT: %d/%d TESTFALL GODKÄNDA (100%% PASS)", passed, TEST_COUNT);
    } else {
        ESP_LOGE(TAG, "   RESULTAT: %d/%d TESTFALL GODKÄNDA (%d%% PASS), %d UNDERKÄNDA",
                 passed, TEST_COUNT, passed * 100 / TEST_COUNT, TEST_COUNT - passed);
    }
    ESP_LOGI(TAG, "==================================================");
    return TEST_COUNT - passed;
}

void self_test_task(void *pvParameters) {
    // Nätverkstesterna kräver Wi-Fi + MQTT, som startas av mqtt_task.
    for (int i = 0; i < 600 && !mqtt_client_module_is_connected(); i++) vTaskDelay(pdMS_TO_TICKS(100));
    if (!mqtt_client_module_is_connected()) ESP_LOGW(TAG, "MQTT ej uppe efter 60 s - nätverkstester kommer att underkännas");
    run_system_self_tests();
    vTaskDelete(NULL);
}
