# Smart Environmental Monitoring

Ett utbildningsprojekt som demonstrerar ett lokalt IoT-dataflöde för badvattenmätningar. Projektet använder en Python-simulator som återspelar data från ett öppet dataset. Ingen fysisk sensor krävs för MVP:n.

```text
Öppet dataset → Python-simulator → MQTT eller HTTP → Django → SQLite → REST-API → dashboard
```

## Aktuell status

Följande delar finns och kan köras lokalt:

- simulator för turbiditet och vattentemperatur,
- MQTT som huvudtransport och HTTP som lokal testväg,
- validering och lagring av tidsstämplade mätningar i Django/SQLite,
- REST-API för hälsokontroll, sensorer, senaste värde och historik,
- statusen `OK` eller `ANOMALY` utifrån konfigurerbara projektgränser,
- responsiv dashboard med aktuella värden och historikdiagram,
- automatiska tester för backend, simulator, dashboard och migrationer.

Dashboardens status är en teknisk projektregel. Den avgör inte om vattnet är säkert att bada i. Standardvärdena 30 NTU och 25 °C är konfigurerbara demo-/projektgränser, inte officiella badvattenkrav.

## Team och ansvar

| Person | Hittills genomfört | Fortsatt huvudansvar |
|---|---|---|
| Pat | Projektplanering, issue- och sprintstruktur, sensorunderlag, wireframe, responsiv dashboard, dataset-/protokolldokumentation och demoarbete | Frontend, UX, dashboard, README och demosamordning |
| Muhammad | Grundstruktur, simulator, datasetintegration, kommunikationsdelar, temperaturstöd och säker hantering av data i dashboard/API | Simulator, MQTT, kommunikation, lokal start och end-to-end-flöde |
| Khaled | Backendgranskning, intervallvalidering, avvikelsestatus, dokumentationssynkronisering och release-/CI-arbete | Django, datamodell, validering, REST-API och backendtester |

En person är huvudansvarig för ett område, men teamet granskar och hjälper varandra. Aktuell issuefördelning finns i [sprintplanen](docs/SPRINT_PLAN.md).

## Krav

- Python 3.11 eller senare
- Node.js för dashboardtestet
- Docker endast om MQTT-flödet ska köras med den medföljande Mosquitto-konfigurationen

## Snabbstart med HTTP

HTTP-vägen är enklast för en lokal demonstration eftersom den inte kräver en MQTT-broker.

### 1. Skapa miljö och installera beroenden

PowerShell från projektets rot:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -r backend/requirements.txt
```

### 2. Förbered databasen och valfri demohistorik

PowerShell:

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py seed_demo_data --repeat 2
```

`seed_demo_data` lägger till historik utan att radera befintliga mätningar. Flaggan `--clear` avvisas för att skydda data.

### 3. Starta Django

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver
```

Öppna <http://127.0.0.1:8000/>. Hälsokontrollen finns på <http://127.0.0.1:8000/api/health/>.

### 4. Skicka simulerade mätningar

Öppna en andra terminal medan Django körs:

```powershell
Set-Location sensor
..\.venv\Scripts\python.exe -m sensor_sim --offline --transport http --count 10
```

Ta bort `--offline` för att försöka läsa det öppna datasetet. Om datakällan inte kan nås använder simulatorn sin lokala reservdata.

## Fullständigt MQTT-flöde

Starta den lokala brokern från projektets rot:

```powershell
docker compose up -d
```

Starta därefter tre processer i var sin terminal:

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver
```

```powershell
.\.venv\Scripts\python.exe backend\manage.py run_mqtt_consumer
```

```powershell
Set-Location sensor
..\.venv\Scripts\python.exe -m sensor_sim --offline --transport mqtt --count 10
```

MQTT använder topic-formatet `beach/<sensor_id>/readings` och QoS 1. Se [protokollbeslutet](docs/protocol-decision.md) för motiveringen.

