#include "time_sync.h"
#include <time.h>
#include "esp_log.h"
#include "esp_sntp.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "time";

void time_sync_start(void)
{
    esp_sntp_setoperatingmode(ESP_SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_init();
}

bool time_sync_wait(int timeout_ms)
{
    for (int waited = 0; waited < timeout_ms; waited += 500) {
        time_t now = time(NULL);
        if (now > 1700000000) {  // klockan är satt (efter nov 2023)
            ESP_LOGI(TAG, "Tid synkad: %lld", (long long)now);
            return true;
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    return false;
}
