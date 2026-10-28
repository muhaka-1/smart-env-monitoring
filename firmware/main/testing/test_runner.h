#ifndef TEST_RUNNER_H
#define TEST_RUNNER_H

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// TEST & VERIFIERING: Test Runner & Verification Suite
// Varje testfall utför en verklig kontroll. PASS/FAIL och slutsumman räknas fram från utfallet.
// Aktiveras i menuconfig: Smart Environmental Monitoring -> Kör automatiska systemtester.
// ============================================================================

/**
 * @brief Kör alla testfall TC-01..TC-n och skriver rapport till serieporten.
 * @return antal underkända testfall (0 = alla godkända)
 */
int run_system_self_tests(void);

/**
 * @brief FreeRTOS Task: väntar på Wi-Fi + MQTT (max 60 s), kör testerna och avslutas.
 */
void self_test_task(void *pvParameters);

#ifdef __cplusplus
}
#endif

#endif // TEST_RUNNER_H
