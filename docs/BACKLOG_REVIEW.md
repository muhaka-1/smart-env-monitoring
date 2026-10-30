# Backloggranskning mot projektunderlaget

Granskad: 2026-10-23  
Omfattning: README, samtliga 35 issues och fem milstolpar, inklusive kontroll av stängda objekt.

## Sammanfattning

GitHub-backloggen täcker nästan alla krav i projektunderlaget, men den beskriver ett betydligt större system än uppgiften kräver. Den viktigaste korrigeringen är att projektet ska använda en **simulerad sensor som läser det angivna öppna datasetet**. Fysisk sensor, ESP32 och firmware är inte del av den obligatoriska MVP:n.

Vid granskningen var:

- 35 av 35 issues öppna och 0 stängda,
- fem av fem milstolpar öppna,
- inga issues märkta med labels,
- Sprint 0 försenad och Sprint 1 på sin slutdag,
- repot fortfarande dokumentationsbaserat utan körbar implementation.

Ändra inte alla objekt samtidigt. Börja med scope, kontrakt och en tunn end-to-end-kedja. Uppdatera sedan issue-texterna och milstolparna i GitHub efter gemensamt beslut.

## Källhierarki

1. Projektunderlaget styr obligatorisk omfattning.
2. Gemensamma, dokumenterade teknikbeslut styr hur kraven löses.
3. README och issues ska spegla besluten och den faktiska implementationen.
4. Framtidsidéer ska märkas som valfria och får inte se ut som redan byggda funktioner.

## Rekommenderad arbetsordning

### Beslutsgrind

Färdigställ #3-#6 först: dataset, protokoll, datamodell och API-kontrakt. Välj en enda ordinarie transportväg för MVP:n. Definiera även vilket mätvärde som används, hur `quality/status` beräknas och vilka värden som är ogiltiga.

### Tunn vertikal kedja

Bygg därefter minsta fungerande flöde: en datapunkt från simulatorn till SQLite och tillbaka via API. Prioritera #7, #9-#12, #14/#15 och #17-#19. Lägg tester nära varje del, inte sist.

### Dashboard

När API-kontraktet är stabilt genomförs #22-#27. Ett responsivt gränssnitt räcker; tre separata implementationer för de tre personas krävs inte.

### Kvalitet och överlämning

Avsluta med #29-#34: reproducerbar lokal start, README, diagram, teknikreflektion, kodgranskning och demo.

## Granskning av samtliga issues

| Issue | Rekommenderad åtgärd | Konkret korrigering |
|---|---|---|
| #1 Skapa repo och grundstruktur | Behåll, skriv om | Kontrollera verklig struktur, `.gitignore`, PR-flöde och eventuell branch protection. Ta bort krav på tomma mappar; skapa mappar när kod tillkommer. |
| #2 Projekttavla, labels och milstolpar | Behåll, uppdatera | Ändra 34 till 35 issues. Skapa och applicera labels; vid granskningen hade alla issues tom labellista. Rebasera sprintdatum efter verklig start. |
| #3 Utforska datasetet | Behåll, högsta prioritet | Dokumentera kolumner, enheter, tidsluckor, avvikande värden och vald mätserie från Chicago-datasetet. Ingen fysisk sensor ska väljas här. |
| #4 Beslut: IoT-protokoll | Behåll, högsta prioritet | Jämför minst två alternativ men välj en ordinarie MVP-väg. Dokumentera varför valet uppfyller lokal körbarhet och felhantering. |
| #5 Beslut: databas och datamodell | Behåll, högsta prioritet | SQLite räcker för MVP. Dokumentera index och modell; TimescaleDB/Redis flyttas till skalbarhetsreflektion. |
| #6 API-kontrakt | Behåll, högsta prioritet | Frys JSON-schema, valideringsregler, felkoder, senaste-värde-endpoint och historikfilter innan parallell implementation. |
| #7 Django-projekt som startar | Behåll | Lägg till minsta Django-projekt, låsta beroenden, health check/startsida och verifierade startkommandon. |
| #8 Wireframes för dashboarden | Förenkla | Gör ett responsivt dashboardflöde som tillgodoser tre personas. Tre separata skisser är användbart men inte ett krav i underlaget. |
| #9 Sensorn läser datasetet | Behåll | Kalla komponenten simulator, läs vald CSV-serie och gör fil-/URL-källan konfigurerbar. |
| #10 Tidsstämpel och sensor-ID | Behåll | Använd ISO 8601 med tidszon och dokumentera skillnaden mellan datasetets ursprungstid och simulatorns aktuella sändningstid. |
| #11 Periodisk sändning och loggning | Behåll | Konfigurerbart intervall, kontrollerat stopp, ett uttalat slutbeteende och strukturerad loggning. |
| #12 Datamodell och migrering | Behåll | Lägg index på sensor + tid och besluta duplicatskydd. Adminstöd är bra men sekundärt till migrering och test. |
| #13 Gränsvärden för avvikelse | Behåll, precisera | Tröskeln måste vara spårbar och får inte beskrivas som officiell badsäkerhet om vald mätserie inte stöder det. |
| #14 Broker och publicering | Villkorad | Behåll brokerkravet endast om #4 väljer MQTT. Vid annat protokoll ska titel och kriterier följa beslutet. |
| #15 Mottagare som för data till backend | Slå ihop eller skriv om | En separat relätjänst krävs inte av underlaget. Placera mottagaren modulärt där den ger minst dubblerad validering, eller slå ihop med #14/#17. |
| #16 Felhantering i kommunikationen | Behåll | Specificera begränsade retries/backoff, vilka fel som inte ska återförsökas och hur resultatet verifieras. |
| #17 POST med validering | Behåll | Testa obligatoriska fält, typer, intervall och begripligt HTTP 400-svar. Återanvänd samma valideringslogik för all ingestion. |
| #18 Hämta senaste mätvärdet | Behåll | Definiera beteende utan data och vid flera sensor-ID:n. |
| #19 Hämta historisk data | Behåll | Datumfilter, sensorfilter, stabil sortering, radgräns/paginering och 400 vid ogiltiga parametrar. |
| #20 Automatiska tester för API:t | Behåll | Kör i CI när första testbara kod finns. Lägg även test för tom databas och dubblett. |
| #21 Hela kedjan fungerar | Behåll, skriv om | Kräv reproducerbar lokal körning från ren klon. Körning på båda utvecklarnas datorer är bra verifiering men inte ett separat projektkrav. |
| #22 Grundlayout från wireframen | Behåll | Responsiv och publik vy. Offlinekopior av bibliotek är valfritt så länge hela systemet kan köras lokalt och beroenden dokumenteras. |
| #23 Aktuellt värde och status | Behåll | Visa värde, enhet, tidsstämpel och status med både text och färg. Definiera stale/ingen data. |
| #24 Automatisk uppdatering | Behåll | Polling räcker för MVP. Visa senaste lyckade hämtning och hantera serverfel utan att rensa senast kända värde. |
| #25 Historiskt linjediagram | Behåll | Korrekt tidsskala, enhet, tomt läge och rimligt antal punkter. |
| #26 Filter på tidsintervall | Behåll | Börja med givna intervall och sensor. Eget datumintervall kan komma efter fungerande grundflöde. |
| #27 Avvikelser markerade | Behåll, precisera | Visa regel och tröskel. Kalla resultatet projektets avvikelse, inte officiell badvattenklassificering. |
| #28 Användartest | Valfri förstärkning | Bra LIA- och UX-material men inte ett uttryckligt systemkrav. Genomför när dashboarden är stabil; låt inte detta blockera MVP. |
| #29 Enkel lokal start | Behåll, hög prioritet sent i flödet | Ett dokumenterat kommando eller få steg, `.env.example` utan hemligheter och inga obligatoriska molntjänster. |
| #30 README och ren installation | Behåll | README ska beskriva vad som faktiskt finns. Testa instruktionerna på ren miljö; lägg endast till OS-stöd som teamet kan verifiera. |
| #31 Arkitekturdiagram | Behåll | Diagrammet ska följa implementerade komponentnamn, visa protokoll/dataformat och markera var validering/felhantering sker. |
| #32 Teknikval och skalbarhet | Behåll | Samla besluten från #4, #5 och #13. Beskriv skalning som reflektion, inte som krav på att införa produktionsstacken. |
| #33 Kodgranskning och städning | Behåll | Ta bort död kod och hårdkodning, kör formattering/lint/test och kontrollera att båda kan förklara lösningen. |
| #34 Demo för handledaren | Behåll | Visa kravspårbar end-to-end-demo och ett kontrollerat fel. Dokumentera feedback och beslut efter mötet. |
| #35 Sensor val | Stäng som ej planerad | Fysisk sensor krävs inte. Bevara researchen som framtidsmaterial men köp eller implementera inte hårdvara inom nuvarande MVP. |

