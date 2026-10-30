# Firmware (ESP-IDF)

ESP32 som ersätter `sensor/`-simulatorn. Skickar samma JSON via MQTT till samma backend.

**Core 1:** `sensor_task` mäter med jämna intervall (`vTaskDelayUntil`) → FreeRTOS-kö.
**Core 0:** `comm_task` läser kön, bygger JSON, publicerar QoS 1 och väntar på PUBACK, med retry (exponentiell backoff).
På enkärniga chip (C3) körs båda på core 0.

## Krav
- ESP-IDF **v5.2 eller nyare**, installerat (tillägget *Espressif IDF* i VS Code, eller `install` + `export`-skripten).
- Backend + MQTT-broker körs på datorn (se rot-README).

## Bygg och flasha
```bash
cd firmware
idf.py set-target esp32          # eller esp32s3 / esp32c3
idf.py menuconfig                # "Beach Sensor": Wi-Fi, broker-URI, sensor-ID, intervall
idf.py build flash monitor       # (Ctrl+] avslutar monitor)
```
Alternativt redigera `sdkconfig.defaults` före första bygget.

## Koppla ihop med backend
1. Skaffa datorns LAN-IP (`ipconfig`) och sätt den i `BEACH_MQTT_BROKER_URI`, t.ex. `mqtt://192.168.1.50:1883`.
2. Starta brokern: `docker compose up -d` (rotmappen). Mosquitto-konfigen tillåter anonyma anslutningar på 1883.
3. Starta `python manage.py run_mqtt_consumer` och `python manage.py runserver`.
4. Öppna Windows-brandväggen för port 1883.
5. Dashboarden visar sensorn `esp32-beach-01-turbidity` (eller ditt valda ID).

## Riktig sensor
Avmarkera `Simulerade matvärden` i menuconfig, ange ADC-kanal och `NTU vid full ADC-utslag`.
Omvandlingen är en linjär **platshållare** - kalibrera mot din sensors datablad.

## Felsökning
- `SNTP misslyckades`: Wi-Fi saknar internet.
- `Försök x/5 misslyckades: ESP_ERR_INVALID_STATE`: ingen anslutning till brokern (fel IP / brandvägg / broker nere).
- Inga värden på dashboard men firmware loggar "Skickade": kör `run_mqtt_consumer`.