## API

| Metod | Sökväg | Syfte |
|---|---|---|
| `GET` | `/api/health/` | Kontrollerar att backend och databas svarar |
| `GET` | `/api/sensors/` | Returnerar kända sensor-ID:n |
| `POST` | `/api/readings/` | Validerar och sparar en mätning |
| `GET` | `/api/readings/` | Returnerar historik med valfria filter |
| `GET` | `/api/readings/latest/` | Returnerar senaste värdet per sensor |

Exempel på en mätning:

```json
{
  "sensor_id": "oak-street-beach-turbidity",
  "metric": "turbidity",
  "timestamp": "2026-10-30T12:00:00Z",
  "value": 11.1,
  "unit": "NTU",
  "quality": "good"
}
```

Historik kan filtreras med `sensor_id`, `start`, `end`, `order` och `limit`. Färdiga manuella anrop finns i [docs/api-requests.http](docs/api-requests.http).

## Konfiguration

Django och simulatorn läser miljövariabler från den process där de startas. [.env.example](.env.example) visar vanliga värden, men filen läses inte automatiskt.

| Variabel | Standard | Syfte |
|---|---:|---|
| `ANOMALY_THRESHOLD_TURBIDITY` | `30` | Projektgräns i NTU |
| `ANOMALY_THRESHOLD_TEMPERATURE` | `25` | Projektgräns i °C |
| `READING_STALE_SECONDS` | `300` | Tid innan en mätning markeras som inaktuell |
| `INGEST_API_KEY` | tom | Valfri nyckel för POST via headern `X-API-Key` |
| `MQTT_HOST` | `localhost` | MQTT-broker |
| `MQTT_PORT` | `1883` | MQTT-port |
| `MQTT_SUBSCRIBE_TOPIC` | `beach/+/readings` | Topic som backend prenumererar på |
| `SENSOR_TRANSPORT` | `mqtt` | Simulatorns transport: `mqtt` eller `http` |
| `SENSOR_INTERVAL` | `5` | Sekunder mellan mätningar |

Exempel i PowerShell:

```powershell
$env:READING_STALE_SECONDS = "3600"
$env:ANOMALY_THRESHOLD_TURBIDITY = "30"
```

## Tester

Kör från projektets rot:

```powershell
.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe backend\manage.py test monitoring
Set-Location sensor
..\.venv\Scripts\python.exe -m unittest discover -s tests -t .
Set-Location ..
node backend\monitoring\tests\dashboard.test.cjs
```

CI kör samma kontroller för pull requests mot `development`, `Testing` och `main`.

## Projektstruktur

```text
backend/    Django, datamodell, REST-API, MQTT-konsument och dashboard
sensor/     Python-simulator, dataset/reservdata och simulatortester
docs/       Arkitektur, beslut, testunderlag, sprintplan och wireframe
infra/      Lokal Mosquitto-konfiguration
firmware/   Tidig ESP32-prototyp; ingår inte i MVP-kravet
```

## Nästa arbete

- slutföra MQTT-publicering, mottagning och end-to-end-verifiering,
- slutföra dashboardens diagram, tidsfilter och avvikelsemarkering,
- genomföra användartest på dator och mobil,
- verifiera en ren lokal installation,
- färdigställa arkitekturdiagram, teknikreflektion och slutdemo.

Öppna issues och milstolpar är projektets källa för aktuell status. Arbetssätt, grenar och PR-regler finns i [CONTRIBUTING.md](CONTRIBUTING.md).

## Viktiga avgränsningar

- Projektet använder simulerade sensorer; fysisk sensor och driftsatt firmware krävs inte.
- SQLite är vald för den lokala MVP:n.
- Gränsvärdena är konfigurerbara projektvärden och ska dokumenteras som sådana.
- Dashboarden är ett demonstrations- och övervakningsgränssnitt, inte en officiell badvattenbedömning.
