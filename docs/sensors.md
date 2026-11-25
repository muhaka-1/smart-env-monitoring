# Sensorer, intervall och meddelanden

## Val av källdata

- **Källa:** City of Chicago, *Beach Water Quality – Automated Sensors*, Socrata `qmqz-2xku`.
- **Platser för projektets uppspelning:** Ohio Street Beach, 63rd Street Beach och Rainbow Beach. Antalet tre är ett projektval, inte ett krav från uppgiften.
- **Mätstorheter:** turbiditet (`turbidity`, NTU) och vattentemperatur (`water_temperature`, °C). Lufttemperatur används inte.
- **Urval:** serverfilter `beach_name` per plats, 25 giltiga rader med båda mätstorheterna och unika `measurement_id`. Sortering: `measurement_timestamp DESC, measurement_id DESC`.
- **Ofullständiga rader:** ordinarie validering används; urvalet söker nästa sida tills kvoten fyllts, högst 10 sidor per plats. En ofullständig kvot eller ett nätverksfel ger återgång till den verifierade reservfilen för alla tre platser. Saknade värden ersätts aldrig med noll.
- **Reservfil:** `sensor/data/chicago_sample.json`. Den innehåller ursprungliga rader inklusive `measurement_id` och källtid; inga slumpmässiga variationer används.

### Ursprungskontroll av reservfilen

