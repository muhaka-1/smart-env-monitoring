# Testdokumentation

Dokumentet beskriver automatiska kontroller och dokumenterade verifieringar. Resultat gäller den angivna körningen; de ersätter inte framtida tester. Manuella kontroller som inte har utförts markeras uttryckligen nedan.

## Testmiljö och e-post

Installera beroendena i en separat venv enligt [README](../README.md). Kör från projektroten med miljön aktiverad och ange minnesbackend i testterminalen **innan** Django-kommandon körs, även om `.env` innehåller riktiga SMTP-uppgifter.

PowerShell:

```powershell
$env:EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
```

Git Bash/macOS/Linux:

```bash
export EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend
```

Processvariabeln har företräde framför `.env`. Testbackend lagrar mejl i processens minne och skickar inte till externa mottagare. Utan denna inställning kan en ren klon stoppas av SMTP-kontrollerna. SMTP är fortfarande applikationens standard; testerna verifierar inte verklig leverans till en inkorg. Se [e-postdokumentationen](email.md) för separat SMTP-verifiering.

Avsluta testterminalen efteråt, eller ta bort variabeln med `Remove-Item Env:EMAIL_BACKEND` i PowerShell respektive `unset EMAIL_BACKEND` i Bash innan riktig SMTP används.

### Automatiska kontroller

```bash
python -B backend/manage.py makemigrations --check --dry-run
python -B backend/manage.py test monitoring.tests
node backend/monitoring/tests/dashboard.test.cjs
cd sensor
python -B -m unittest discover -s tests -t .
cd ..
```

Samma argument fungerar i PowerShell. Simulatorns testkommando nedan körs från `sensor/`; backend- och dashboardkommandon körs från projektroten.

## Backend (Django, `python backend/manage.py test monitoring`)

Tester: validering (HTTP 400), API-nyckel, senaste värde, historik med datumfilter och sortering, per-mätstorhet gränsvärde, dubblettskydd, MQTT-hantering av ogiltig data, demodata (`seed_demo_data`) och att firmwarens gränsvärden är lika med backendens.

Åtkomsttesterna i `test_access_control.py` verifierar att senaste värden är publika, att anonym historik nekas för både `GET` och `HEAD`, att inloggad historik fungerar och att historikpanelen inte skickas i den publika sidans HTML. Se [`access-control.md`](access-control.md).

Lösenordstesterna i `test_password.py` verifierar glömt lösenord (neutral bekräftelse, giltig, ogiltig, använd och utgången token) och lösenordsbyte med Djangos lösenordsvalidering. Se [`password.md`](password.md).

Regressionstesterna från PR #86 verifierar att fel API-nyckel med icke-ASCII-tecken ger HTTP 401 utan att spara en mätning, att en matchande nyckel fungerar och att datum som hamnar utanför giltigt UTC-intervall ger HTTP 400 för både historik-API och historik-PDF.

## Sensorsimulator (`python -m unittest discover -s tests -t .`)

Tester: normalisering och felregler för datasetet (NaN, Infinity, tomt strandnamn, ogiltig tid), giltig reservfil, retry/backoff, HTTP-statusmappning.

## Dashboard (`node backend/monitoring/tests/dashboard.test.cjs`)

Dashboardens bibliotek läses lokalt. Testet verifierar status, intervall, åtkomstflagga och avvikelsemarkering. Verifiera även tidsaxel med ojämna tidsavstånd och märkning av inaktuella mätningar. `READING_STALE_SECONDS` styr tidsgränsen (standard 300 sekunder).

## Migrationskontroll

```powershell
python backend\manage.py makemigrations --check --dry-run
```

## Verifierade resultat – 2026-11-11

Verifieringen utfördes på Windows i en separat klon av `development`, med en ny venv, isolerad databas och backendändringarna från PR #86 (`8ebede5`). Efter merge kontrollerades att de sex ändrade filerna i `development` vid `421b3b1` var identiska med PR:n. Inga riktiga SMTP-utskick gjordes och projektets befintliga databas ändrades inte.

