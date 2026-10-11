# Sensorval och rekommenderad omfattning

**Projekt:** smart-env-monitoring  
**Målplattform:** ESP32-S3  
**Dokumentdatum:** 2026-10-11  
**Status:** Beslutsunderlag - inte en ändring av GitHub-repot

## Kort beslut

### Rekommenderad MVP

1. **Vattentemperatur:** vattentät **DS18B20**.
2. **Grumlighet:** **DFRobot SEN0189**, men endast som prototypsensor för trend och avvikelse.
3. **Kommunikation:** MQTT som enda ordinarie väg i MVP:n.
4. **Backend:** Django/Django REST Framework.
5. **Databas:** SQLite med en generell mätvärdestabell och spårbar kalibrering.
6. **Dashboard:** senaste värden, historik, mätkvalitet, kalibreringsstatus och tydligt separerad jämförelse med öppna data.
7. **Simulerad sensor:** behålls för att backend och dashboard ska kunna utvecklas innan hårdvaran är stabil.

### Vänta med eller välj bort

- **pH:** vänta till fas 2. Kräver regelbunden tvåpunktskalibrering, korrekt förvaring och mer underhåll.
- **EC:** vänta till fas 2. Dyrare, temperaturberoende och kräver kalibreringslösningar samt säkrare analog anslutning.
- **TDS som separat sensor:** välj bort. Den överlappar EC, tillför en beräknad proxy och saknar tydlig koppling till det aktuella öppna badvattendatasetet.
- **Syrehalt, ORP, klorofyll/blågröna alger och laboratoriemätning av bakterier:** inte MVP. De innebär högre kostnad, mer specialiserad kalibrering eller laboratoriearbete.
- **Produktionsfunktioner** som OTA, TimescaleDB, Redis, Grafana/Prometheus, fullständig TLS/ACL-hantering och notifieringar: planera som framtida arbete.

> **Viktig begränsning:** Turbiditet/grumlighet visar mängden ljusspridande partiklar. Den visar inte om badvattnet är mikrobiologiskt säkert. Badvattensäkerhet bedöms bland annat genom laboratorieanalys av *E. coli* och intestinala enterokocker samt information om exempelvis algblomning och avrådan från bad. Dashboarden får därför aldrig kalla vattnet "säkert", "tjänligt" eller "otjänligt" enbart utifrån turbiditet, temperatur, pH, EC eller TDS.

## Hur dokumentet ska läsas

Följande markeringar används för att undvika att blanda ihop plan och rekommendation:

- **[README-plan]** = står i eller följer direkt av projektets README.
- **[Förslag]** = rekommendation i detta dokument och ännu inte ett fattat gruppbeslut.
- **[Framtid]** = kan vara värdefullt senare men ska inte blockera MVP:n.

## 1. Vad som redan finns i README-planen

**[README-plan]** Projektet beskriver ett komplett flöde för miljödata:

```text
ESP32 eller simulator
        -> MQTT eller HTTP
        -> Django-backend
        -> SQLite
        -> REST-API
        -> Bootstrap/Chart.js-dashboard
```

**[README-plan]** Den fysiska mätningen är en turbidity-sensor som ska ge turbiditet i NTU. Systemet ska validera, klassificera, lagra och visualisera mätningar. README:n nämner bland annat:

- sensor-ID och UTC-tidsstämpel,
- kvalitet `good/moderate/bad`,
- status `OK/ANOMALY`,
- MQTT med QoS 1, TLS, autentisering och ACL,
- HTTP/REST som alternativ transport,
- indexering på tid och sensor-ID,
- duplicatskydd på sensor-ID och tidsstämpel,
- senaste värde, historik, diagram, filter och avvikelsemarkering,
- Python-baserad simulator som reserv när hårdvara saknas.

**[README-plan]** README:n beskriver också en större framtida produktionsmiljö med PostgreSQL/TimescaleDB, Redis, Docker, Nginx, Grafana/Prometheus, central loggning, notifieringar, OTA och enhetshantering.

**Bedömning:** README:n är i första hand en målbild. Vid granskningen innehöll repot bara README:n och en kort mall för veckologg. Den uppräknade katalogstrukturen och funktionerna ska därför behandlas som **planerade**, inte som redan implementerade eller testade.

## 2. Sensorvalskriterier

