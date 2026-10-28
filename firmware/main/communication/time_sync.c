#include "time_sync.h"
#include <time.h>
#include "esp_log.h"
#include "esp_sntp.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "TIME_SYNC";
#define MIN_VALID_EPOCH 1700000000   // klockan anses satt efter nov 2023

void time_sync_start(void) {
    esp_sntp_setoperatingmode(ESP_SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_init();
    ESP_LOGI(TAG, "SNTP startad");
}

bool time_sync_is_synced(void) {
    return time(NULL) > MIN_VALID_EPOCH;
}

bool time_sync_wait(int timeout_ms) {
    for (int waited = 0; waited < timeout_ms; waited += 500) {
        if (time_sync_is_synced()) {
            ESP_LOGI(TAG, "Tid synkad: %lld", (long long)time(NULL));
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    return false;
}
