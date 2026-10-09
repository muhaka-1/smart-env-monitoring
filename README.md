# Smart Environmental Monitoring – IoT Platform
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-green?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![ESP--IDF](https://img.shields.io/badge/ESP--IDF-5.2%2B-E7352C?logo=espressif&logoColor=white)](https://docs.espressif.com/projects/esp-idf/en/latest/)
[![MQTT](https://img.shields.io/badge/MQTT-QoS%201-purple)](https://mqtt.org/)
[![License](https://img.shields.io/badge/License-Educational-lightgrey)](#license)


## 📖 Bakgrund


En kommun vill övervaka miljödata, t.ex. badvattenkvalitet, för att:

        fatta faktabaserade beslut
        identifiera avvikelser och risker
        presentera information tydligt för verksamhet och allmänhet

Projektet simulerar ett verkligt IoT-flöde där en Python-baserad sensor skickar mätvärden (turbiditet i NTU) via MQTT eller HTTP till en Django-backend. Backend validerar, klassificerar och lagrar datan som tidsserier och exponerar den via ett REST-API som en Bootstrap/Chart.js-dashboard visualiserar.

## 🎯 Projektmål
Målet är att utveckla ett komplett IoT-dataflöde från en simulerad sensor till en webbaserad dashboard.

Systemet ska:

**Samla in simulerad sensordata**
        
**Skicka data med jämna intervall**
        
**Validara data, Lagra tidsseriedata**
        
**Exponera API för senaste och historiska värden**
        
**Visa dashboard med status, diagram och trender**

    “Backend ska exponera ett REST‑API… API ska möjliggöra hämtning av senaste mätvärde och historisk data.”


## 📌 Projektöversikt

För att nå projekten mål vi ska bygga en end-to-end IoT system for collecting, transmitting, storing, processing and visualizing environmental sensor data.

Projektet är uppbyggt kring **fem huvudmoduler**:

| Modul | Beskrivning |
| --- | --- |
| **1. ESP32‑sensor** | Fysisk turbidity‑sensor som mäter vattengrumlighet i NTU |
| **2. Datakommunikation** | MQTT (Mosquitto) eller HTTP för transport av mätdata |
| **3. Backend / API (Django)** | Validering, lagring, avvikelsedetektering, REST‑API |
| **4. Databas (SQLite)** | Tidsserielagring med index och duplicatskydd |
| **5. Frontend / Dashboard** | Visualisering av realtidsdata och historiska trender |




## Systemöversikt

```text

```

<img width="1024" height="1536" alt="Copilot_20261009_141719" src="https://github.com/user-attachments/assets/d0eb4e19-3965-4c23-9ba8-1f2101702a9f" />



# Project Structure

       smart-env-monitoring/
    │
    ├── backend/                                  # Django backend + REST API
    │   ├── config/                                # Django settings (DEBUG=0 i produktion)
    │   ├── monitoring/
    │   │   ├── models.py                          # Reading model (tidsseriedata)
    │   │   ├── serializers.py                     # API serializers
    │   │   ├── services.py                        # Business logic (anomaly detection)
    │   │   ├── views.py                           # REST API endpoints
    │   │   ├── mqtt_consumer.py                   # MQTT ingestion logic
    │   │   ├── management/commands/
    │   │   │   └── run_mqtt_consumer.py           # MQTT consumer command
    │   │   ├── templates/                         # Dashboard HTML
    │   │   ├── static/                            # CSS/JS assets
    │   │   └── tests/                             # Backend tests
    │   ├── secrets/                               # Secret management (produktion)
    │   ├── logging/                               # Centralized logging config (framtida)
    │   └── manage.py
    │
    ├── sensor/                                    # Python sensor simulator (fallback)
    │   ├── sensor_sim/
    │   │   ├── config.py
    │   │   ├── data_source.py
    │   │   ├── message.py
    │   │   ├── publishers.py
    │   │   ├── simulator.py
    │   │   └── __main__.py
    │   ├── data/sample_readings.json              # Offline fallback data
    │   └── tests/
    │
    ├── firmware/                                  # ESP32 firmware (ESP-IDF)
    │   ├── main/
    │   │   ├── main.c                             # Turbidity sensor firmware
    │   │   ├── wifi.c                             # WiFi setup
    │   │   ├── mqtt.c                             # MQTT publisher (TLS, Auth)
    │   │   ├── sensor.c                           # ADC turbidity logic
    │   │   ├── ota.c                              # OTA updates (framtida)
    │   │   └── device_mgmt.c                      # Device management (framtida)
    │   ├── CMakeLists.txt
    │   └── sdkconfig.defaults
    │
    ├── infra/                                     # Infrastructure configs
    │   ├── mosquitto.conf                         # MQTT broker config (TLS, ACL)
    │   ├── docker/                                # Dockerisering av hela stacken (framtida)
    │   │   ├── docker-compose.yml
    │   │   ├── nginx.conf                         # HTTPS reverse proxy (produktion)
    │   │   └── grafana-prometheus/                # Observability stack (framtida)
    │   └── network/                               # Network segmentation configs (produktion)
    │
    ├── docs/                                      # Documentation
    │   ├── ARCHITECTURE.md                        # System architecture
    │   ├── SECURITY.md                            # Produktionssäkerhet
    │   ├── FUTURE_IMPROVEMENTS.md                 # Skalbarhetsplan
    │   └── api-requests.http                      # API test collection
    │
    ├── scripts/                                   # Deployment scripts
    │   ├── deploy_prod.sh                         # Produktionsdeployment
    │   ├── init_timescaledb.sql                   # TimescaleDB setup (framtida)
    │   └── init_redis.sh                          # Redis setup (framtida)
    │
    ├── docker-compose.yml                         # Lokal MQTT + backend
    ├── requirements.txt                           # Python dependencies
    ├── .env.example                               # Environment variables template
    └── README.md                                  # Main documentation

```text
```
# 🔧 Teknologival 
Detta är vår fullständiga tekniskt ramverk som har vi använt för den projekten.

<img width="1024" height="1536" alt="Copilot_20261009_140145" src="https://github.com/user-attachments/assets/fcb58559-a6c2-4dc9-a7d3-f2aefad83991" />



## ⚙️ Systemmoduler – Smart Environmental Monitoring
### 1️⃣ IoT‑enhet – Sensor (ESP32 + Turbidity‑sensor)
Den fysiska IoT‑enheten mäter vattengrumlighet (NTU) och skickar data till backend.
I utvecklingsmiljön används en Python‑baserad sensor‑simulator som ersättning för hårdvaran.

Funktioner

        ADC‑mätning av turbidity (NTU)
        
        Sensor‑ID och tidsstämpel (UTC)
        
        Klassificering av kvalitet (good/moderate/bad)
        
        Publicering via MQTT (TLS, Auth, ACL)
        
        Alternativ transport via HTTP/REST
        
        Retry‑mekanism vid nätverksfel
        
        Offline‑läge med lokal fallback‑data
        
        OTA‑uppdateringar och device management (produktion)

Exempel på sensorvärde:

    json
    {
      "sensor_id": "esp32-turbidity-01",
      "timestamp": "2026-10-08T08:30:00Z",
      "value": 12.4,
      "unit": "NTU",
      "quality": "good"
    }
### 2️⃣ Datakommunikation
Transporterar sensordata till backend via säkra kanaler.

Teknik

    MQTT (Eclipse Mosquitto) – huvudprotokoll
    
    TLS‑kryptering
    
    Authentication & ACL
    
    QoS 1 (at‑least‑once delivery)
    
    Rate limiting (produktion)
    
    HTTP/REST – fallback för test och integration

Flöde:

    Sensor ──► MQTT ──► Mosquitto ──► Backend
    Sensor ──► HTTP ──► REST API ──► Backend
    
### 3️⃣ Backend / API (Django + DRF)
Systemets centrala lager för databehandling, validering och lagring.

Ansvar

    Ta emot sensorvärden via MQTT och HTTP
    
    Validera inkommande data
    
    Klassificera avvikelser (anomaly detection)
    
    Spara readings i tidsseriedatabas
    
    Exponera REST‑API
    
    Tillhandahålla health‑check
    
    Hantera autentisering och säkerhet

Teknik

    Python 3.11+
    
    Django 5.x
    
    Django REST Framework
    
    MQTT‑consumer (management command)
    
    Service layer för affärslogik
    
    JWT/API‑authentication
    
    Secret management
    
    DEBUG=0 i produktion
    
    Centralized logging (ELK / Grafana Loki)
    
    Network segmentation

Backend‑arkitektur:

    MQTT → Consumer → Service Layer → Django Models → Database
    HTTP → REST API → Serializer → Service Layer → Database
    
### 4️⃣ Databas – Tidsseriedata
Lagrar sensorvärden som tidsserier för analys och visualisering.

Teknik

    SQLite – lokal utveckling
    
    PostgreSQL + TimescaleDB – produktion
    
    Redis caching – snabb åtkomst till senaste värden
    
    Indexering: timestamp, sensor_id
    
    Duplicate protection: sensor_id + timestamp
    
    Retention policies och nedsampling (TimescaleDB)

Reading‑modell:

    Reading
    │
    ├── id
    ├── sensor_id
    ├── timestamp
    ├── value
    ├── unit
    ├── quality
    ├── status (OK / ANOMALY)
    └── created_at
    
### 5️⃣ Frontend – Dashboard
Visualiserar data från backend och databasen i ett användarvänligt gränssnitt.

Teknik

    HTML + Bootstrap 5
    
    JavaScript + Chart.js
    
    AJAX‑polling / WebSockets för realtidsuppdatering
    
    HTTPS för säker kommunikation
    
    Grafana/Prometheus för avancerad visualisering
    
    Notifieringar & larm (SMS, e‑post, Teams/Slack)

Dashboard‑flöde:

    Dashboard → REST API → SQLite / TimescaleDB → Visualisering
Funktioner

    Senaste sensorvärde
    
    Sensorstatus (OK / ANOMALY)
    
    Historiska mätningar
    
    Tidsseriediagram
    
    Sensorval och datumfilter
    
    Automatisk uppdatering
    
    Visuell markering av avvikelser

### 🔄 Komplett dataflöde:

      1. ESP32 / Sensor Simulator
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



# Testing

Backend:

    cd backend
    python manage.py test

Sensor:

    cd sensor
    python -m unittest discover -s tests -t .

Tester omfattar bland annat API, validation, service logic, MQTT ingestion, simulator, publishing och retry behavior.


## Development Workflow

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
    1	    Simulerad IoT-enhet           Generera sensorvärden
    2	    Datakommunikation	          Transportera data med MQTT/HTTP
    3	    Backend / API	              Validera, bearbeta och exponera data
    4	    Databas	                      Lagra tidsseriedata
    5	    Frontend	                  Visualisera data och anomalier

End-to-end:

Sensor → Communication → Backend/API → Time-Series Database → Dashboard
Author

Smart Environmental Monitoring – IoT Project

Technologies:

Python • IoT • MQTT • Django • REST API • SQLite • Time-Series Data • JavaScript • Bootstrap • Chart.js • Docker • ESP32 • ESP-IDF • FreeRTOS