Sensorerna har bedömts utifrån:

1. kompatibilitet med ESP32-S3,
2. elektrisk risk för 3,3 V-logik och ADC,
3. kalibrering och löpande underhåll,
4. kostnad och tillgång till förbrukningsmaterial,
5. hur lätt resultatet är att förklara och demonstrera,
6. koppling till Havs- och vattenmyndighetens öppna badvattendata,
7. om sensorn hjälper gruppen att visa ett komplett IoT-flöde inom LIA-tiden.

Tillverkarpriser nedan är ungefärliga listpriser i USD den 2026-10-11, exklusive moms, frakt och svensk återförsäljares påslag. De används för relativ jämförelse, inte som inköpspris.

## 3. Jämförelse och beslut

| Sensor/parameter | Teknik och ESP32-S3 | Kalibrering och underhåll | Relativ kostnad | Koppling till öppna data | Beslut |
|---|---|---|---:|---|---|
| **DS18B20, vattentemperatur** | Digital 1-Wire, 3-5,5 V. Kräver normalt 4,7 kOhm pull-up till 3,3 V. Ingen ADC behövs. | Enkel rimlighetskontroll mot referenstermometer. Välj färdig vattentät prob. | Låg, cirka 6,90 USD | Temperatur mäts vid badvattenprovtagning och kustbad kan ha temperaturprognoser i HaV:s API. | **Välj i MVP** |
| **SEN0189, turbiditet** | Drivs med 5 V. Analog utgång kan vara 0-4,5 V och får inte kopplas direkt till ESP32-S3:s ADC. Kräver spänningsdelare eller extern ADC/signalomvandling. | Behöver noll-/referenspunkter, stabil provgeometri, rengöring och lagring av råspänning. Den enkla proben är inte lämplig för permanent oskyddad utomhusinstallation. | Låg, cirka 9,90 USD | Turbiditet ingår inte i de listade parametrarna i HaV:s öppna badvatten-API. Endast indirekt jämförelse med händelser, alginformation och avrådan. | **Välj i MVP som trend-/demonstrationssensor** |
| **SEN0161-V2, pH** | 3,3-5,5 V matning och 0-3,0 V analog utgång. Kan mätas av ADC1 med rätt attenuation och kalibrering; extern ADC ger bättre reproducerbarhet. | Tvåpunktskalibrering, pH 4 och 7, rekommenderas. Glasproben måste hållas ren och förvaras rätt. Labproben driver vid långvarig mätning och är inte avsedd för permanent nedsänkning. | Medel, cirka 39,50 USD plus buffert/förvaring | pH finns inte bland de listade kärnparametrarna i HaV:s badvatten-API. | **Fas 2, inte MVP** |
| **DFR0300, EC** | 3-5 V matning, analog utgång upp till 3,4 V. Använd spänningsdelare/externt ADC-steg; direkt anslutning ger för liten eller ingen marginal mot ADC-området. | Tvåpunktskalibrering och temperaturkompensation. Proben ska sköljas och labversionen är inte avsedd för ständig nedsänkning. | Hög, cirka 69,90 USD plus lösningar | EC finns inte bland de listade kärnparametrarna i HaV:s badvatten-API. | **Fas 2 endast om gruppen har en tydlig fråga om ledningsförmåga/salthalt** |
| **SEN0244, TDS** | 3,3-5,5 V matning, 0-2,3 V analog utgång och temperaturkompensation bör användas. | Kräver kalibrering. Visar en uppskattad mängd lösta ämnen, inte vilka ämnen som finns. | Låg, cirka 11,80 USD | TDS finns inte bland de listade parametrarna i HaV:s API och är inte ett mått på badvattensäkerhet. | **Välj bort som separat sensor** |
| **DO, löst syre** | Vanligen analog signalbehandling eller dyrare digital/RS485-prob. | Mer krävande kalibrering, membran/elektrolyt eller dyr optisk prob. | Mycket hög, enkel hobbylösning cirka 169 USD eller mer | Ekologiskt intressant men inte kärnparameter i det valda badvatten-API:t. | **Framtida specialstudie** |
| **ORP** | Analog och känslig för jordning/störning. | Referenselektrod, rengöring och kalibreringskontroll. | Hög | Ingen direkt koppling till HaV:s kärndata och säger inte ensam om bad är säkert. | **Välj bort** |
| **BME280/SHT31, lufttemperatur och luftfuktighet** | Enkel I2C och 3,3 V-kompatibel. | Låg kalibreringsbörda. | Låg-medel | Mäter omgivande luft, inte badvatten. | **Välj bort ur vatten-MVP; kan användas endast om projektfrågan ändras** |

