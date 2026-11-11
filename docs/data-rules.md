# Regler för saknade och felaktiga värden

Gäller datasetet (och reservfilen) i simulatorn (`sensor/sensor_sim/data_source.py`).
En rad kan ge två mätvärden (turbiditet och temperatur). Ett ogiltigt värde avvisar bara det värdet, inte hela raden, om inte felet gäller strandnamn eller tid.

| Fall | Regel | Räknas som |
| --- | --- | --- |
| Strandnamn saknas, är tomt eller blir tomt efter slugify (t.ex. `!!!`) | Hela raden avvisas | `row:beach_name` |
| Tidsstämpel saknas eller kan inte tolkas som ISO 8601 | Hela raden avvisas | `row:timestamp` |
| Logiskt värde (`true` eller `false`) | Avvisas före omvandling till tal | `turbidity:invalid` / `temperature:invalid` |
| Turbiditet saknas, är inte ett tal, `NaN` eller `±Infinity` | Turbiditeten avvisas | `turbidity:invalid` |
| Turbiditet < 0 | Turbiditeten avvisas | `turbidity:negative` |
| Turbiditet > 1000 NTU | **Skickas**, men `quality = suspect` | |
| Temperatur saknas, inte tal, `NaN` eller `±Infinity` | Temperaturen avvisas | `temperature:invalid` |
| Temperatur utanför −5…50 °C | Temperaturen avvisas | `temperature:out_of_range` |

- Avvisade värden loggas (en varning med antal per orsak) och skickas aldrig.
- Tidsstämplar med `Z` eller tidszon omvandlas till UTC; tider utan zon tolkas som UTC.
- Reservfilen `sensor/data/chicago_sample.json` testas så att alla rader är giltiga (inga avvisade).

## Backend (andra försvarslinjen)

Backend validerar allt som tas emot oavsett källa (HTTP eller MQTT):

| Fall | Svar |
| --- | --- |
| Logiskt `value` (`true` eller `false`) | HTTP 400 (MQTT: avvisas); ingen läsning, varning eller användarmeddelande skapas |
| Obligatoriskt fält saknas, ogiltigt tal, `NaN`/`Infinity`, ogiltigt `sensor_id`, okänd `metric` eller `quality` | HTTP 400 (MQTT: loggas och avvisas) |
| Turbiditet < 0 eller temperatur utanför −5…50 °C | HTTP 400 (MQTT: loggas och avvisas); mätningen sparas inte |
| Samma `sensor_id` + `timestamp` en gång till | HTTP 400 (dubblett) |
| `unit` som inte hör till `metric` (turbiditet = `NTU`, temperatur = `°C`), t.ex. HTML i fältet | HTTP 400 (dashboarden visar enheten som text, issue #43) |
| Fel eller saknad API-nyckel (när `INGEST_API_KEY` är satt) | HTTP 401 |

## Tester

- `sensor/tests/test_data_source.py`: alla regler ovan, samt att reservfilen är en giltig JSON-lista utan avvisade rader.
- `backend/monitoring/tests/test_services.py`, `test_api.py`: backendens regler.
- `sensor/tests/test_data_source.py`: serverfilter per plats, sidindelning, verifierad reservdata och balanserad uppspelning.

Urvalet för uppspelning kräver att båda mätstorheterna i en rad klarar dessa regler. Vid ett avvisat värde söker hämtningen ytterligare rader, utan att ändra eller ersätta källvärden.
