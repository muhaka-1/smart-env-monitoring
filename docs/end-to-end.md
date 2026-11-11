# Hela kedjan: från ren start till REST-API (issue #21)

```text
Dataset -> Python-simulator -> HTTP (eller MQTT) -> Django -> SQLite -> REST-API (latest + history)
```
Verifieringen använder den riktiga simulatorn mot en riktig server och läser tillbaka varje skickad mätning via API:t.

## Ren lokal start (Windows/Git Bash, samma steg på macOS/Linux)
Kräver Python 3.11+ och Git. Börja i en tom mapp. Stegen nedan är en isolerad verifiering utan riktiga mejl: minnesbackend anges uttryckligen och SMTP-uppgifter behövs inte. För vanlig lokal drift med riktig e-post, konfigurera `.env` enligt [README](../README.md) och [email.md](email.md) och använd SMTP-backend.
```bash
git clone https://github.com/muhaka-1/smart-env-monitoring.git
cd smart-env-monitoring
git checkout development
python -m venv .venv
source .venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
# Om Scripts/activate saknas (MSYS/MinGW): source .venv/bin/activate
python -m pip install -r requirements.txt -r backend/requirements.txt
export EMAIL_BACKEND=django.core.mail.backends.locmem.EmailBackend
cd backend
python manage.py migrate                 # skapar en tom lokal databas
python manage.py createsuperuser --username local-review  # välj lösenord interaktivt
python manage.py runserver 8001          # lämna terminalen öppen
```
I PowerShell aktiveras miljön med `.\.venv\Scripts\Activate.ps1` och testbackend sätts med `$env:EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"`. Använd en separat testterminal så att inställningen inte förväxlas med riktig SMTP.

I en **andra terminal** (aktivera `.venv` igen från projektets rotmapp):
```bash
cd sensor
python -m tools.verify_flow --base-url http://127.0.0.1:8001 --username local-review
```
Ange samma lösenord när verktyget frågar; skriv det inte i kommandot. Historik kräver inloggning, så kontot behövs även om senaste värden är publika. Använd samma värdnamn vid inloggning och API-anrop. Om `INGEST_API_KEY` konfigureras måste samma värde finnas i simulatorns processmiljö; simulatorn läser inte backendens `.env`.
Förväntat resultat (sensor-ID beror på datasetets strand):
```text
PASS  Backend svarar (/api/health/)  [HTTP 200]
PASS  Simulatorn skickade 3 mätningar och backend bekräftade alla (HTTP 201)  [3 av 3 bekräftade]
PASS  Varje meddelande har sensor_id, timestamp (UTC), value, unit och quality  [alla fält finns]
PASS  latest: <sensor_id> returnerar senast skickade mätning  [värde ... NTU, status OK]
PASS  history: <sensor_id> innehåller alla ... skickade mätningar i tidsordning  [... rader i API:t]
RESULTAT: N/N kontroller godkända
```
Verktyget avslutas med felkod 1 om någon kontroll misslyckas (backend nere, 401 vid fel API-nyckel, mätning som inte kan läsas tillbaka med samma värde, enhet, kvalitet och tid).

Flaggor: `--count 10` (fler mätningar), `--online` (hämta riktiga datasetet i stället för den lokala reservfilen).

## Kontrollera manuellt i webbläsaren eller med curl
```bash
curl "http://localhost:8001/api/readings/latest/"                              # senaste värde per sensor
```
Dashboarden visar samma data på `http://127.0.0.1:8001/`. Logga in där för att se historik eller använd verifieringsverktyget ovan, som skickar sessionscookien även vid historikanrop. Anonymt `curl` mot `/api/readings/` ger HTTP 403.

## Stoppa och starta om

Stoppa Django med `Ctrl+C` och starta samma kommando igen från samma klon. Behåll `backend/db.sqlite3` och testbackend i backendterminalen. Kör sedan verifieringsverktyget igen med samma konto. Verktyget skickar nya tidsstämplar; tidigare mätningar och konto ska finnas kvar. Radera inte databasen och skapa inte om kontot vid omstart.

## MQTT-varianten
MQTT kräver broker och mottagare. Följ `docs/mqtt.md`, avsnitt 1 till 4, och kör sedan `python -m sensor_sim --transport mqtt --offline --count 3` i `sensor/`. Mätningarna ska synas i samma API-anrop som ovan.

## Automatiskt test (körs även i CI)
`backend/monitoring/tests/test_end_to_end.py` startar en verklig server med en **tom testdatabas** och kör simulatorn mot den, och kontrollerar dessutom att simulatorns MQTT-meddelanden (topic och JSON) accepteras av mottagaren utan broker:
```bash
cd backend
python manage.py test monitoring.tests.test_end_to_end
```

## Kopplingen till "Klart när" i #21
| Kriterium | Bevis |
|---|---|
| En simulerad mätning passerar hela kedjan | `verify_flow`: kontrollerna "skickade ... bekräftade (HTTP 201)" och "latest"; testet `HttpChainTests` |
| Mätningen kan hämtas via latest och history | `verify_flow`: kontrollerna `latest:` och `history:` per sensor |
| Kan upprepas från ren start, på två datorer | Stegen ovan, och tabellen nedan |

## Verifieringsprotokoll (fylls i per dator)
| Dator | Operativsystem | Python | Datum | Resultat från `verify_flow` | Utfört av |
|---|---|---|---|---|---|
| 1 (ren klon) | Windows (Git Bash) | 3.12.12 | 2026-11-03 | RESULTAT: 7/7 kontroller godkända | Muhammad |
| 2 | – | – | – | Ej utförd | – |

> Verifiering på en andra fysisk dator är inte utförd. Kedjan har körts från en ny klon på dator 1
> och i CI (`test_end_to_end.py`, ren Ubuntu-miljö). Uppföljning: [#76](https://github.com/muhaka-1/smart-env-monitoring/issues/76).

### Om API:t kräver inloggning (efter #62/#65)
Historik är skyddad med Django-session. Logga in med ett testkonto:
```bash
VERIFY_USERNAME=anna python -m tools.verify_flow --base-url http://localhost:8001
```
Lösenordet frågas efter (eller sätt `VERIFY_PASSWORD`). Utan konto körs verifieringen anonymt.
