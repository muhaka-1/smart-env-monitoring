# Smart Environmental Monitoring

Ett utbildningsprojekt som bygger ett lokalt, komplett IoT-dataflöde med **simulerad sensordata**:

```text
Öppet dataset -> Python-simulator -> valt IoT-protokoll -> Django -> SQLite -> REST-API -> dashboard
```

## Status

Projektet är i planeringsfas. Repositoriet innehåller ännu ingen körbar applikation. Dokumenterade komponenter och kataloger nedan är därför målbild, inte färdig funktionalitet.

## Uppgift och avgränsning

Projektunderlaget kräver:

- en simulerad IoT-enhet som läser data från ett öppet dataset,
- tidsstämplade meddelanden med sensor-ID som skickas periodiskt,
- felhantering i kommunikationen,
- en Django-backend som validerar och lagrar data,
- ett REST-API för senaste värde och historik,
- tidsserielagring med minst `sensor_id`, `timestamp`, `value` och `quality/status`,
- en publik dashboard med aktuellt värde, historik och status,
- lokal körbarhet, modulär kod, arkitekturdiagram och motiverade teknikval.

Projektet använder datasetet [Beach Water Quality - Automated Sensors](https://catalog.data.gov/dataset/beach-water-quality-automated-sensors) från City of Chicago.

### Inte krav för MVP

Följande kan utvärderas senare men ska inte blockera den första fungerande versionen:

- fysisk ESP32 eller verkliga sensorer,
- firmware/ESP-IDF och kalibrering av hårdvara,
- två parallella transportvägar,
- TimescaleDB, Redis, Grafana, Prometheus eller ELK/Loki,
- JWT för den publika dashboarden,
- produktions-TLS, ACL, nätverkssegmentering, OTA eller enhetshantering,
- WebSockets, notifieringar eller AI/ML-baserad avvikelsedetektering.

## Föreslagen MVP

1. **Simulator** - läser en vald del av CSV-datasetet, normaliserar en datapunkt och skickar den med konfigurerbart intervall.
2. **Kommunikation** - ett protokoll väljs och motiveras i ett teknikbeslut. Lösningen hanterar anslutningsfel, begränsade återförsök och tydlig loggning.
3. **Django-backend** - validerar obligatoriska fält och rimliga värden, beräknar projektets status och sparar giltiga mätningar.
4. **SQLite** - används lokalt med index för sensor och tid. En tyngre databas är en framtida skalbarhetsdiskussion, inte ett MVP-krav.
5. **REST-API** - returnerar senaste värde samt historik filtrerad på sensor och tidsintervall.
6. **Dashboard** - visar senaste värde, tidsstämpel, status i text och färg, historiskt diagram och begripliga felmeddelanden.

Exakt protokoll, mätvärde, JSON-schema och tröskel ska beslutas och dokumenteras innan implementationen delas upp mellan utvecklare.

## Definition av klart

MVP:n är klar när:

- en ren lokal installation kan startas med dokumenterade steg,
- simulerad data passerar hela kedjan utan manuella databasändringar,
- ogiltig data avvisas och kommunikationsfel loggas,
- senaste värde och filtrerad historik kan hämtas via API,
- dashboarden visar aktuell status och historik,
- automatiska tester täcker validering och de viktigaste API-flödena,
- arkitekturdiagram och teknikbeslut stämmer med den implementerade lösningen.

## Plan och backlog

Den granskade, korrigerade backlogplanen finns i [docs/BACKLOG_REVIEW.md](docs/BACKLOG_REVIEW.md). Den beskriver hur samtliga 35 issues och fem milstolpar bör behållas, ändras, slås ihop eller flyttas ut ur MVP:n.

Den beslutade sprintplanen, onsdagsleveranserna och ansvarsfördelningen för tre personer finns i [docs/SPRINT_PLAN.md](docs/SPRINT_PLAN.md).

Den responsiva dashboard-wireframen och dess API-underlag finns i [docs/dashboard-wireframe.md](docs/dashboard-wireframe.md). Den körbara prototypen kan öppnas lokalt via [docs/dashboard-wireframe.html](docs/dashboard-wireframe.html).

## Nuvarande struktur

```text
smart-env-monitoring/
├── README.md
└── docs/
    ├── BACKLOG_REVIEW.md
    ├── SPRINT_PLAN.md
    ├── pat_veckolagg.md
    └── sensorval.md
```

När implementationen börjar bör strukturen växa stegvis och bara visa mappar och filer som faktiskt finns.

## Lokal start

Det finns ännu ingen körbar applikation. Tills simulator och Django-projekt har lagts till består en lokal kontroll av att klona och läsa dokumentationen:

```bash
git clone https://github.com/muhaka-1/smart-env-monitoring.git
cd smart-env-monitoring
```

Installations- och testkommandon ska läggas till samtidigt som den första körbara koden, och verifieras på en ren dator.

## Arbetssätt

- Skapa en kortlivad branch per issue.
- Öppna en pull request mot `main`.
- Koppla PR:n till relevant issue och dokumentera hur acceptanskriterierna verifierades.
- Ändra inte `main` direkt.
- Stäng en issue först när dess verifierbara acceptanskriterier är uppfyllda.

## Licens

Ingen licens är vald ännu. Lägg till en faktisk licensfil innan en licensbadge eller återanvändningsvillkor publiceras.

