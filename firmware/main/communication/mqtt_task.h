#ifndef MQTT_TASK_H
#define MQTT_TASK_H

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// MODUL 2: Datakommunikation - FreeRTOS MQTT Task (Ansvar: Muhammad)
// ============================================================================

/**
 * @brief FreeRTOS Task på Core 0: startar Wi-Fi, SNTP och MQTT, och publicerar
 *        telemetri från s_sensor_queue (ett meddelande per mätstorhet) med retry.
 */
void mqtt_task(void *pvParameters);

#ifdef __cplusplus
}
#endif

#endif // MQTT_TASK_H
