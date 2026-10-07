# Smart Environmental Monitoring Platform

End-to-end IoT-system: simulerad sensor → MQTT/HTTP → Django REST API → databas → dashboard.
Data: [Beach Water Quality – Automated Sensors](https://catalog.data.gov/dataset/beach-water-quality-automated-sensors) (turbiditet i NTU).

## Projektstruktur
```
backend/    Django (config/ + app monitoring/: models, services, views, mqtt_consumer, tests)
sensor/     Sensorsimulator (sensor_sim/: data_source, message, publishers, simulator, tests)
<<<<<<< HEAD
firmware/   ESP-IDF-firmware för riktig ESP32 (core 0/1, MQTT) - se firmware/README.md
=======
>>>>>>> 309d9750b177e1fb84201d1eeb64c828cf7f5bc9
docs/       ARCHITECTURE.md (diagram + teknikval), api-requests.http
infra/      Mosquitto-konfiguration (+ docker-compose.yml i rotmappen)
.vscode/    Debug-konfigurationer för varje modul
```

## Installation (VS Code)
Kräver Python 3.10+.
```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cd backend && python manage.py migrate && cd ..
```
Välj interpretern `.venv` i VS Code (Ctrl+Shift+P → *Python: Select Interpreter*).

## Kör
**Alternativ A – utan broker (enklast):** Run and Debug → **"Kör utan broker (HTTP)"**.
**Alternativ B – med MQTT:** starta broker (`docker compose up -d`, eller installera Mosquitto) → Run and Debug → **"Kör hela systemet (MQTT)"**.

Öppna sedan http://localhost:8000 (dashboard), http://localhost:8000/api/readings/latest/ (API) och /admin (skapa användare: `python manage.py createsuperuser`).

Manuellt i separata terminaler:
```bash
cd backend && python manage.py runserver
cd backend && python manage.py run_mqtt_consumer
cd sensor  && python -m sensor_sim --transport mqtt --interval 3      # eller --transport http --offline
```

## Testa modulerna
```bash
cd backend && python manage.py test                        # API, validering, status, MQTT-hantering
cd sensor  && python -m unittest discover -s tests -t .    # datakälla, retry, publishers
```
Eller använd launch-konfigurationerna **Tester: backend / Tester: sensor**. API kan provas med `docs/api-requests.http` (tillägget REST Client).

## API
| Metod | URL | Beskrivning |
|---|---|---|
| POST | `/api/readings/` | Ta emot mätning (201 / 400 vid felaktig data) |
| GET | `/api/readings/latest/?sensor_id=` | Senaste värde (utan sensor_id: senaste per sensor) |
| GET | `/api/readings/?sensor_id=&start=&end=&order=asc\|desc&limit=` | Historik, filtrerbar på tid |
| GET | `/api/sensors/` | Lista sensorer |
| GET | `/api/health/` | Hälsokontroll |

## Konfiguration (miljövariabler, se `.env.example`)
`ANOMALY_THRESHOLD` (standard 30 NTU), `INGEST_API_KEY`, `MQTT_HOST/PORT`, `SENSOR_INTERVAL`, `SENSOR_TRANSPORT`, `SENSOR_DATASET_URL`, `SENSOR_MAX_RETRIES`.

## Noter
- Sensorn försöker hämta live-data från datasetet (Socrata-URL i `sensor/sensor_sim/config.py`). Misslyckas det används `sensor/data/sample_readings.json` automatiskt; `--offline` tvingar sample.
- Dashboarden laddar Bootstrap/Chart.js från CDN (webbläsaren behöver internet för styling/diagram); backend kräver inga molntjänster.
- Git: `git init && git add . && git commit -m "Initial commit"` – gör gärna små, beskrivande commits per modul.