| Kontroll | Förväntat | Faktiskt resultat |
| --- | --- | --- |
| Installation i ny venv | Båda requirements-filerna kan installeras | Godkänt: rotens och backendens beroenden installerades |
| Django | Alla backendtester godkända | 215 tester, `OK` |
| Simulator | Alla simulatortester godkända | 21 tester, `OK` |
| Dashboard | Befintliga kontroller inklusive händelsehantering och resize godkända | Godkänt |
| Migrationer | Inga modelländringar utan migration | `No changes detected` |
| HTTP-kedjan | Mätningar skickas, sparas och kan läsas via latest och inloggad historik | 8/8 kontroller godkända |
| Omstart av Django | Samma konto och tidigare mätningar finns kvar; nya mätningar fungerar | Godkänt: HTTP-kedjan kördes igen och tre nya mätningar sparades |
| MQTT-kedjan | Publicerade mätningar når databasen | 3/3 mätningar sparades före och 3/3 efter omstart av den isolerade brokern; mottagaren återanslöt |
| CI efter merge | Alla CI-kontroller godkända | [Godkänt på `421b3b1`](https://github.com/muhaka-1/smart-env-monitoring/actions/runs/42930753223) |

Lokala portar ändrades till 8767 för HTTP och 18884 för den isolerade Mosquitto-brokern så att befintliga tjänster inte påverkades. Det var en lokal verifiering på en dator, inte det andra fysiska datortestet i [#76](https://github.com/muhaka-1/smart-env-monitoring/issues/76).

## Manuella och webbläsarbaserade kontroller

Åtkomst och responsivitet nedan verifierades separat med syntetiska data och testkonton 2026-11-10–11. Det var en teknisk webbläsargranskning, inte ett deltagartest. Ett verkligt deltagartest enligt [usability-test.md](usability-test.md) och ett långtest får inte räknas som utförda utifrån dessa resultat.

| ID | Test | Metod | Förväntat | Faktiskt |
| --- | --- | --- | --- | --- |
| M-01 | End-to-end | Simulator → MQTT → backend → dashboard | Värden syns inom 10 s | Delvis: MQTT till databas verifierat enligt ovan. Hela kedjans tid till synlig dashboard mättes inte i denna körning. |
| M-02 | Avvikelse | Grumligt vatten / varmt vatten | Rött kort och gränslinje i diagram | Delvis: avvikelsesymbol, statusförklaring och gränslinje verifierade med syntetiska data. Rött kort för en färsk avvikelse verifierades inte separat i denna körning. |
| M-03 | Kommunikationsfel | Stoppa brokern/Django | Retry loggas, ingen krasch, data kommer efter återstart | Delvis: kontrollerad omstart, bevarade data och MQTT-återanslutning godkända. Publicering under avbrott och uttömda retry-försök testades inte i denna körning; tidigare MQTT-protokoll finns i [mqtt.md](mqtt.md). |
| M-06 | Långtest | Kör flera timmar | Stabil datainsamling | Ej utfört i denna verifiering. |
| M-65.1 | Publik dashboard | Öppna `/` utan session | Senaste värden visas; historik och tidsfilter saknas | Godkänt: senaste värden visades, historikpanel och PDF-knapp saknades. |
| M-65.2 | Skyddat historik-API | Anropa `GET` och `HEAD /api/readings/` utan session | HTTP 401/403 och ingen historikdata | Godkänt: GET och HEAD gav HTTP 403 utan historik. |
| M-65.3 | Inloggad historik | Logga in och öppna `/` samt `/api/readings/` | Historikpanel visas och API svarar 200 | Godkänt: panelen visades, API gav 200 och sensor-, dygns- och egna tidsfilter fungerade. |
| M-65.4 | Utloggning | Logga ut med POST och försök läsa historik | Sessionen avslutas och historiken nekas | Godkänt: POST avslutade sessionen; API nekade åtkomst och skyddade sidor hänvisade till inloggning. |
| M-65.5 | Responsiv åtkomstvy | Kontrollera cirka 390, 1024 och 1400 px | Rätt innehåll och navigation utan överlappning | Delvis: 390, 768 och 1400 px verifierade utan horisontellt överflöde; resize-fixen kontrollerades även vid 320 px. 1024 px verifierades inte separat. |
