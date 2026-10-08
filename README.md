# Smart Environmental Monitoring – IoT Platform
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-green?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![ESP--IDF](https://img.shields.io/badge/ESP--IDF-5.2%2B-E7352C?logo=espressif&logoColor=white)](https://docs.espressif.com/projects/esp-idf/en/latest/)
[![MQTT](https://img.shields.io/badge/MQTT-QoS%201-purple)](https://mqtt.org/)
[![License](https://img.shields.io/badge/License-Educational-lightgrey)](#license)

An end-to-end IoT system for collecting, transmitting, storing, processing and visualizing environmental sensor data.

Projektet är uppbyggt kring **fem huvudmoduler**:

1. **Simulerad IoT-enhet (Sensor)**
2. **Datakommunikation**
3. **Backend / API**
4. **Databas – tidsseriedata**
5. **Frontend – Dashboard**

Målet är att demonstrera ett komplett IoT-dataflöde från en simulerad sensor till en webbaserad dashboard.

---

## Systemöversikt

```text
    ┌─────────────────────────────┐
    │ 1. SIMULERAD IoT-ENHET      │
    │                             │
    │ Python Sensor Simulator     │
    │ - Sensorvärden              │
    │ - Sensor ID                 │
    │ - Timestamp                 │
    │ - NTU / turbidity           │
    └──────────────┬──────────────┘
                   │
                   │ MQTT / HTTP
                   ▼
    ┌─────────────────────────────┐
    │ 2. DATAKOMMUNIKATION        │
    │                             │
    │ MQTT                         │
    │ Eclipse Mosquitto            │
    │ REST/HTTP                    │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │ 3. BACKEND / API            │
    │                             │
    │ Django                      │
    │ Django REST Framework       │
    │ MQTT Consumer               │
    │ Validation & Business Logic │
    └──────────────┬──────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │ 4. DATABAS                  │
    │    TIDSSERIEDATA            │
    │                             │
    │ SQLite                      │
    │ Sensor readings             │
    │ Timestamp                   │
    │ Value / Unit / Quality      │
    └──────────────┬──────────────┘
                   │
                   │ REST API
                   ▼
    ┌─────────────────────────────┐
    │ 5. FRONTEND / DASHBOARD     │
    │                             │
    │ HTML                        │
    │ Bootstrap                   │
    │ JavaScript                  │
    │ Chart.js                    │
    │                             │
    │ Live / historical data      │
    │ Sensor selection            │
    │ Charts & anomaly status     │
    └─────────────────────────────┘

#Project Structure
        smart-env-monitoring/
        │
        ├── backend/
        │   ├── config/
        │   ├── monitoring/
        │   │   ├── models.py
        │   │   ├── serializers.py
        │   │   ├── services.py
        │   │   ├── views.py
        │   │   ├── mqtt_consumer.py
        │   │   ├── management/
        │   │   │   └── commands/
        │   │   │       └── run_mqtt_consumer.py
        │   │   ├── templates/
        │   │   ├── static/
        │   │   └── tests/
        │   └── manage.py
        │
        ├── sensor/
        │   ├── sensor_sim/
        │   │   ├── config.py
        │   │   ├── data_source.py
        │   │   ├── message.py
        │   │   ├── publishers.py
        │   │   ├── simulator.py
        │   │   └── __main__.py
        │   ├── data/
        │   │   └── sample_readings.json
        │   └── tests/
        │
        ├── firmware/
        │   ├── main/
        │   ├── CMakeLists.txt
        │   └── sdkconfig.defaults
        │
        ├── infra/
        │   └── mosquitto.conf
        │
        ├── docs/
        │   ├── ARCHITECTURE.md
        │   └── api-requests.http
        │
        ├── docker-compose.yml
        ├── requirements.txt
        ├── .env.example
        └── README.md
```
## 1. Simulerad IoT-enhet – Sensor

Den första modulen representerar själva IoT-enheten.

I utvecklingsmiljön används en Python-baserad sensor simulator istället för fysisk hårdvara. Simulatorn genererar miljödata som representerar exempelvis turbidity/vattengrumlighet.

## Sensorfunktioner

Simulatorn kan:

      Generera sensorvärden
      Använda riktiga dataset som datakälla
      Använda lokal fallback-data
      Skapa timestamps
      Identifiera sensorn med sensor_id
      Skicka data via MQTT
      Skicka data via HTTP
      Hantera nätverksfel
      Retry:a transient errors
      Köra i offline-läge

Exempel på sensorvärde:

        {
          "sensor_id": "sensor-01-turbidity",
          "timestamp": "2026-10-08T08:30:00Z",
          "value": 12.4,
          "unit": "NTU",
          "quality": "good"
        }

### Sensor simulator

Exempel:

    cd sensor
    python -m sensor_sim --transport mqtt --interval 3

HTTP:

    python -m sensor_sim --transport http --interval 3

Offline:

      python -m sensor_sim --offline

Simulatorn kan därför användas för att testa hela IoT-systemet utan fysisk ESP32-hårdvara.

## 2. Datakommunikation

Datakommunikationsmodulen ansvarar för att transportera sensorinformationen från IoT-enheten till backend-systemet.

Projektet stödjer två kommunikationsvägar:

    Sensor
      │
      ├── MQTT ──► Mosquitto ──► Backend
      │
      └── HTTP ──► REST API ────► Backend
    MQTT

MQTT används som huvudsaklig IoT-kommunikation.

## Broker:

      Eclipse Mosquitto

## Standardport:

      1883

Topic:

    beach/{sensor_id}/readings

Backend prenumererar på:

      beach/+/readings

Exempel:

      beach/sensor-01-turbidity/readings
MQTT payload
      {
        "sensor_id": "sensor-01-turbidity",
        "timestamp": "2026-10-08T08:30:00Z",
        "value": 12.4,
        "unit": "NTU",
        "quality": "good"
      }

MQTT använder:

QoS 1

vilket ger at-least-once delivery.

Starta MQTT broker
    docker compose up -d

Kontrollera:

    docker compose ps

Stoppa:

      docker compose down

## HTTP

HTTP används som alternativ transport för exempelvis:

    API-testning
    Lokal utveckling
    Test utan MQTT broker
    Integrationstester

Exempel:

POST /api/readings/
      Content-Type: application/json
## 3. Backend / API

Backend-modulen är systemets centrala lager.

### Den ansvarar för:

      Ta emot sensorvärden
      Validera data
      Bearbeta data
      Klassificera sensorvärden
      Spara readings
      Exponera REST API
      Hantera MQTT-data
      Tillhandahålla health check

### Teknik:

    Python
    Django
    Django REST Framework
    Backend-arkitektur

              MQTT
                │
                ▼
       ┌─────────────────┐
       │ MQTT Consumer    │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ Service Layer    │
       │ Validation       │
       │ Business Logic   │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ Django Models    │
       └────────┬────────┘
                │
                ▼
             Database

## HTTP-flödet:
      
          HTTP Client
              │
              ▼
          Django REST API
              │
              ▼
          Serializer / Validation
              │
              ▼
          Service Layer
              │
              ▼
          Database

## Starta backend
    cd backend
    python manage.py migrate
    python manage.py runserver

### Backend:

      http://localhost:8000
      API-endpoints
      Health
      GET /api/health/

Exempel:

    {
      "status": "ok"
    }

### Sensors
       GET /api/sensors/
Latest readings
       GET /api/readings/latest/

### För en specifik sensor:

      GET /api/readings/latest/?sensor_id=sensor-01-turbidity
### Historical readings
      GET /api/readings/

Exempel:

      GET /api/readings/?sensor_id=sensor-01-turbidity&limit=100&order=desc

## Stödda filter:

Parameter	Beskrivning
sensor_id	Filtrera på sensor
start	Starttid
end	Sluttid
limit	Antal readings
order	asc eller desc
Create reading
POST /api/readings/

Payload:

{
  "sensor_id": "sensor-01-turbidity",
  "timestamp": "2026-10-08T08:30:00Z",
  "value": 12.4,
  "unit": "NTU",
  "quality": "good"
}
## 4. Databas – Tidsseriedata

Databasmodulen lagrar sensorvärden som tidsseriedata.

Teknik:

SQLite

Databasen innehåller historiska mätningar som kan användas för:

Realtidsvisning
Historiska grafer
Sensoranalys
Anomalidetektering
Filtrering per sensor
Filtrering per tidsintervall
Reading-modell
        Reading
        │
        ├── id
        ├── sensor_id
        ├── timestamp
        ├── value
        ├── unit
        ├── quality
        ├── status
        └── created_at

Exempel:

    sensor_id   : sensor-01-turbidity
    timestamp   : 2026-10-08 08:30:00
    value       : 12.4
    unit        : NTU
    quality     : good
    status      : OK
    Tidsserie

Data kan konceptuellt representeras:

    Time
     │
     ├── 08:00 → 8.4 NTU
     ├── 08:05 → 9.1 NTU
     ├── 08:10 → 11.2 NTU
     ├── 08:15 → 12.4 NTU
     └── 08:20 → 31.7 NTU  ← ANOMALY

Det gör databasen lämplig för att bygga historiska grafer och analysera förändringar över tid.

Duplicate protection

Systemet skyddar mot duplicerade mätningar genom en unik kombination av:

sensor_id + timestamp

Databasen använder även index för vanliga queries:

timestamp
sensor_id + timestamp
5. Frontend – Dashboard

Frontend-modulen visualiserar den data som finns i backend och databasen.

Teknik:

    HTML
    Bootstrap 5
    JavaScript
    Chart.js

Dashboarden kommunicerar med backend via REST API.

      ┌───────────────┐
      │   Dashboard   │
      └───────┬───────┘
              │ HTTP GET
              ▼
      ┌───────────────┐
      │ REST API      │
      └───────┬───────┘
              │
              ▼
      ┌───────────────┐
      │ SQLite        │
      └───────────────┘
Dashboardfunktioner

Dashboarden visar bland annat:

      Senaste sensorvärde
      Sensor-ID
      Sensorstatus
      Historiska mätningar
      Tidsseriediagram
      Sensorval
      Datum-/tidsfilter
      Anomalistatus
      Automatisk uppdatering

Dashboarden kan hämta nya värden med jämna intervall för att ge en nära realtidsliknande vy.

Komplett dataflöde

## Ett komplett scenario ser ut så här:

      1. Sensor Simulator
              │
              │ Sensor value
              ▼
      2. MQTT / HTTP
              │
              ▼
      3. Mosquitto / REST API
              │
              ▼
      4. Django Backend
              │
              │ Validation
              │ Business logic
              ▼
      5. SQLite Time-Series Database
              │
              │ REST API
              ▼
      6. Web Dashboard
              │
              ▼
         Visualization
      
  Exempel:
      
      Sensor
        │
        │ 12.4 NTU
        ▼
      MQTT
        │
        │ beach/sensor-01-turbidity/readings
        ▼
      Django MQTT Consumer
        │
        ▼
      Validation
        │
        ▼
      SQLite
        │
        ▼
      REST API
        │
        ▼
      Chart.js
        │
        ▼
      Dashboard
Anomaly Detection

Backend kan klassificera sensorvärden baserat på en konfigurerad tröskel.

Exempel:

ANOMALY_THRESHOLD=30

Då kan:

    12.4 NTU → OK
    18.7 NTU → OK
    29.8 NTU → OK
    35.2 NTU → ANOMALY

Detta gör det möjligt för dashboarden att tydligt visa avvikande mätningar.

Reliability

Systemet innehåller flera mekanismer för robust IoT-kommunikation.

Retry

Vid temporära kommunikationsfel används retry med exponential backoff:

1s
 ↓
2s
 ↓
4s
 ↓
8s

Permanenta HTTP-fel retry:as inte eftersom samma request förväntas misslyckas igen.

Offline fallback

Om extern datakälla inte är tillgänglig kan simulatorn använda lokal data:

sensor/data/sample_readings.json

Det gör att projektet fortfarande kan köras utan internetåtkomst till den externa datakällan.


Testing

Backend:

cd backend
python manage.py test

Sensor:

cd sensor
python -m unittest discover -s tests -t .

Tester omfattar bland annat API, validation, service logic, MQTT ingestion, simulator, publishing och retry behavior.

Technology Stack
Modul	Technology
1. Simulerad IoT-enhet	Python
2. Datakommunikation	MQTT, HTTP, Eclipse Mosquitto
3. Backend / API	Python, Django, Django REST Framework
4. Databas	SQLite, Time-Series Data
5. Frontend	HTML, Bootstrap 5, JavaScript, Chart.js
Infrastruktur	Docker Compose
Embedded extension	ESP32, ESP-IDF, FreeRTOS
Reliability

Systemet innehåller:

MQTT QoS 1
Retry vid transient errors
Exponential backoff
Offline fallback
Input validation
Duplicate protection
Database indexes
Health endpoint

Exempel på retry:

1s → 2s → 4s → 8s
Security

För lokal utveckling används en enkel MQTT-konfiguration.

För produktion bör systemet kompletteras med:

MQTT TLS
MQTT authentication
MQTT ACL
HTTPS
API authentication
Secret management
DEBUG=0
Network segmentation
Rate limiting
Centralized logging
Future Improvements
Riktig ESP32-sensor
PostgreSQL + TimescaleDB
Redis caching
MQTT TLS
JWT/API authentication
Dockerisering av hela stacken
Grafana/Prometheus
Sensor alarms
Notifications
Device management
OTA firmware updates
Development Workflow
feature/*
    ↓
integration / development
    ↓
testing
    ↓
main

Exempel:

    feat(sensor): add sensor simulator
    feat(mqtt): add MQTT publisher
    feat(api): add readings endpoint
    feat(database): add time-series reading model
    feat(dashboard): add monitoring chart
    fix(mqtt): retry transient errors
    test(api): add readings tests
    docs: update IoT architecture

##Project Summary

Detta projekt demonstrerar en komplett IoT-pipeline med fem tydliga moduler:

    #	          Modul	                      Huvudansvar
    1	    Simulerad IoT-enhet        	Generera sensorvärden
    2	    Datakommunikation	          Transportera data med MQTT/HTTP
    3	    Backend / API	              Validera, bearbeta och exponera data
    4	    Databas	                    Lagra tidsseriedata
    5	    Frontend	                  Visualisera data och anomalier

End-to-end:

Sensor → Communication → Backend/API → Time-Series Database → Dashboard
Author

Smart Environmental Monitoring – IoT Project

Technologies:

Python • IoT • MQTT • Django • REST API • SQLite • Time-Series Data • JavaScript • Bootstrap • Chart.js • Docker • ESP32 • ESP-IDF • FreeRTOS

