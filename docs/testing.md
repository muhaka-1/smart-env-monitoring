# Testdokumentation

Varje testfall anger vad som testas, hur, förväntat resultat och faktiskt resultat.

## Backend (Django, `python backend/manage.py test monitoring`)

Tester: validering (HTTP 400), API-nyckel, senaste värde, historik med datumfilter och sortering, per-mätstorhet gränsvärde, dubblettskydd, MQTT-hantering av ogiltig data, demodata (`seed_demo_data`) och att firmwarens gränsvärden är lika med backendens.

Åtkomsttesterna i `test_access_control.py` verifierar att senaste värden är publika, att anonym historik nekas för både `GET` och `HEAD`, att inloggad historik fungerar och att historikpanelen inte skickas i den publika sidans HTML. Se [`access-control.md`](access-control.md).

Lösenordstesterna i `test_password.py` verifierar glömt lösenord (neutral bekräftelse, giltig, ogiltig, använd och utgången token) och lösenordsbyte med Djangos lösenordsvalidering. Se [`password.md`](password.md).

## Sensorsimulator (`python -m unittest discover -s tests -t .`)

Tester: normalisering och felregler för datasetet (NaN, Infinity, tomt strandnamn, ogiltig tid), giltig reservfil, retry/backoff, HTTP-statusmappning.

## Dashboard (`node backend/monitoring/tests/dashboard.test.cjs`)

Dashboardens bibliotek läses lokalt. Testet verifierar status, intervall, åtkomstflagga och avvikelsemarkering. Verifiera även tidsaxel med ojämna tidsavstånd och märkning av inaktuella mätningar. `READING_STALE_SECONDS` styr tidsgränsen (standard 300 sekunder).

## Migrationskontroll

```powershell
python backend\manage.py makemigrations --check --dry-run
```

## Manuella tester (fylls i)

| ID | Test | Metod | Förväntat | Faktiskt |
| --- | --- | --- | --- | --- |
| M-01 | End-to-end | Simulator → MQTT → backend → dashboard | Värden syns inom 10 s | |
| M-02 | Avvikelse | Grumligt vatten / varmt vatten | Rött kort och gränslinje i diagram | |
| M-03 | Kommunikationsfel | Stoppa brokern/Django | Retry loggas, ingen krasch, data kommer efter återstart | |
| M-06 | Långtest | Kör flera timmar | Stabil datainsamling | |
| M-65.1 | Publik dashboard | Öppna `/` utan session | Senaste värden visas; historik och tidsfilter saknas | |
| M-65.2 | Skyddat historik-API | Anropa `GET` och `HEAD /api/readings/` utan session | HTTP 401/403 och ingen historikdata | |
| M-65.3 | Inloggad historik | Logga in och öppna `/` samt `/api/readings/` | Historikpanel visas och API svarar 200 | |
| M-65.4 | Utloggning | Logga ut med POST och försök läsa historik | Sessionen avslutas och historiken nekas | |
| M-65.5 | Responsiv åtkomstvy | Kontrollera cirka 390, 1024 och 1400 px | Rätt innehåll och navigation utan överlappning | |