## 4. Föslags sensorer

### 4.1 DS18B20 - välj

**[Förslag]** Lägg till en vattentät DS18B20 även om README:n främst nämner turbiditet.

Skäl:

- Den är digital och undviker ESP32-S3:s analoga brus och spänningsnivåproblem.
- Den är billig, lätt att koppla och lätt att testa.
- Temperaturen behövs om gruppen senare vill temperaturkompensera EC, TDS eller pH.
- Temperaturen ger en begriplig serie i dashboarden även när turbiditetssensorn kalibreras eller felsöks.
- Den har tydligare koppling till badvattendata än pH, EC eller TDS.

Praktiskt:

- Kör sensorn på 3,3 V.
- Använd extern matning, inte parasitmatning, för en enklare och stabilare prototyp.
- Använd normalt 4,7 kOhm pull-up mellan DATA och 3,3 V.
- Spara både temperatur och sensorns unika 1-Wire-ID.
- Kontrollera den i isvatten och rumstempererat vatten eller mot en rimlig referenstermometer. Detta är en verifiering, inte en spårbar laboratoriekalibrering.

Tillverkarens datablad anger 1-Wire, 9-12 bitars upplösning och typiskt ±0,5 °C noggrannhet i intervallet -10 till +85 °C.

### 4.2 SEN0189 - välj med begränsningar

**[README-plan]** Turbiditet är projektets ursprungliga fysiska mätstorhet.

**[Förslag]** Behåll SEN0189 i MVP:n eftersom den ger en tydlig analog IoT-demonstration, men beskriv resultatet som **lokal grumlighetstrend** tills en dokumenterad kalibrering mot kända standarder har genomförts.

Skäl:

- Den är billig och ger synlig respons när mängden partiklar ändras.
- Den passar projektets redan beskrivna dataflöde.
- Den gör att gruppen kan visa ADC-läsning, filtrering, kalibrering, MQTT, datalagring och visualisering.

Begränsningar:

- Tillverkaren anger 5 V matning och analog utgång 0-4,5 V.
- Utgången måste nivåanpassas innan ESP32-S3.
- DFRobot beskriver produkten som inte vattentät; använd den därför som prov-/bänksensor och håll elektronik, kort och anslutningar torra.
- Smuts, repor, bubblor, omgivningsljus, probens vinkel, kärlets form och temperatur kan påverka signalen.
- En kurva från internet eller exempelkod gör inte automatiskt sensorn till en spårbar NTU-mätare.

**Rekommenderad MVP-tolkning:**

- lagra `raw_adc` och `raw_mv`,
- beräkna `turbidity_index` eller `ntu_estimate`,
- märk värdet med `quality_flag` och `calibration_id`,
- kalla det inte verifierad NTU förrän gruppens metod och referenser är dokumenterade,
- visa avvikelse från lokal baslinje, inte "badbart/inte badbart".

### 4.3 pH - vänta

**[Förslag]** pH är en rimlig fas 2-sensor men ger för mycket extra arbete i MVP:n.

SEN0161-V2 är elektriskt enklare än SEN0189 eftersom utgången anges till 0-3,0 V, men mätningen kräver:

- färska pH 4- och pH 7-buffertar,
- tvåpunktskalibrering,
- temperaturregistrering,
- sköljning mellan prover,
- korrekt våtförvaring av proben,
- kontroll av drift över tid.

Tillverkaren anger dessutom att labproben inte är avsedd för långvarig kontinuerlig nedsänkning. Om projektet senare ska mäta dygnet runt behövs en industriell 7/24-prob och en ny kostnads-/underhållsbedömning.

### 4.4 EC eller TDS - välj högst en senare

**[Förslag]** Om gruppen senare har en konkret fråga om salthalt eller lösta joner ska den mäta **EC** och vid behov presentera en tydligt märkt TDS-uppskattning. Köp inte både EC- och TDS-sensor för MVP:n.

Varför EC i första hand:

