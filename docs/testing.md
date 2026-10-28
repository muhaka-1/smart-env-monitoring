# Testdokumentation

Varje testfall anger vad som testas, hur, förväntat resultat och faktiskt resultat.

## A. Firmware-självtester (på enheten, `testing/test_runner.c`)
Aktiveras i menuconfig. Metod: testet utför en verklig kontroll och loggar `[PASS]`/`[FAIL]` med orsak.

| ID | Test | Metod | Förväntat resultat | Faktiskt resultat |
|---|---|---|---|---|
| TC-01 | Turbiditet | `sensor_read_all()` | Giltigt, ändligt värde ≥ 0 NTU | Fylls i efter körning på enhet |
| TC-02 | Vattentemperatur | `sensor_read_all()` | DS18B20 svarar, −5…50 °C | Fylls i efter körning på enhet |
| TC-03 | Tidsstämpel | Läs tid efter SNTP | UTC-tid efter 2023, ms 0–999 | Fylls i efter körning på enhet |
| TC-04 | Larmgräns turbiditet | Mock 45 NTU → `evaluate_alarm_limits` | `ALARM_TURBIDITY_HIGH` | Fylls i efter körning på enhet |
| TC-05 | Larmgräns vatten | Mock 28,5 °C | `ALARM_WATER_OVERHEAT` | Fylls i efter körning på enhet |
| TC-06 | Inget falsklarm | Normalvärden + värde exakt på gränsen | `NONE` | Fylls i efter körning på enhet |
| TC-07 | Sensorbortfall & failsafe | Mock: sensorer ogiltiga | `ERR_SENSOR_DISCONNECTED`, ogiltigt värde serialiseras inte | Fylls i efter körning på enhet |
| TC-08 | JSON-struktur | `serialize_reading_json` + `cJSON_Parse` | Giltig JSON, rätt fält/typer/värden | Fylls i efter körning på enhet |
| TC-09 | JSON buffertskydd | Buffer på 20 byte | Avvisas (false) | Fylls i efter körning på enhet |
| TC-10 | MQTT-topic | `build_reading_topic` | `beach/<id>-turbidity/readings` | Fylls i efter körning på enhet |
| TC-11 | FreeRTOS-kö | Skicka/ta emot ett paket | Oförändrad data | Fylls i efter körning på enhet |
| TC-12 | Task-affinitet | Pinnad task per core | Körs på begärd core | Fylls i efter körning på enhet |
| TC-13 | NVS | Skriv, läs tillbaka | Samma värde | Fylls i efter körning på enhet |
| TC-14 | Wi-Fi | `wifi_manager_is_connected()` | Ansluten | Fylls i efter körning på enhet |
| TC-15 | MQTT-anslutning | Vänta ≤ 10 s | Ansluten till broker | Fylls i efter körning på enhet |
| TC-16 | MQTT-publicering | QoS 1 till `beach/selftest/status` | PUBACK inom 5 s | Fylls i efter körning på enhet |

Logiken bakom TC-01..13 är även körd på dator mot stubbade ESP-IDF-headers och riktiga cJSON: 16/16 godkända, och med ett avsiktligt fel gränsvärde underkändes TC-04 som förväntat. Det ersätter inte körning på enheten.

## B. Backend (Django, `python manage.py test`)
17 tester: validering (HTTP 400), API-nyckel, senaste värde, historik med datumfilter och sortering, per-mätstorhet gränsvärde, dubblettskydd, MQTT-hantering av ogiltig data. **Resultat: 17/17 OK.**

## C. Sensorsimulator (`python -m unittest discover -s tests -t .`)
11 tester: normalisering av dataset, retry/backoff, HTTP-statusmappning, tidsstämpel. **Resultat: 11/11 OK.**

## D. Manuella tester (fylls i)
| ID | Test | Metod | Förväntat | Faktiskt |
|---|---|---|---|---|
| M-01 | End-to-end | ESP32 → MQTT → backend → dashboard | Värden syns inom 10 s | |
| M-02 | Avvikelse | Grumligt vatten / varmt vatten | Rött kort och gränslinje i diagram | |
| M-03 | Kommunikationsfel | Stoppa brokern/Django | Retry loggas, ingen krasch, data kommer efter återstart | |
| M-04 | Sensorbortfall | Dra ur DS18B20 | `ESP_ERR_NOT_FOUND` loggas, turbiditet fortsätter | |
| M-05 | Kalibrering | Klart vatten + referensvatten | NTU nära referensvärdet | |
| M-06 | Långtest | Kör flera timmar | Stabil datainsamling | |
