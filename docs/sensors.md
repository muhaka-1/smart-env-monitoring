# Sensorer, intervall och meddelanden

## MVP-beslut för datasetet

- **Källa:** City of Chicago, *Beach Water Quality – Automated Sensors*.
- **Vald plats:** Ohio Street Beach.
- **Primärt mätvärde:** turbiditet i NTU, eftersom projektets scenario handlar om badvattenkvalitet.
- **Kompletterande mätvärde:** vattentemperatur i °C. Det ger ett andra realistiskt mätflöde men kan tas bort utan att MVP:n slutar fungera.
- **Lokal reservdata:** `sensor/data/chicago_sample.json` med 25 verkliga datasetrader.

### Kontroll av reservdatan

Kontrollen utfördes 2026-10-29. Alla 25 rader är användbara och ger tillsammans 50 simulerade mätvärden: 25 turbiditetsvärden och 25 temperaturvärden.

| Kontroll | Resultat |
|---|---|
| Plats | 25 av 25 rader: Ohio Street Beach |
| Unika `measurement_id` | 25 av 25 |
| Saknade platsnamn, tidsstämplar, mätvärden eller ID | 0 |
| Turbiditet | 0,00–0,99 NTU |
| Vattentemperatur | 22,4–23,1 °C |
| Rader som avvisas av simulatorns validering | 0 |

Den lokala kopian uppfyller därmed kravet på minst 20 användbara rader. Det fullständiga fjärrdatasetet kan däremot innehålla saknade, negativa eller orimliga värden. Dessa fall och simulatorns hantering dokumenteras i [`data-rules.md`](data-rules.md).

## Sensorlista i den äldre demofilen
Sensor-ID skapas av strandnamnet i datasetet: `<strandnamn som slug>-<mätstorhet>`.