- EC är den direktare elektriska mätstorheten.
- TDS-värdet är en modell-/omräkningsberoende uppskattning och avslöjar inte vilka ämnen som finns i vattnet.
- DFR0300 har bättre möjlighet till tvåpunktskalibrering men kostar mer och kräver temperaturkompensation.

Varför vänta:

- Varken EC eller TDS är en listad kärnparameter i HaV:s öppna badvattendata.
- EC-kortets utgång kan nå 3,4 V och behöver nivåanpassning eller extern ADC.
- Den billiga labproben passar inte en permanent utomhusnod.
- Sensorinterferens och gemensam jord blir mer komplicerat när flera analoga vattenprober körs samtidigt. Mät sensorer sekventiellt och överväg elektrisk isolering i en framtida multisensorlösning.

## 5. Elsäkerhet och analog anslutning till ESP32-S3

ESP32-S3 är ett 3,3 V-system. Espressifs dokumentation anger att ADC-området med högsta attenuation är ungefär upp till 3,1 V, och rekommenderar kalibrerings-API för att omvandla råvärden till spänning. Tillverkaren påpekar också att mätningar över det effektiva området blir odefinierade.

### Regler för projektet

1. **Anslut aldrig en okänd analog signal direkt till en ADC-pin.** Mät först med multimeter och läs sensorns datablad.
2. **SEN0189:s 0-4,5 V måste delas ned.** En möjlig startpunkt är 10 kOhm överst och 18 kOhm mot jord, vilket ger cirka 2,89 V vid 4,5 V in. Verifiera verklig spänning och vald koppling innan anslutning.
3. **Använd ADC1, inte ADC2, för de analoga sensorerna** när Wi-Fi används. Det minskar risken för resurskonflikt och instabila läsningar.
4. **Gemensam jord krävs** mellan sensorernas signalbehandling och ESP32 om inte galvanisk isolering används.
5. **Håll nätspänning helt utanför prototypen.** Använd en godkänd, isolerad USB-/lågspänningsmatning.
6. **Håll ESP32, kopplingsdäck och sensorkort torra.** Endast en prob som uttryckligen är avsedd för vatten får komma i kontakt med provet.
7. Lägg gärna till seriemotstånd, RC-filter och skyddsklämning efter granskning av ansvarig elektronikperson.
8. Läs flera prover, använd median/medelvärde och spara även spridning. Filtrering får inte ersätta kalibrering.

### Rekommenderad MVP-koppling

```text
DS18B20 VCC   -> ESP32-S3 3V3
DS18B20 GND   -> ESP32-S3 GND
DS18B20 DATA  -> vald digital GPIO
4,7 kOhm      -> mellan DATA och 3V3

SEN0189 VCC   -> stabil 5 V lågspänningsmatning
SEN0189 GND   -> gemensam GND
SEN0189 AO    -> spänningsdelare -> vald ADC1-pin
```

Exakta GPIO-val beror på gruppens ESP32-S3-kort. Kontrollera kortets pinout, undvik boot-/strap-pinnar och dokumentera valen i firmware.

## 6. Koppling till öppna badvattendata

**[Förslag]** Använd Havs- och vattenmyndighetens API **Badplatser och badvatten** som extern referenskälla.

API:t innehåller bland annat:

- badplatser och koordinater,
- halter av indikatorbakterier,
- algblomning,
- avrådan från bad,
- badplatsklassificering,
- för vissa kustbad prognos för vattentemperatur.

### Vad som kan jämföras

| Lokal mätning | Öppen data | Tillåten tolkning |
|---|---|---|
| DS18B20 vattentemperatur | Uppmätt temperatur eller prognos när den finns | Jämför nivå och trend. En prognos ska märkas som prognos, inte facit. |
| SEN0189 grumlighetstrend | Datum för alginformation, avrådan eller provtagning | Utforskande tidsmässig jämförelse. Den visar inte orsak eller mikrobiologisk säkerhet. |
| Lokal nods koordinater | Badplatskoordinater | Koppla noden till närmaste eller uttryckligen vald badplats. Låt gruppen bekräfta matchningen. |
| pH/EC/TDS i framtiden | Ingen direkt kärnparameter i detta API | Visa som lokala kompletterande mätningar, inte som validering mot API:t. |

### Vad som inte får påstås

