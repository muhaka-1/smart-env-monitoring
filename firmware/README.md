# Firmware (ESP-IDF) - Modul 1 och 2

ESP32 som ersätter `sensor/`-simulatorn. Skickar samma JSON via MQTT till samma backend.
Uppbyggd som HydroGreen/MicroHydros: `sensor_task` (Core 1) → FreeRTOS-kö → `mqtt_task` (Core 0).

## Struktur (efter systemets moduler)
```
firmware/main/
  main.c                  startar kö, sensorer och tasks
  sensor_types.h          sensor_telemetry_t, metric_t, quality_t, s_sensor_queue
  sensors/                MODUL 1: ESP32-sensor
    sensor_task.c/h         sensor_task (Core 1), sensor_read_all()
    turbidity_driver.c/h    turbiditet (ADC1), NTU
    ds18b20_driver.c/h      vattentemperatur (1-Wire, CRC-kontrollerad)
    alarm_limits.c/h        gränsvärden och larmkoder
  communication/          MODUL 2: Datakommunikation
    mqtt_task.c/h           mqtt_task (Core 0): Wi-Fi → SNTP → MQTT → retry
    wifi_manager.c/h        Wi-Fi (återansluter alltid)
    time_sync.c/h           SNTP (UTC)
    env_mqtt_client.c/h     MQTT-klient (QoS 1, PUBACK, command/status)
    json_serializer.c/h     JSON + topic enligt backendens API-kontrakt
  testing/                TEST & VERIFIERING
    test_runner.c/h         självtester TC-01..TC-16 (riktiga kontroller)
    sensor_mocks.c/h        fault injection (värden, aldrig larmkoden)
```
Modul 3-5 (Backend, Databas, Dashboard) finns i `../backend`. Se `../docs/MODULES.md`.

## Krav
- ESP-IDF **v5.2 eller nyare** (testat byggt med v5.5), installerat via ESP-IDF-installern eller VS Code-tillägget *Espressif IDF*.
- Backend + MQTT-broker körs på datorn (se rot-README). Kör kommandon i en **ESP-IDF-terminal**.

## Bygg och flasha
```bash
cd firmware
idf.py set-target esp32          # ESP32 DevKit (ESP-WROOM-32)
# eller
idf.py set-target esp32s3        # Freenove ESP32-S3-WROOM
idf.py menuconfig                # "Smart Environmental Monitoring": Wi-Fi, broker-URI, sensor-ID, intervall
idf.py -p COMx build flash monitor    # (Ctrl+] avslutar monitor)
```
`set-target` läser automatiskt `sdkconfig.defaults` och därefter `sdkconfig.defaults.<target>`, så rätt pinnar för kortet sätts själva.

**Wi-Fi-uppgifter** anges i menuconfig (Nätverk) och sparas i `sdkconfig`, som inte versionshanteras. Skriv aldrig lösenord i koden.

**Byta kort:** kör `idf.py set-target ...` igen. Det **nollställer `sdkconfig`**, så ange Wi-Fi-uppgifter och kalibrering på nytt.
Ändringar i `sdkconfig.defaults*` gäller först när `sdkconfig` genereras om (`set-target` eller radera filen `sdkconfig`).

**Flasha ESP32-S3:** använd den USB-C-port som är märkt UART/COM. Hittas inte kortet, håll **BOOT**, tryck **EN/RST** och släpp BOOT.

## Koppla ihop med backend
1. Datorns LAN-IP (`ipconfig`) sätts i `MQTT broker URI`, t.ex. `mqtt://192.168.1.50:1883`.
2. Starta brokern: `docker compose up -d` (rotmappen).
3. Starta `python manage.py run_mqtt_consumer` och `python manage.py runserver`.
4. Öppna Windows-brandväggen för port 1883.
5. Dashboarden visar `esp32-beach-01-turbidity` och `esp32-beach-01-temperature`.

**Dataflöde:** `sensor_task` stämplar mätningen (UTC) och köar den först när SNTP är synkad → `mqtt_task` skickar **ett meddelande per mätstorhet** till `beach/<id>-<metric>/readings` (QoS 1, väntar på PUBACK, exponentiell backoff vid fel).

## Sensorer och koppling
Standardläget är simulerade värden. Avmarkera *Simulerade mätvärden* i menuconfig för riktig hårdvara.

