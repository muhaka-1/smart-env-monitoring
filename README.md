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

## Nya beslutade krav

Följande funktioner är implementerade i `development`:

- olika publika och inloggade vyer,
- en fortsatt publik sida för aktuella mätvärden,
- inloggning och utloggning för åtkomst till historik och meddelanden,
- serverbaserat skydd så att obehöriga inte kan läsa skyddade sidor eller API-data,
- glömt lösenord och byte av lösenord,
- administratörsskapade konton med e-postinbjudan som ska användas inom tre dagar och därefter kunna skickas om,
- nedladdning av historiska data som PDF,
- e-postvarningar vid upptäckta dataproblem samt sparade meddelanden för inloggade användare,
- felrapport på skärmen och som PDF.

Se [åtkomstkontroll](docs/access-control.md), [lösenord](docs/password.md), [inbjudningar](docs/invitations.md), [e-post](docs/email.md), [meddelanden](docs/notifications.md), [historik-PDF](docs/history-pdf.md) och [felrapporter](docs/error-reports.md) för detaljer och verifiering.

## Team och ansvar

| Person | Hittills genomfört | Fortsatt huvudansvar |
| --- | --- | --- |
| Pat | Projektplanering, issue- och sprintstruktur, sensorunderlag, wireframe, responsiv dashboard, dataset-/protokolldokumentation och demoarbete | Publik och skyddad dashboard, åtkomstkontroll för sidor och data, historik- och felrapporter samt PDF-export |
| Jubayer | Grundstruktur, simulator, datasetintegration, MQTT/HTTP, temperaturstöd och säker hantering av data i dashboard/API | Backend för autentisering, inloggning, utloggning, lösenordsflöden och administratörsskapade konton |
| Khaled | Backendgranskning, intervallvalidering, avvikelsestatus, dokumentationssynkronisering och release-/CI-arbete | E-posttjänst, kontoinbjudningar, datavarningar och sparade användarmeddelanden |

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

### 2. Konfigurera lokal miljö

Kopiera exempelkonfigurationen endast om `.env` inte redan finns. Behåll befintliga lokala uppgifter.

PowerShell:

```powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
```

macOS/Linux/Git Bash:

```bash
[ -e .env ] || cp .env.example .env
```

Fyll i SMTP-värd, port, inloggning, nyckel, TLS/SSL och verifierad avsändare enligt [e-postkonfigurationen](docs/email.md). SMTP är standard; exempelvärdena räcker inte för start. Sätt `PLATFORM_BASE_URL` till den adress där du öppnar plattformen. Lägg aldrig `.env` eller riktiga nycklar i Git.

För en **isolerad lokal verifiering utan utskick** kan processens `EMAIL_BACKEND` sättas till `django.core.mail.backends.locmem.EmailBackend` i varje backendterminal. Det är samma testbackend som i CI, inte verifiering av riktig e-postleverans. Se [ren end-to-end-start](docs/end-to-end.md) för ett komplett exempel utan SMTP-uppgifter.

### 3. Förbered databasen och valfri demohistorik

PowerShell:

```powershell
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py createsuperuser
.\.venv\Scripts\python.exe backend\manage.py seed_demo_data --repeat 2
```

`seed_demo_data` lägger till historik utan att radera befintliga mätningar. Flaggan `--clear` avvisas för att skydda data.

`createsuperuser` skapar ett lokalt testkonto interaktivt. Logga in för historik, meddelanden och rapporter; den publika sidan visar senaste värden. Admin kan bjuda in vanliga användare via [kontoinbjudningar](docs/invitations.md). Skapa inget nytt administratörskonto om du redan har ett.

### 4. Starta Django

```powershell
.\.venv\Scripts\python.exe backend\manage.py runserver
```

Öppna <http://127.0.0.1:8000/>. Hälsokontrollen finns på <http://127.0.0.1:8000/api/health/>.

### 5. Skicka simulerade mätningar

Öppna en andra terminal medan Django körs:

Om `INGEST_API_KEY` är satt i backendens `.env`, sätt samma värde som processvariabel i simulatorns terminal. Simulatorn läser inte `.env` automatiskt. Utan konfigurerad nyckel tillåts HTTP-inmatning lokalt utan nyckel.

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

Stoppa simulator, MQTT-mottagare och Django med `Ctrl+C`. Stoppa brokern med `docker compose stop`; starta om med `docker compose up -d` och starta sedan mottagare, Django och simulator igen. Befintlig databas behålls. Starta inte om med tom eller raderad databas; använd inte `--clear`. Simulatorn buffrar inte mätningar under längre avbrott, se [MQTT](docs/mqtt.md).

## API

| Metod | Sökväg | Syfte |
| --- | --- | --- |
| `GET` | `/api/health/` | Kontrollerar att backend och databas svarar |
| `GET` | `/api/sensors/` | Returnerar kända sensor-ID:n |
| `POST` | `/api/readings/` | Validerar och sparar en mätning |
| `GET` | `/api/readings/` | Returnerar historik med valfria filter; kräver inloggad session |
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

Django läser `.env` i projektroten automatiskt. Processens befintliga miljövariabler har företräde. [.env.example](.env.example) är en mall och läses inte direkt. Simulatorn läser endast processens miljövariabler; ange exempelvis `INGEST_API_KEY` och `MQTT_HOST` även i dess terminal när de avviker från standard.

| Variabel | Standard | Syfte |
| --- | ---: | --- |
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

Använd minnesbackend i testterminalen så att inga riktiga mejl skickas, även om `.env` innehåller SMTP-uppgifter. PowerShell:

```powershell
$env:EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe backend\manage.py test monitoring
Set-Location sensor
..\.venv\Scripts\python.exe -m unittest discover -s tests -t .
Set-Location ..
node backend\monitoring\tests\dashboard.test.cjs
```

I macOS/Linux/Git Bash används `export EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend` och `.venv/bin/python` (Git Bash på Windows: `.venv/Scripts/python.exe`) med samma argument. Avsluta testterminalen innan du återgår till riktig SMTP, eller ta bort processvariabeln.

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

- rätta och granska kvarvarande öppna pull requests innan nytt funktionsarbete påbörjas,
- verifiera säkerhet, e-postflöden och responsivitet med automatiska och manuella tester,
- verifiera en ren lokal installation och fortsätta dokumentera veckodemon.

Öppna issues och milstolpar är projektets källa för aktuell status. Arbetssätt, grenar och PR-regler finns i [CONTRIBUTING.md](CONTRIBUTING.md).

## Viktiga avgränsningar

- Projektet använder simulerade sensorer; fysisk sensor och driftsatt firmware krävs inte.
- SQLite är vald för den lokala MVP:n.
- Gränsvärdena är konfigurerbara projektvärden och ska dokumenteras som sådana.
- Dashboarden är ett demonstrations- och övervakningsgränssnitt, inte en officiell badvattenbedömning.
