#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include "esp_err.h"
#include <stdbool.h>
#include "sdkconfig.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// MODUL 2: Datakommunikation - Wi-Fi Manager
// Ansvar: Muhammad
// Uppgifter läses från menuconfig (Smart Environmental Monitoring -> Nätverk)
// och sparas i sdkconfig, som inte versionshanteras. Skriv aldrig lösenord i koden.
// ============================================================================

#define WIFI_SSID_DEFAULT CONFIG_BEACH_WIFI_SSID
#define WIFI_PASS_DEFAULT CONFIG_BEACH_WIFI_PASSWORD

/**
 * @brief Startar Wi-Fi och väntar max 20 s på IP. Fortsätter försöka i bakgrunden även efter timeout/fel.
 * @return ESP_OK ansluten, ESP_FAIL/ESP_ERR_TIMEOUT ej ansluten än, annat = initieringsfel
 */
esp_err_t wifi_manager_init(void);

bool wifi_manager_is_connected(void);

#ifdef __cplusplus
}
#endif

#endif // WIFI_MANAGER_H
