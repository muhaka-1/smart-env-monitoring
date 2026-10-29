# Testdokumentation

Varje testfall anger vad som testas, hur, förväntat resultat och faktiskt resultat.

## Backend (Django, `python manage.py test`)
Tester: validering (HTTP 400), API-nyckel, senaste värde, historik med datumfilter och sortering, per-mätstorhet gränsvärde, dubblettskydd, MQTT-hantering av ogiltig data, demodata (`seed_demo_data`) och att firmwarens gränsvärden är lika med backendens.

## Sensorsimulator (`python -m unittest discover -s tests -t .`)
Tester: normalisering och felregler för datasetet (NaN, Infinity, tomt strandnamn, ogiltig tid), giltig reservfil, retry/backoff, HTTP-statusmappning.

Dashboardens bibliotek läses lokalt. Verifiera tidsaxel med ojämna tidsavstånd och märkning av inaktuella mätningar. `READING_STALE_SECONDS` styr tidsgränsen (standard 300 sekunder).

## Manuella tester (fylls i)
| ID | Test | Metod | Förväntat | Faktiskt |
|---|---|---|---|---|
| M-01 | End-to-end | Simulator → MQTT → backend → dashboard | Värden syns inom 10 s | |
| M-02 | Avvikelse | Grumligt vatten / varmt vatten | Rött kort och gränslinje i diagram | |
| M-03 | Kommunikationsfel | Stoppa brokern/Django | Retry loggas, ingen krasch, data kommer efter återstart | |
| M-06 | Långtest | Kör flera timmar | Stabil datainsamling | |