Hämtad och verifierad **2026-11-11** från [officiellt JSON-API](https://data.cityofchicago.org/resource/qmqz-2xku.json). För varje plats används `$where=beach_name='platsnamn'`, `$limit=25` och sidindelning med `$offset`. Alla 75 sparade rader jämfördes därefter i sin helhet mot ett separat API-anrop filtrerat på deras `measurement_id`: **75 av 75 matchade exakt**.

| Plats | Giltiga rader | Äldsta källtid | Nyaste källtid |
| --- | ---: | --- | --- |
| Ohio Street Beach | 25 | 2026-09-24 23:00 | 2026-09-25 23:00 |
| 63rd Street Beach | 25 | 2015-09-13 03:00 | 2025-03-18 00:30 |
| Rainbow Beach | 25 | 2015-09-30 05:00 | 2025-03-18 00:30 |

Källtiderna ovan är återgivna som i datasetet. Äldre ursprungstider är väntade vid återspelning. Alla rader klarar befintlig validering och ger totalt 150 mätningar, 25 per sensor. Verktyget `python -m tools.fetch_real_sample --beach "Ohio Street Beach" --rows 25` använder samma serverfiltrerade urval.

Sensor-ID skapas av strandnamnet: `<strandnamn som slug>-<mätstorhet>`. Oak Street Beach finns inte i den aktuella vattenmätgruppen och ingår inte i uppspelningen. Den äldre demofilen och kommandot för direktinläsning av varierad demohistorik har tagits bort; normal start fyller bara historik via simulatorn och mottagningsvägen.

## Gränsvärden och statusens innebörd (issue #13)

Standardgränserna är 30 NTU för turbiditet och 25 °C för temperatur. Enligt motiveringen som Pat dokumenterade i [issue #13](https://github.com/muhaka-1/smart-env-monitoring/issues/13) är de konfigurerbara standardvärden för projektets demonstration, inte myndighetsgränser eller dokumenterade verksamhetskrav. De är inte beräknade från den nuvarande reservdatan.

30 NTU gör att den äldre demodatan visar både `OK` och `ANOMALY`: 24 av 240 turbiditetsvärden ligger över gränsen. Temperaturen i samma demodata ligger på 17–24 °C och ger därför inga avvikelser vid 25 °C. Temperaturgränsen används i stället för att verifiera avvikelsefunktionen i tester och manuellt skapad demodata. Detta är motiveringen för demonstrationsvärdena, inte en vetenskaplig bedömning av badvattenkvalitet.

`ANOMALY` betyder att värdet är **större än** den konfigurerade gränsen för sin mätstorhet. Ett värde på eller under gränsen ger `OK`. Statusen anger endast resultatet av denna jämförelse, inte en statistiskt fastställd avvikelse eller att vattnet är säkert att bada i. Simulatorn skickar värden från verkliga datasetrader med nya sändningstidsstämplar; det är inte en aktuell mätning på plats.

### Källor och tillämpningsgränser

- [Chicago Park District – Beach FAQs](https://www.chicagoparkdistrict.com/beach-faqs): badvattenövervakningen använder indikatorbakterien Enterococci. Turbiditet och temperatur ersätter inte denna bedömning.
- [US EPA – Recreational Water Quality Criteria and Methods](https://www.epa.gov/wqc/recreational-water-quality-criteria-and-methods): kriterierna behandlar bland annat indikatorer för fekal förorening och cyanotoxiner. De ger inte stöd för projektets gränser 30 NTU och 25 °C.
- [Health Canada – Physical, Aesthetic and Chemical Characteristics](https://www.canada.ca/en/services/health/publications/healthy-living/guidelines-canadian-recreational-water-physical-aesthetic-chemical-characteristics.html), tabell 1 och avsnitt 2.3: turbiditet under 50 NTU anges för klarhet och estetisk acceptans, medan ett generellt exakt temperaturgränsvärde inte fastställs. Detta är kanadensisk vägledning och motiverar inte att automatiskt ändra projektets gränser för Chicago.

Källorna granskades 2026-10-29. De förklarar begränsningarna i bedömningen; de är inte källor till projektets demonstrationsvärden. För användning som faktiska verksamhetsgränser krävs en separat motivering utifrån användningsfall och platsens förutsättningar.

Reservfilen innehåller ursprungliga värden från tre platser och kan ge både OK och ANOMALY. För att demonstrera en avvikelse utan att ändra datasetet kan backend startas med en tillfällig lokal gräns, exempelvis `ANOMALY_THRESHOLD_TEMPERATURE=23`. Kör sådana manuella försök endast mot en separat testdatabas med `EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend`, aldrig mot driftens databas eller SMTP-utskick. Nya temperaturmätningar över 23 °C får då `ANOMALY`; redan lagrade statusvärden räknas inte om. Ta bort den tillfälliga miljövariabeln och starta om backend för att återgå till standardgränsen. Tester använder separata testvärden under, på och över båda gränserna.

## Enheter

- **Turbiditet: alltid NTU.** Temperatur: °C. Enheten följer med i varje meddelande (`unit`). Om `unit` saknas sätter backend rätt enhet utifrån `metric`; en annan enhet än den som hör till mätstorheten avvisas med HTTP 400.
- Temperatur är ett tillägg till kravet om turbiditet. Den kan tas bort utan att övriga delar påverkas.

## Sändningsfrekvens

| Källa | Intervall |
| --- | --- |
| PC-simulator | **5 s** totalt (`SENSOR_INTERVAL` eller `--interval`), ett meddelande åt gången |
| PC-simulator, per sensor | ungefär var **30 s** (6 sensorer delar på 5 s-takten). Ett varv = 150 meddelanden = **12 min 30 s** |
| Fördelning | en mätning per sensor i varje sexmeddelandersomgång, i tidsordning inom respektive sensor |

Formel för simulatorn: tid per sensor = intervall × antal meddelanden mellan två sändningar från samma sensor.

## Dynamiska sensorer

- **Backend och dashboard: ja.** Sensorlistan hämtas från databasen (`/api/sensors/`), så en ny `sensor_id` dyker upp automatiskt första gången ett giltigt meddelande tas emot. Ingen kodändring behövs.
- **Simulatorn: nej.** Sensoruppsättningen läses från datasetet vid start; nya strandnamn kräver omstart.
- Sensor-ID måste matcha `^[a-z0-9][a-z0-9_-]{0,99}$`, annars svarar backend HTTP 400.

## MQTT

| | |
| --- | --- |
| **Topic** | `beach/<sensor_id>/readings` (backend prenumererar på `beach/+/readings`) |
| **QoS** | 1 (minst en gång; dubbletter avvisas av unik constraint på `sensor_id` + `timestamp`) |
| **Format** | JSON |

```json
{"sensor_id":"ohio-street-beach-turbidity","metric":"turbidity","timestamp":"2026-10-27T12:00:00.123456+00:00","value":4.28,"unit":"NTU","quality":"good"}
```

`timestamp` är sändtidpunkten (aktuell tid, UTC) enligt krav 2.1; datasetets ursprungliga mättid bevaras inte.
`quality`: `good`, `suspect` eller `bad`. Officiella nollvärden bevaras; saknade eller logiska värden (`true`/`false`) ersätts aldrig med noll.

### Vid anslutningsfel

1. Tillfälligt fel (ingen broker, tidsgräns, HTTP 5xx): upp till **5 försök** med exponentiell väntetid (1, 2, 4, 8 s). Varje försök loggas.
2. Efter sista försöket loggas felet och mätvärdet **förloras** (ingen lagring på sändarsidan).
3. Avvisad data (HTTP 4xx): **ingen retry**, felet loggas.
4. Backend loggar och avvisar ogiltig data utan att stoppa konsumenten.
5. Klienten (`paho`) återansluter själv i bakgrunden efter ett avbrott.

## Historik i kördatabasen

Historik skapas genom verklig inmatning från simulatorn via HTTP eller MQTT. Automatiska tester får använda konstruerade värden i separata testdatabaser; de ska inte fylla kördatabasen.
