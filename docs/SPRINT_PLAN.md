# Sprintplan och ansvarsfördelning

Planen gäller från 2026-10-23. Sprintarna avslutas på onsdagar så att resultatet kan visas vid handledarmötet.

## Roller

| Roll | Huvudområde | Ansvar |
|---|---|---|
| Person 1 | Backend och databas | Django, datamodell, validering, REST-API och backendtester |
| Person 2 | Simulator och kommunikation | Dataset, simulator, MQTT, mottagare, felhantering och lokal start |
| Person 3 | Frontend, UX och dokumentation | Wireframe, dashboard, diagram, filter, README och demosamordning |

Varje issue har en huvudansvarig. Vid integrations-, kvalitets- och demouppgifter arbetar alla tre tillsammans.

## Milstolpar

| Sprint | Slutdatum | Mål | Demonstration |
|---|---:|---|---|
| Sprint 0 - Scope, beslut och första körbara delar | 2026-10-28 | Avgränsning, datasetanalys, teknikbeslut, JSON/API-kontrakt, startande Django, enkel simulator och wireframe | Django startsida/health check, simulator som skriver normaliserad JSON, API-kontrakt och wireframe |
| Sprint 1 - Simulator, datamodell och ingestion | 2026-11-04 | Periodisk simulator, Django-modell/migrering, tröskelregel och validerad POST-endpoint | En simulerad datapunkt sparas i SQLite och syns i Django admin |
| Sprint 2 - Kommunikation och läs-API | 2026-11-11 | MQTT, mottagare, felhantering, senaste värde, historik och automatiska API-tester | Komplett flöde från simulator till databas och tillbaka via API |
| Sprint 3 - Dashboard | 2026-11-18 | Responsiv dashboard med aktuellt värde, historik, filter, automatisk uppdatering och avvikelsemarkering | Användaren kan förstå aktuell status och historik utan att öppna admin |
| Sprint 4 - Kvalitet, dokumentation och demo | 2026-11-25 | Reproducerbar lokal start, korrekt README, arkitekturdiagram, teknikreflektion, kodgranskning och slutdemo | Ren installation, gröna tester och en sammanhängande end-to-end-demo |

## Leverans onsdag 2026-10-28

Målet är inte ett färdigt system. Målet är att visa tre konkreta delar som senare kan kopplas ihop.

### Person 1 - Backend och databas

- Starta ett minimalt Django-projekt.
- Lägg till en health check eller enkel startsida.
- Skissa modellen `Reading`.
- Ta fram första versionen av POST-, latest- och history-kontraktet.
- Visa: Django startar lokalt och endpoint-strukturen är dokumenterad.

### Person 2 - Simulator och kommunikation

- Ladda ned och analysera CSV-datasetet.
- Välj en strand/sensorplats och ett mätvärde.
- Implementera en första simulator som läser minst 20 rader.
- Normalisera raderna till det beslutade JSON-formatet.
- Visa: simulatorn skriver flera giltiga JSON-meddelanden med sensor-ID och aktuell tidsstämpel.

### Person 3 - Frontend, UX och dokumentation

- Uppdatera GitHub-tavla, labels och milstolpar.
- Skapa en enkel wireframe för en responsiv dashboard.
- Definiera vyerna för senaste värde, status, historik och fel/tomt läge.
- Säkerställ att README beskriver simulerad sensor och verklig repostatus.
- Visa: wireframe och en tydlig genomgång av användarflödet.

### Gemensamt före mötet

- Frys JSON-formatet.
- Fatta och dokumentera protokollbeslutet.
- Bestäm vad `OK`, `ANOMALY`, `valid` och `invalid` betyder.
- Genomför en 10-minuters intern repetition.
- Förbered tre frågor till handledaren: protokollval, tröskelregel och förväntad detaljnivå i demon.

## Issuefördelning

| Person | Issues | Kommentar |
|---|---|---|
| Person 1 | #5, #6, #7, #12, #13, #17, #18, #19, #20, #32, #33 | Leder backend, data och testbarhet |
| Person 2 | #3, #4, #9, #10, #11, #14, #15, #16, #21, #29, #31, #35 | Leder datakälla, transport och integration; #35 stängs som ej planerad |
| Person 3 | #1, #2, #8, #22, #23, #24, #25, #26, #27, #28, #30, #34 | Leder användarupplevelse, dokumentation och demo |

## Gemensamma kvalitetsregler

- En issue stängs först när dess checklista är verifierad.
- Varje pull request kopplas till en issue.
- README får endast beskriva funktioner och filer som faktiskt finns.
- Fysisk sensor, ESP32 och firmware ska inte blockera MVP:n.
- Projektets `OK/ANOMALY` får inte presenteras som officiell badvattenklassificering.
- Varje onsdagsdemo ska kunna köras lokalt utan manuella databasändringar.
