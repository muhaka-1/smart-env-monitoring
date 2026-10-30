#pragma once
#include <stdbool.h>

void time_sync_start(void);
bool time_sync_wait(int timeout_ms);   // true när klockan är satt (UTC)
