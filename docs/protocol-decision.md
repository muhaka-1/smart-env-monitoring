# Beslut om IoT-protokoll

- **Status:** Beslutat
- **Datum:** 2026-10-29
- **Omfattning:** Simulerad sensor till Django-backend

## Beslut

Projektet använder **MQTT som huvudprotokoll** för mätdata. **HTTP behålls som lokal fallback och testväg**.

Beslutet gäller MVP:n med Python-simulator. Fysisk sensor, ESP32 och firmware ingår inte.

## Jämförelse mot projektets krav

| Krav | MQTT | HTTP |
|---|---|---|
| Periodisk överföring av små IoT-meddelanden | Låg overhead och byggt för återkommande publicering | Fungerar, men en ny request görs för varje mätning |
| Lös koppling mellan simulator och backend | Broker kopplar isär producent och konsument | Simulatorn anropar backend direkt |
| Leveranssäkerhet | QoS 1 ger minst-en-gång-leverans | Kräver egen retry; statuskod visar resultatet direkt |
| Flera sensorer | Topic-strukturen `beach/<sensor_id>/readings` skalar naturligt | Fungerar via samma endpoint men saknar topic-baserad routing |
| Enkel lokal felsökning | Kräver att Mosquitto och MQTT-konsumenten körs | Enklast att prova med enbart Django-servern |
| Validering och felmeddelanden | Fel loggas av MQTT-konsumenten | HTTP 400/401/5xx returneras direkt till simulatorn |
| Projektets IoT-karaktär | Tydligt publish/subscribe-flöde | Användbar reservväg men mindre representativ för IoT-flödet |

## Motivering

MQTT väljs eftersom projektet ska demonstrera ett komplett IoT-flöde med periodiska meddelanden, flera sensor-ID:n, återanslutning och minst-en-gång-leverans. QoS 1 kombineras med databasens unika regel för `sensor_id` och `timestamp`, så en eventuell dubblett sparas inte två gånger.

HTTP behålls eftersom det gör lokal utveckling och API-testning möjlig utan broker. Båda transporterna skickar samma JSON-format och använder samma validering och lagring i backend.

## Dataflöde

```text
Öppet dataset
      ↓
Python-simulator
      ↓ MQTT, QoS 1
Mosquitto
      ↓
Django MQTT-konsument
      ↓
Gemensam validering → SQLite → REST-API → dashboard

Fallback för lokal test:
Python-simulator → HTTP POST /api/readings/ → gemensam validering
```

## Konsekvenser

### Simulator

- Standardtransporten är `mqtt`.
- Transport kan bytas till HTTP med `--transport http` eller `SENSOR_TRANSPORT=http`.
- Tillfälliga fel försöks om med exponentiell väntetid. HTTP 4xx betraktas som permanent avvisning.
- Samma meddelandemodell används oavsett transport.

### Backend

- MQTT kräver en körande broker och kommandot `python manage.py run_mqtt_consumer`.
- HTTP-ingest finns kvar på `POST /api/readings/`.
- MQTT och HTTP går genom samma service- och valideringslogik innan data sparas.
- Dashboarden läser data via REST-API oberoende av hur mätningen kom in.

### Lokal körning

- Fullständigt MVP-flöde: Django, Mosquitto, MQTT-konsument och simulator.
- Snabb API-test utan broker: Django och simulator med `--transport http`.
- Om MQTT är otillgängligt loggar simulatorn felet och använder sin retry-strategi; den byter inte automatiskt protokoll.

## Omprövning

Beslutet bör omprövas om projektet senare kräver drift utan broker, synkrona svar för varje mätning eller en miljö där endast HTTPS är tillåtet. För nuvarande utbildningsprojekt ger MQTT huvudflödet och HTTP reservvägen bäst täckning av kraven.