- Att låg turbiditet betyder låga bakteriehalter.
- Att klarare vatten alltid är säkrare att bada i.
- Att en lokal hobbyprob ersätter kommunens provtagning och laboratorieanalys.
- Att en korrelation i ett litet dataset visar orsakssamband.
- Att dashboardens egen avvikelseklass är samma sak som myndighetens `tjänligt`, `tjänligt med anmärkning` eller `otjänligt`.

### Rekommenderad märkning i dashboarden

> **Lokala prototypmätningar** visar temperatur och grumlighet vid noden. De är inte en officiell bedömning av badvattensäkerhet. Officiell klassificering, bakterieprov och avrådan visas separat med källa och uppdateringstid.

## 7. MVP - det gruppen faktiskt bör bygga först

MVP betyder här den minsta lösning som visar ett komplett och testbart IoT-flöde.

### 7.1 Måste ingå

#### Hårdvara och firmware

- ESP32-S3 läser DS18B20.
- ESP32-S3 läser SEN0189 via säker nivåanpassning till ADC1.
- Firmware skickar ett enhetligt JSON-meddelande via MQTT.
- Firmware validerar uppenbara fel, till exempel bortkopplad DS18B20 och ADC utanför tillåtet område.
- Simulatorn kan skicka samma schema som hårdvaran.

#### Backend och databas

- MQTT-consumer tar emot och validerar meddelandet.
- Dubbletter stoppas med `message_id` eller kombinationen sensor/tid.
- Råvärde, bearbetat värde, enhet, kvalitet och kalibrering sparas.
- REST-API returnerar senaste värden och historik.
- SQLite har index för sensor och tid.
- Tider lagras i UTC.

#### Dashboard

- senaste temperatur,
- senaste grumlighetstrend/NTU-estimat,
- senaste mottagningstid och online/offline,
- tidsseriediagram med val av parameter och tidsintervall,
- tydlig mätkvalitet och kalibreringsstatus,
- avvikelse från lokal baslinje,
- separat panel för officiell öppen data med källa och uppdateringstid,
- tydlig ansvarsfriskrivning om badvattensäkerhet.

#### Tester och dokumentation

- test av datavalidering,
- test av duplicatskydd,
- test av API för senaste värde och historik,
- test med simulerade normala, saknade och extrema värden,
- enkel kopplingsskiss,
- kalibreringsprotokoll,
- demo som fortfarande fungerar när den fysiska sensorn ersätts av simulatorn.

### 7.2 Ska inte blockera MVP

- pH, EC eller TDS,
- WebSockets; polling räcker för första demon,
- HTTP som parallell sensortransport,
- användarkonton/JWT om dashboarden bara körs lokalt under utveckling,
- produktions-TLS och full ACL-konfiguration,
- OTA och enhetshantering,
- PostgreSQL/TimescaleDB och Redis,
- Grafana/Prometheus/ELK/Loki,
- SMS, e-post, Teams eller Slack-larm,
- AI/ML-baserad anomaly detection,
- automatiska slutsatser om badvattensäkerhet.

## 8. Föreslaget MQTT-meddelande

**[Förslag]** Skicka flera observationer i ett meddelande men lagra varje observation som en egen rad.

```json
{
  "schema_version": 1,
  "message_id": "esp32-s3-01-00000142",
  "device_id": "esp32-s3-01",
  "observed_at": "2026-10-11T10:15:00Z",
  "firmware_version": "0.1.0",
  "measurements": [
    {
      "sensor_id": "temp-01",
      "metric": "water_temperature",
      "value": 17.6,
      "unit": "degC",
      "quality_flag": "ok"
    },
    {
      "sensor_id": "turbidity-01",
      "metric": "turbidity_index",
      "value": 0.42,
      "unit": "ratio",
      "raw_adc": 2381,
      "raw_mv": 1685,
      "quality_flag": "estimated",
      "calibration_id": "turbidity-01-cal-20261011"
    }
  ]
}
```

Använd `ntu_estimate` och enheten `NTU` först när kalibreringsmetoden mot kända referenser är dokumenterad. Fram till dess är `turbidity_index` ärligare.

## 9. Föreslagen SQLite-datamodell

**[README-plan]** README:n föreslår en enda `Reading` med `sensor_id`, tid, värde, enhet, kvalitet och status.

