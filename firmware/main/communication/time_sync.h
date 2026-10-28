#ifndef TIME_SYNC_H
#define TIME_SYNC_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// MODUL 2: Datakommunikation - SNTP tidssynkronisering (UTC)
// Backend kräver korrekta tidsstämplar (ISO 8601, UTC).
// ============================================================================

void time_sync_start(void);
bool time_sync_wait(int timeout_ms);   // true när klockan är satt
bool time_sync_is_synced(void);

#ifdef __cplusplus
}
#endif

#endif // TIME_SYNC_H
