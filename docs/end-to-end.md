# Hela kedjan: från ren start till REST-API (issue #21)

```text
Dataset -> Python-simulator -> HTTP (eller MQTT) -> Django -> SQLite -> REST-API (latest + history)
```
Verifieringen använder den riktiga simulatorn mot en riktig server och läser tillbaka varje skickad mätning via API:t.

## Ren lokal start (Windows/Git Bash, samma steg på macOS/Linux)
Kräver Python 3.10+ och Git. Börja i en tom mapp.
```bash
git clone https://github.com/muhaka-1/smart-env-monitoring.git
cd smart-env-monitoring
git checkout development
python -m venv .venv
source .venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
Om `.venv/Scripts/activate` saknas (Python från MSYS/MinGW), använd `source .venv/bin/activate`.
pip install -r backend/requirements.txt
cd backend
python manage.py migrate                 # skapar en tom lokal databas
python manage.py runserver 8001          # lämna terminalen öppen
```
I en **andra terminal** (aktivera `.venv` igen från projektets rotmapp):
```bash
cd sensor
python -m tools.verify_flow --base-url http://localhost:8001
```
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
curl "http://localhost:8001/api/readings/?sensor_id=<sensor_id>&limit=10"      # historik, äldst först
```
Dashboarden visar samma data på `http://localhost:8001/`.

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
> och i CI (`test_end_to_end.py`, ren Ubuntu-miljö). Uppföljning: #<issuenummer>.

### Om API:t kräver inloggning (efter #62/#65)
Historik och data kan vara skyddade med Django-session. Logga då in med ett testkonto:
```bash
VERIFY_USERNAME=anna python -m tools.verify_flow --base-url http://localhost:8001
```
Lösenordet frågas efter (eller sätt `VERIFY_PASSWORD`). Utan konto körs verifieringen anonymt.