## Milstolpar

Alla fem befintliga milstolpar kan behållas, men deras innehåll och datum behöver rebaseras. Uppdatera dem först när gruppen har bestämt en realistisk ny startpunkt.

| Milstolpe | Nuvarande problem | Föreslagen klar-definition |
|---|---|---|
| Sprint 0 - Uppstart och beslut | 9 öppna, 0 stängda; förfallet datum | #1-#7 klara, verklig repo-struktur, låst schema/protokoll/datamodell och startande Django. |
| Sprint 1 - Simulator och datamodell | 5 öppna, 0 stängda; slutdag vid granskning | Simulatorn producerar kontraktsenlig data och en giltig datapunkt kan sparas och läsas tillbaka. Ta bort fysisk hårdvara ur formuleringen. |
| Sprint 2 - Kommunikation och API | 8 öppna, 0 stängda | En datapunkt går hela vägen; felaktig data stoppas; senaste värde och historik fungerar och testas. |
| Sprint 3 - Dashboard | 7 öppna, 0 stängda | Dashboarden visar senaste värde, status, historik, filter och fel-/tomlägen. |
| Sprint 4 - Kvalitet, dokumentation och demo | 6 öppna, 0 stängda | Ren lokal installation, gröna tester, korrekt README/diagram/teknikval och genomförd demo. |

## Föreslagna labels

Minsta användbara uppsättning:

- område: `setup`, `simulator`, `communication`, `backend`, `frontend`, `docs`
- typ: `feature`, `bug`, `decision`, `test`
- prioritet: `P0`, `P1`, `P2`
- statusmarkörer vid behov: `blocked`, `needs-decision`

Undvik att använda både issue-nummer i titeln och GitHubs egna nummer som enda sorteringsmetod. Projektvyn och milstolparna ska bära ordningen.

## Ändringar som bör göras i GitHub efter granskning

1. Stäng #35 med en kommentar som hänvisar till simulator-kravet och behåller hårdvaruresearchen som framtida arbete.
2. Redigera #2 från 34 till 35 issues och applicera labels.
3. Revidera #8, #14, #15, #21, #22, #28 och milstolpe 2 enligt tabellerna ovan.
4. Flytta allt som gäller fysisk sensor, ESP-IDF och produktionstjänster till en tydligt märkt framtidslista.
5. Sätt nya milstolpsdatum först när teamet har uppskattat återstående arbete och ägarskap.
6. Stäng varje issue först efter verifiering av dess kriterier; stäng inte backloggen administrativt bara för att datumen har passerat.