**[Förslag]** Behåll den enkla idén men separera enheter, sensorer, kalibreringar, mätningar och extern referensdata. Det gör pH/EC möjliga senare utan nya kolumner i varje mätvärdesrad.

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE devices (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    latitude        REAL,
    longitude       REAL,
    created_at      TEXT NOT NULL,
    last_seen_at    TEXT
);

CREATE TABLE sensors (
    id              TEXT PRIMARY KEY,
    device_id       TEXT NOT NULL REFERENCES devices(id),
    metric          TEXT NOT NULL,
    model           TEXT NOT NULL,
    native_unit     TEXT NOT NULL,
    interface       TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    installed_at    TEXT NOT NULL
);

CREATE TABLE calibrations (
    id                  TEXT PRIMARY KEY,
    sensor_id           TEXT NOT NULL REFERENCES sensors(id),
    calibrated_at       TEXT NOT NULL,
    method              TEXT NOT NULL,
    coefficients_json   TEXT,
    reference_json      TEXT,
    valid_until         TEXT,
    notes               TEXT
);

CREATE TABLE readings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      TEXT NOT NULL,
    sensor_id       TEXT NOT NULL REFERENCES sensors(id),
    observed_at     TEXT NOT NULL,
    received_at     TEXT NOT NULL,
    raw_value       REAL,
    raw_unit        TEXT,
    value           REAL NOT NULL,
    unit            TEXT NOT NULL,
    quality_flag    TEXT NOT NULL,
    calibration_id  TEXT REFERENCES calibrations(id),
    UNIQUE (message_id, sensor_id)
);

CREATE INDEX idx_readings_sensor_time
    ON readings(sensor_id, observed_at DESC);

CREATE TABLE bathing_sites (
    source              TEXT NOT NULL,
    external_id         TEXT NOT NULL,
    name                TEXT NOT NULL,
    municipality_id     TEXT,
    latitude            REAL,
    longitude           REAL,
    source_url          TEXT NOT NULL,
    PRIMARY KEY (source, external_id)
);

