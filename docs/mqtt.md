# MQTT: lokal broker, publicering och mottagning

Beslutet (MQTT som huvudtransport, HTTP som lokal reservlösning) finns i `docs/protocol-decision.md` (issue #4).

## 1. Starta och stoppa brokern lokalt
Kräver Docker. Konfigurationen finns i `infra/mosquitto.conf` (port 1883, anonyma klienter, endast för lokal utveckling).
```bash
docker compose up -d                       # startar Mosquitto
docker compose ps                          # ska visa mosquitto som "running"
docker compose logs mosquitto --tail 5     # visar anslutningar och eventuella fel
docker compose stop                        # stoppar (används för avbrottstester)
docker compose start                       # startar igen
docker compose down                        # tar bort containern
```

## 2. Topic och meddelandeformat
| | |
|---|---|
| Topic | `beach/<sensor_id>/readings`, t.ex. `beach/ohio-street-beach-turbidity/readings` |
| QoS | 1 (minst en gång) |
| Format | JSON: `sensor_id`, `metric`, `timestamp` (UTC, ISO 8601), `value`, `unit`, `quality` |

Mottagaren prenumererar på `beach/+/readings`. Övriga topics (till exempel `beach/selftest/status`) ignoreras.

## 3. Verifiera med ett separat klientverktyg
`mosquitto_sub` finns inne i broker-containern, så inget extra behöver installeras:
```bash
docker compose exec mosquitto mosquitto_sub -t "beach/#" -v     # lyssna på alla mätningar (Ctrl+C avslutar)
docker compose exec mosquitto mosquitto_pub -t beach/test/readings -m '{"sensor_id":"x"}'   # skicka ett testmeddelande
```
Starta lyssnaren först och kör sedan `python -m sensor_sim --transport mqtt --offline --count 3 --interval 2` i `sensor/`.

## 4. Mottagaren (backend)
```bash
cd backend
python manage.py migrate
python manage.py run_mqtt_consumer
```
- Anropar `services.ingest_reading()`, **samma funktion som `POST /api/readings/`**. Validering och statusberäkning finns därför på ett enda ställe och dupliceras inte. (Mottagaren går inte via HTTP; det sparar ett nätverkshopp och ger samma regler.)
- Ogiltig JSON eller ogiltig data loggas och hoppas över. Ett oväntat fel (till exempel databasfel) loggas med detaljer och stoppar inte mottagaren.
- Loggarna innehåller sensor-ID, tid och värde samt fältnamn med valideringsfel, aldrig hela meddelanden eller nycklar.
- Varje mottagare får ett unikt klient-ID (`django-ingestor-<dator>-<pid>`, kan sättas med `MQTT_CLIENT_ID`). Ett fast ID får två mottagare att kasta ut varandra i en reconnect-loop.
- Startar brokern senare än mottagaren försöker mottagaren igen i stället för att avsluta. Efter ett avbrott loggas `Bortkopplad från broker` och därefter `Ansluten till broker` när anslutningen är tillbaka (prenumerationen görs om automatiskt).

## 5. Felhantering i sändaren
| Fel | Beteende |
|---|---|
| Brokern nere eller publicering misslyckas | upp till 5 försök, väntetid 1, 2, 4 och 8 s, varje försök loggas |
| Alla försök misslyckas | `Gav upp efter 5 försök - datapunkt förlorad` med hela meddelandet |
| Brokern kommer tillbaka under pågående retry | nästa försök lyckas, ingen omstart behövs |

## 6. Manuellt testprotokoll
Kör med riktig Mosquitto och fyll i kolumnen "Faktiskt".

| ID | Issue | Test | Förväntat | Faktiskt |
|---|---|---|---|---|
| M-14.1 | #14 | `docker compose up -d`, sedan `docker compose ps` | mosquitto "running" | |
| M-14.2 | #14 | `mosquitto_sub -t "beach/#" -v` + simulatorn med `--transport mqtt --count 3` | tre meddelanden på `beach/<sensor_id>/readings` med alla fält | |
| M-15.1 | #15 | mottagare + Django + simulator (3 meddelanden) | `Sparade ...` tre gånger, värdena syns i `/api/readings/latest/` | |
| M-15.2 | #15 | `mosquitto_pub` med `{"sensor_id":"x"}` och med `inte json` | `Avvisade data` / `Ogiltig JSON` i loggen, mottagaren lever | |
| M-15.3 | #15 | `docker compose stop`, vänta 10 s, `docker compose start`, kör simulatorn | `Bortkopplad` sedan `Ansluten`, nya mätningar sparas | |
| M-15.4 | #15 | stoppa brokern, starta mottagaren, starta brokern | mottagaren väntar och ansluter, ingen krasch | |
| M-16.1 | #16 | brokern stoppad, kör simulatorn med `--count 1` | `Försök 1/5` ... `5/5` (1, 2, 4, 8 s), sedan `Gav upp ... förlorad` | |
| M-16.2 | #16 | kör simulatorn, stoppa brokern en stund mitt i, starta den igen | `Försök`-varningar, därefter `Skickade` igen utan omstart | |
| M-16.3 | #16 | skicka mot fel URL (`--transport http`, fel port) | `Avvisad (ingen retry): HTTP 404` | |
