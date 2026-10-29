# Sensorer, intervall och meddelanden

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