CREATE TABLE external_observations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source              TEXT NOT NULL,
    external_site_id    TEXT NOT NULL,
    observed_at         TEXT,
    fetched_at          TEXT NOT NULL,
    metric              TEXT NOT NULL,
    numeric_value       REAL,
    text_value          TEXT,
    unit                TEXT,
    source_updated_at   TEXT,
    raw_json            TEXT,
    FOREIGN KEY (source, external_site_id)
        REFERENCES bathing_sites(source, external_id),
    UNIQUE (source, external_site_id, metric, observed_at)
);
```

### Datamodellens regler

- ISO 8601 och UTC används för alla tider, till exempel `2026-10-11T10:15:00Z`.
- `observed_at` är sensorns mättid; `received_at` är backendens mottagningstid.
- Behåll råvärdet så att felaktig omräkning kan rättas i efterhand.
- `quality_flag` beskriver datakvalitet, exempelvis `ok`, `estimated`, `uncalibrated`, `out_of_range`, `sensor_error` eller `stale`.
- Officiell extern data lagras separat från lokala prototypmätningar.
- Myndighetens status får inte skrivas över av projektets egen avvikelselogik.
- Spara gärna hela API-svaret i `raw_json` för spårbarhet, men exponera bara validerade fält i dashboardens API.

I Django bör motsvarande `UniqueConstraint` och index definieras i modeller/migrationsfiler. SQL-blocket är en beslutad målmodell, inte en uppmaning att skapa tabeller manuellt bredvid Django migrations.

## 10. Dashboard-funktioner

### MVP

1. **Översiktskort**
   - vattentemperatur,
   - grumlighetstrend eller NTU-estimat,
   - senaste mättid,
   - enhet online/offline,
   - kalibrerad/okallibrerad.

2. **Historiskt diagram**
   - val av sensor,
   - 1 timme, 24 timmar, 7 dagar eller eget intervall,
   - råvärde kan visas i felsökningsläge,
   - luckor i data ska synas och inte fyllas med påhittade värden.

3. **Avvikelser**
   - markera mätfel och avvikelse från lokal baslinje,
   - använd texten `lokal sensoravvikelse`, inte `dåligt badvatten`,
   - visa vilken regel som utlöst markeringen.

4. **Öppen data**
   - vald badplats,
   - officiell klassificering och eventuell avrådan,
   - senaste bakterieprov när det finns,
   - alginformation,
   - källa, uppdateringstid och länk till HaV,
   - visuellt separerad från lokala sensorer.

5. **Datakvalitet**
   - sensor-ID och modell,
   - firmware-version,
   - kalibreringsdatum,
   - kvalitet/status,
   - antal saknade eller avvisade meddelanden.

### Fas 2

- pH och eventuellt EC,
- kalibreringssida med historik,
- export till CSV,
- annoteringar för rengöring, regn eller manuella prover,
- automatisk import från HaV:s API,
- enkel korrelationsvy med tydlig text att sambandet är explorativt,
- WebSockets om polling verkligen är ett problem,
- användarkonton och rollstyrning om fler än utvecklingsgruppen ska använda systemet.

### Framtida produktion

- industriella 24/7-prober,
- väderskyddat kapslings- och strömkoncept,
- extern ADC och/eller galvaniskt isolerade analoga kanaler,
- TLS, certifikathantering, MQTT-ACL och hemlighetshantering,
- OTA med signerad firmware och återställningsplan,
- larmflöde med ansvarig mottagare och kvittens,
- PostgreSQL/TimescaleDB först när datamängd eller samtidighet kräver det,
- observability och retention-policy.

## 11. Förslag på genomförandeordning

### Steg 1 - besluta och låsa kontraktet

- Bekräfta `DS18B20 + SEN0189`.
- Bekräfta att resultatet är en prototyp, inte officiell badvattenbedömning.
- Välj MQTT-topic och JSON-schema.
- Välj en testbadplats i HaV:s API.
- Bestäm vem som äger firmware, backend, databas, dashboard och test.

### Steg 2 - simulator före full hårdvara

- Skicka giltiga och ogiltiga meddelanden med simulatorn.
- Implementera validering, SQLite-modeller, duplicatskydd och API.
- Bygg dashboard mot simulerade data.

### Steg 3 - DS18B20

- Läs stabil temperatur.
- Lägg till sensorfel och enhetstest.
- Skicka genom hela MQTT-flödet och visa i dashboarden.

### Steg 4 - SEN0189

- Bygg och kontrollmät spänningsdelaren innan ESP32 ansluts.
- Spara rå ADC, millivolt och filtrerat värde.
- Dokumentera provkärl, position, temperatur, rengöring och referenspunkter.
- Presentera först ett grumlighetsindex; byt till NTU-estimat endast efter dokumenterad kalibrering.

### Steg 5 - öppna data och demo

- Importera en vald badplats och relevanta observationer.
- Visa officiell data i egen panel.
- Testa demo utan internet och/eller fysisk sensor med simulatorn.
- Dokumentera kända begränsningar och vad gruppen skulle göra i fas 2.

## 12. Definition av klart för MVP

MVP:n är klar när gruppen kan visa följande utan manuella databasändringar:

- ESP32-S3 eller simulator publicerar samma validerade schema.
- Minst temperatur passerar hela vägen till dashboarden.
- Turbiditet visas som grumlighetstrend eller dokumenterat estimat.
- Dubbletter ger inte dubbla rader.
- Felaktiga värden avvisas eller märks, och orsaken loggas.
- Dashboarden visar senaste värde, historik och datakvalitet.
- En officiell badplats kan visas separat från lokala mätningar.
- Systemet påstår inte att turbiditet ensam avgör badvattensäkerhet.
- Koppling, kalibreringsmetod, API-kontrakt och kända begränsningar är dokumenterade.
- Gruppen kan förklara vilka README-funktioner som medvetet flyttats till framtiden.

## 13. Beslutsfrågor för gruppen

Besvara dessa skriftligt innan fler sensorer köps:

1. Är projektets mål en **utbildningsprototyp** eller en nod för **kontinuerlig utomhusdrift**?
2. Godkänner gruppen `DS18B20 + SEN0189` som MVP och att pH/EC skjuts upp?
3. Ska turbiditet visas som `turbidity_index` tills kalibrering är dokumenterad?
4. Vilken exakt ESP32-S3-kortmodell har varje person, och vilka ADC1-/GPIO-pinnar är säkra på kortet?
5. Vem granskar och kontrollmäter nivåanpassningen innan SEN0189 ansluts?
6. Vilken badplats i HaV:s API ska användas, och varför är den relevant för den lokala mätplatsen?
7. Ska MVP:n använda endast MQTT, med HTTP enbart för API-läsning/test?
8. Vilket MQTT-topic och vilket JSON-schema fryses för första versionen?
9. Vad betyder `offline`, `stale`, `sensor_error`, `uncalibrated` och `anomaly` i gruppens gemensamma ordlista?
10. Hur ofta ska temperatur och turbiditet mätas och publiceras?
11. Hur dokumenteras kalibrering, rengöring och byte av prob?
12. Vilka delar av README:n är uttryckligen **framtida**, så att de inte bedöms som ofärdiga MVP-krav?
13. Vem ansvarar för att dashboardens texter inte blandar ihop lokal sensoravvikelse med officiell badvattenklassificering?
14. Vilka acceptanskriterier måste visas på nästa demo?

## 14. Rekommenderat gruppbeslut

Följande formulering kan läggas i ett protokoll eller issue:

> Gruppen bygger först en utbildnings-MVP med ESP32-S3, vattentät DS18B20 och SEN0189. DS18B20 används för vattentemperatur. SEN0189 används för lokal grumlighetstrend och får endast visas som NTU-estimat efter dokumenterad kalibrering. SEN0189:s analoga signal nivåanpassas och kontrollmäts innan anslutning till ADC1. pH och EC flyttas till fas 2; separat TDS-sensor väljs bort. Officiell information från Havs- och vattenmyndighetens API visas separat och används inte som bevis för att hobbygivarna mäter badvattensäkerhet. MVP:n prioriterar ett fungerande flöde från sensor/simulator via MQTT, Django och SQLite till REST-API och dashboard.

## 15. Källor och underlag

### Projektunderlag

- [Projektets README](https://github.com/muhaka-1/smart-env-monitoring/blob/main/README.md), läst 2026-10-11.
- Uppladdat LIA-underlag: *Information till handledare och företag*.
- Uppladdat kursunderlag: *LIA-seminarium #1 IOT25M*, särskilt kursmål om C/C++/Python, inbyggda system, reflektion och utveckling av kunskaper.
- Uppladdad projektrapport: *Dokumentation av IoT-projektets arkitektur*, använd som erfarenhetsunderlag för modularitet, SQLite och vikten av att avgränsa ett för stort scope.

### Tekniska primärkällor

- Analog Devices: [DS18B20 - datablad och produktinformation](https://www.analog.com/en/products/ds18b20.html).
- DFRobot: [Vattentät DS18B20 - utförande och listpris](https://www.dfrobot.com/product-2481.html).
- DFRobot: [SEN0189 - specifikation och kopplingsunderlag](https://wiki.dfrobot.com/sen0189).
- DFRobot: [SEN0189 - produktinformation, begränsning och listpris](https://www.dfrobot.com/product-1394.html?description=true&search=SEN0189).
- DFRobot: [SEN0161-V2 - pH-specifikation och kalibrering](https://wiki.dfrobot.com/sen0161-v2).
- DFRobot: [SEN0161-V2 - produktinformation och listpris](https://www.dfrobot.com/product-1782.html).
- DFRobot: [DFR0300 - EC-produktinformation](https://www.dfrobot.com/product-1123.html/).
- DFRobot: [SEN0244 - TDS-specifikation](https://wiki.dfrobot.com/sen0244).
- DFRobot: [SEN0244 - produktinformation och listpris](https://www.dfrobot.com/product-1662.html).
- Espressif: [ESP32-S3 ADC-dokumentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-reference/peripherals/adc/adc_calibration.html) och [ADC FAQ](https://docs.espressif.com/projects/esp-faq/en/latest/software-framework/peripherals/adc.html).
- Havs- och vattenmyndigheten: [API Badplatser och badvatten](https://www.havochvatten.se/data-kartor-och-rapporter/data-och-statistik/data-och-apier/api-badplatser-och-badvatten.html).
- Havs- och vattenmyndigheten: [Vad kommunen mäter i badvattnet](https://www.havochvatten.se/badplatser-och-badvatten/fakta-om-badvatten/faq-badvatten/2015-06-29-vad-ar-det-kommunen-mater-i-vattnet-och-varfor.html).