| Funktion | ESP32 DevKit | Freenove ESP32-S3 |
|---|---|---|
| Turbiditet (analog, via spänningsdelare) | **GPIO34** (ADC1 kanal 6) | **GPIO1** (ADC1 kanal 0) |
| DS18B20 DATA | **GPIO4** | **GPIO21** |
| Status-LED (heartbeat) | GPIO2 (inbyggd) | GPIO2 (inbyggd) |
| 5 V (turbiditetssensorns VCC) | `5V` / `VIN` | `5V` (kortets övre kant eller extension-boardens 5V-skena) |
| 3,3 V (DS18B20 VCC, pull-up) | `3V3` | `3.3V` på extension-boarden |

- **Turbiditet:** sensor VCC → 5 V, GND → GND, signal → **10 kΩ** → mätpunkt → GPIO. Mätpunkten kopplas även via **22 kΩ** till GND (spänningsdelare, ADC tål max 3,3 V).
- **DS18B20:** VCC → 3,3 V, GND → GND, DATA → GPIO, **4,7 kΩ mellan DATA och 3,3 V**.
- Använd bara ADC1-pinnar (ADC2 fungerar inte när Wi-Fi är igång).

**Freenove ESP32-S3, upptagna pinnar:** 4–13 och 15–18 (kamera, GPIO14 är fri), 2 och 48 (lysdioder), 0/3/45/46 (strapping), 19/20 (USB), 43/44 (konsol), 35–37 (PSRAM), 38–40 (SD-kort). Pinnuppgifterna kommer från etiketterna på kortet och Freenoves dokumentation; dubbelkolla mot ditt kort om något beter sig konstigt.

**Kalibrera turbiditet:** spänningen *sjunker* när vattnet blir grumligare, och firmware inverterar det.
1. Läs ADC-råvärdet i klart vatten → `ADC-råvärde i klart vatten`.
2. Läs råvärdet i referensvatten med känd grumlighet → `ADC-råvärde i referensvatten` + `NTU för referensvattnet`.

Omvandlingen är linjär och en grov approximation; sensorn ersätter inte en riktig mätare.
DS18B20 läses med bit-bangad 1-Wire och CRC-kontrolleras; 85 °C (värdet efter strömpåslag) markeras `suspect`.

## Gränsvärden
Backend avgör status (OK/Avvikelse) i databasen och dashboarden. Firmware använder samma gränser för sin lokala larmkod (`alarm_limits`: turbiditet > 30 NTU, vattentemperatur > 25 °C; menuconfig *ESP32-sensor*).

**Ändra gräns:** ändra den på båda ställen: `ANOMALY_THRESHOLD_*` i `backend/config/settings.py` (eller miljövariabel) och `default` i `main/Kconfig.projbuild`. Testet `backend/monitoring/tests/test_firmware_consistency.py` underkänner bygget (lokalt och i CI) om standardvärdena skiljer sig åt. Ändrar du bara via menuconfig eller miljövariabel på en enhet gäller ändringen den enheten.

## Systemtester på enheten
Slå på `Kör automatiska systemtester efter uppstart` i menuconfig och bygg om. `self_test_task` väntar på Wi-Fi + MQTT (max 60 s), kör sedan:
```
[TC-01] Test Turbiditet (ADC / simulerad) ............. [PASS]
...
RESULTAT: 16/16 TESTFALL GODKÄNDA (100% PASS)
```
Testerna är **riktiga kontroller**: ett fel loggas som `[FAIL]` med orsak, och summan räknas från utfallet. Larmtesterna använder `sensor_mocks` som bara ändrar mätvärden, så den riktiga larmlogiken verifieras. Testmeddelandet går till `beach/selftest/status` och ignoreras av backend. Stäng av alternativet för normal drift. Se `../docs/testing.md`.

## Felsökning
- `Tid ej synkad (SNTP)`: Wi-Fi saknar internet; inga mätvärden köas förrän klockan är satt.
- `Försök x/5 misslyckades: ESP_ERR_INVALID_STATE`: ingen anslutning till brokern (fel IP / brandvägg / broker nere).
- Inga värden på dashboard men firmware loggar "Telemetry publicerad": kör `run_mqtt_consumer`.
- `ESP_ERR_NOT_FOUND` från DS18B20: kontrollera 4,7 kΩ pull-up och att DATA sitter på rätt GPIO.
