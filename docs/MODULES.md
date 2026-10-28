# Moduler

Systemet består av fem moduler. Varje modul har tydligt ansvar, egna mappar och egna tester.

| # | Modul | Ansvar | Var | Tester |
|---|---|---|---|---|
| 1 | **ESP32-sensor** | Muhammad | `firmware/main/sensors/` (+ `sensor/` = PC-simulator utan hårdvara) | TC-01..07 (firmware), `sensor/tests` |
| 2 | **Datakommunikation** | Muhammad | `firmware/main/communication/` (MQTT, Wi-Fi, SNTP, JSON), `sensor/sensor_sim/publishers.py` (MQTT/HTTP + retry) | TC-03, TC-08..16, `sensor/tests` |
| 3 | **Backend / API (Django)** | Muhammad | `backend/monitoring/` (`services.py`, `serializers.py`, `views.py`, `mqtt_consumer.py`) | `backend/monitoring/tests/` |
| 4 | **Databas (SQLite)** | Pat | `backend/monitoring/models.py`, `migrations/` | `test_services.py`, `test_api.py` |
| 5 | **Frontend / Dashboard** | Pat | `backend/monitoring/templates/`, `static/` | manuell/visuell test |

## Gränssnitt mellan modulerna (kontrakt)
**1 → 2:** `sensor_telemetry_t` via FreeRTOS-kön `s_sensor_queue` (sensor_task Core 1 → mqtt_task Core 0).

**2 → 3:** MQTT-topic `beach/<sensor_id>/readings` (QoS 1) eller `POST /api/readings/`, med JSON:
```json
{"sensor_id":"esp32-beach-01-turbidity","metric":"turbidity","timestamp":"2026-01-01T12:00:00.123Z","value":12.3,"unit":"NTU","quality":"good"}
```
**3 → 4:** `services.ingest_reading()` validerar, räknar ut status (OK/ANOMALY) och sparar en `Reading`.

**3 → 5:** REST-API: `/api/readings/latest/`, `/api/readings/?sensor_id=&start=&end=`, `/api/sensors/`.

Ändringar i ett kontrakt kräver en PR som berör båda modulerna.