Simulatorns reservfil `sensor/data/chicago_sample.json` innehåller 25 faktiska rader från Ohio Street Beach i [Chicago Beach Water Quality](https://data.cityofchicago.org/resource/qmqz-2xku.json), hämtade 2026-10-29. Tidsintervallet i källan är 2026-09-24 23:00–2026-09-25 23:00. Kolumnerna är `beach_name`, `measurement_timestamp`, `turbidity`, `water_temperature` och `measurement_id`. Fälten kan kontrolleras med `python -m tools.fetch_real_sample` i `sensor/`.

Den äldre filen `sample_readings.json` används separat för demodata. Tabellen nedan beskriver den, inte den nya reservfilen.

| Strand (visningsnamn) | Sensor-ID | Mätstorhet | Enhet | Gränsvärde (avvikelse om värdet är **över**) |
|---|---|---|---|---|
| Oak Street Beach | `oak-street-beach-turbidity` | Grumlighet | NTU | 30 |
| Oak Street Beach | `oak-street-beach-temperature` | Vattentemperatur | °C | 25 |
| 63rd Street Beach | `63rd-street-beach-turbidity` | Grumlighet | NTU | 30 |
| 63rd Street Beach | `63rd-street-beach-temperature` | Vattentemperatur | °C | 25 |
| Rainbow Beach | `rainbow-beach-turbidity` | Grumlighet | NTU | 30 |
| Rainbow Beach | `rainbow-beach-temperature` | Vattentemperatur | °C | 25 |

Gränsvärden: `ANOMALY_THRESHOLD_TURBIDITY` / `ANOMALY_THRESHOLD_TEMPERATURE` i backend. Projektet använder simulerade sensorer.

## Gränsvärden och statusens innebörd (issue #13)

Standardgränserna är 30 NTU för turbiditet och 25 °C för temperatur. Enligt motiveringen som Pat dokumenterade i [issue #13](https://github.com/muhaka-1/smart-env-monitoring/issues/13) är de konfigurerbara standardvärden för projektets demonstration, inte myndighetsgränser eller dokumenterade verksamhetskrav. De är inte beräknade från den nuvarande reservdatan.

30 NTU gör att den äldre demodatan visar både `OK` och `ANOMALY`: 24 av 240 turbiditetsvärden ligger över gränsen. Temperaturen i samma demodata ligger på 17–24 °C och ger därför inga avvikelser vid 25 °C. Temperaturgränsen används i stället för att verifiera avvikelsefunktionen i tester och manuellt skapad demodata. Detta är motiveringen för demonstrationsvärdena, inte en vetenskaplig bedömning av badvattenkvalitet.

`ANOMALY` betyder att värdet är **större än** den konfigurerade gränsen för sin mätstorhet. Ett värde på eller under gränsen ger `OK`. Statusen anger endast resultatet av denna jämförelse, inte en statistiskt fastställd avvikelse eller att vattnet är säkert att bada i. Simulatorn skickar värden från verkliga datasetrader med nya sändningstidsstämplar; det är inte en aktuell mätning på plats.

### Källor och tillämpningsgränser

- [Chicago Park District – Beach FAQs](https://www.chicagoparkdistrict.com/beach-faqs): badvattenövervakningen använder indikatorbakterien Enterococci. Turbiditet och temperatur ersätter inte denna bedömning.
- [US EPA – Recreational Water Quality Criteria and Methods](https://www.epa.gov/wqc/recreational-water-quality-criteria-and-methods): kriterierna behandlar bland annat indikatorer för fekal förorening och cyanotoxiner. De ger inte stöd för projektets gränser 30 NTU och 25 °C.
- [Health Canada – Physical, Aesthetic and Chemical Characteristics](https://www.canada.ca/en/services/health/publications/healthy-living/guidelines-canadian-recreational-water-physical-aesthetic-chemical-characteristics.html), tabell 1 och avsnitt 2.3: turbiditet under 50 NTU anges för klarhet och estetisk acceptans, medan ett generellt exakt temperaturgränsvärde inte fastställs. Detta är kanadensisk vägledning och motiverar inte att automatiskt ändra projektets gränser för Chicago.

Källorna granskades 2026-10-29. De förklarar begränsningarna i bedömningen; de är inte källor till projektets demonstrationsvärden. För användning som faktiska verksamhetsgränser krävs en separat motivering utifrån användningsfall och platsens förutsättningar.

Reservfilens turbiditet (0,00–0,99 NTU) och temperatur (22,4–23,1 °C) ligger under standardgränserna. För att demonstrera en avvikelse utan att ändra datasetet kan backend startas med en tillfällig lokal gräns, exempelvis `ANOMALY_THRESHOLD_TEMPERATURE=23`. Nya temperaturmätningar över 23 °C får då `ANOMALY`; redan lagrade statusvärden räknas inte om. Ta bort den tillfälliga miljövariabeln och starta om backend för att återgå till standardgränsen. Tester använder separata testvärden under, på och över båda gränserna.

## Enheter
- **Turbiditet: alltid NTU.** Temperatur: °C. Enheten följer med i varje meddelande (`unit`). Om `unit` saknas sätter backend rätt enhet utifrån `metric`; en annan enhet än den som hör till mätstorheten avvisas med HTTP 400.
- Temperatur är ett tillägg till kravet om turbiditet. Den kan tas bort utan att övriga delar påverkas.

## Sändningsfrekvens
| Källa | Intervall |
|---|---|
| PC-simulator | **5 s** totalt (`SENSOR_INTERVAL` eller `--interval`), ett meddelande åt gången |
| PC-simulator, per sensor (reservfilen) | var **10 s** (2 sensorer delar på 5 s-takten). Ett varv = 50 meddelanden = **4 min 10 s** |
| PC-simulator, per sensor (riktiga datasetet) | varierar: beror på antalet sensorer och hur mätningarna fördelas i datasetet |

Formel för simulatorn: tid per sensor = intervall × antal meddelanden mellan två sändningar från samma sensor.

## Dynamiska sensorer
- **Backend och dashboard: ja.** Sensorlistan hämtas från databasen (`/api/sensors/`), så en ny `sensor_id` dyker upp automatiskt första gången ett giltigt meddelande tas emot. Ingen kodändring behövs.
- **Simulatorn: nej.** Sensoruppsättningen läses från datasetet vid start; nya strandnamn kräver omstart.
- Sensor-ID måste matcha `^[a-z0-9][a-z0-9_-]{0,99}$`, annars svarar backend HTTP 400.

## MQTT
| | |
|---|---|
| **Topic** | `beach/<sensor_id>/readings` (backend prenumererar på `beach/+/readings`) |
| **QoS** | 1 (minst en gång; dubbletter avvisas av unik constraint på `sensor_id` + `timestamp`) |
| **Format** | JSON |

```json
{"sensor_id":"oak-street-beach-turbidity","metric":"turbidity","timestamp":"2026-10-27T12:00:00.123456+00:00","value":4.28,"unit":"NTU","quality":"good"}
```
`timestamp` är sändtidpunkten (aktuell tid, UTC) enligt krav 2.1; datasetets ursprungliga mättid bevaras inte.
`quality`: `good`, `suspect` eller `bad`.

**Vid anslutningsfel**
1. Tillfälligt fel (ingen broker, tidsgräns, HTTP 5xx): upp till **5 försök** med exponentiell väntetid (1, 2, 4, 8 s). Varje försök loggas.
2. Efter sista försöket loggas felet och mätvärdet **förloras** (ingen lagring på sändarsidan).
3. Avvisad data (HTTP 4xx): **ingen retry**, felet loggas.
4. Backend loggar och avvisar ogiltig data utan att stoppa konsumenten.
5. Klienten (`paho`) återansluter själv i bakgrunden efter ett avbrott.

## Demodata för diagrammet
`python manage.py seed_demo_data --repeat 7` fyller databasen med cirka 6 dygn historik för alla 6 sensorer (se README).
