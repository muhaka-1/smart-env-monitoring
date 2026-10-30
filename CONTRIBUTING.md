# Bidra till projektet

Det här dokumentet beskriver teamets gemensamma arbetssätt. Målet är små, granskbara ändringar som kan integreras utan att arbete skrivs över.

## Teamets huvudområden

| Person | Huvudområde | Vanliga filer |
|---|---|---|
| Pat | Frontend, UX, dashboard, dokumentation och demo | `backend/monitoring/templates/`, `backend/monitoring/static/`, `docs/`, `README.md` |
| Muhammad | Simulator, dataset, MQTT/HTTP-kommunikation och lokal start | `sensor/`, `infra/`, `docker-compose.yml` |
| Khaled | Backend, datamodell, validering, REST-API och backendtester | `backend/monitoring/models.py`, `serializers.py`, `services.py`, `views.py`, `tests/`, `migrations/` |

Huvudansvar betyder samordningsansvar, inte ensamrätt till filer. Den som behöver ändra någon annans område meddelar personen först och ber om granskning i PR:n.

## Grenflöde

```text
feature/* → development → Testing → main
```

| Gren | Syfte | Ändras genom |
|---|---|---|
| `feature/*` | En avgränsad issue eller nära relaterade issues | Egna commits |
| `development` | Integration av färdiga funktioner | PR från `feature/*` |
| `Testing` | Samlad verifiering inför release | PR från `development` |
| `main` | Stabil och inlämningsbar version | PR från `Testing` |

Push aldrig direkt till `development`, `Testing` eller `main`. Observera att `Testing` skrivs med stort T.

## Starta ett arbete

Utgå alltid från senaste `development`:

```bash
git switch development
git pull --ff-only origin development
git switch -c feature/<kort-beskrivning>
```

Alla nya arbetsgrenar använder prefixet `feature/`, även när ändringen främst är en fix eller dokumentation.

Exempel:

- `feature/mqtt-consumer`
- `feature/dashboard-history-filter`
- `feature/clean-readme-contributing`

Koppla normalt en PR till en huvudissue. Flera issues får kombineras endast när de är nära beroende av varandra och PR-beskrivningen visar vad som hör till varje issue.

## Under arbetet

Gör små commits med formatet:

```text
typ(scope): kort beskrivning
```

Vanliga typer är `feat`, `fix`, `test`, `docs`, `refactor` och `chore`.

Exempel:

```text
feat(sensor): add MQTT publisher
fix(api): validate reading date range
test(dashboard): cover anomaly markers
docs: align README with current MVP
```

Synkronisera en längre arbetsgren utan att skriva över andras arbete:

```bash
git fetch origin
git merge origin/development
```

Lös eventuella konflikter lokalt och kör testerna igen innan du pushar.

## Delade filer som kräver samordning

Meddela teamet innan större ändringar i:

- `README.md`, `CONTRIBUTING.md` och `docs/SPRINT_PLAN.md`,
- `backend/monitoring/models.py` och migrationsfiler,
- `backend/monitoring/templates/monitoring/dashboard.html`,
- `backend/monitoring/static/monitoring/dashboard.js`,
- `.github/workflows/ci.yml`.

Skapa aldrig en ny migration utan att först kontrollera befintliga migrationsfiler. Genererade migrationer ska alltid committas tillsammans med modelländringen.

## Tester före en PR

Från projektets rot, med den virtuella Python-miljön skapad enligt README:

```powershell
.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe backend\manage.py test monitoring
Set-Location sensor
..\.venv\Scripts\python.exe -m unittest discover -s tests -t .
Set-Location ..
node backend\monitoring\tests\dashboard.test.cjs
```

Kör minst de tester som berör ändringen. Före en release-PR ska hela sviten vara grön.

För en synlig dashboardändring ska dator-, mellan- och mobilbredd kontrolleras, till exempel cirka 1400, 1024 och 390 pixlar. Lägg gärna skärmbilder i PR:n när layouten ändras.

## Pull request

En PR ska:

- ha `development` som bas för en feature-gren,
- ha en kort titel som förklarar resultatet,
- länka relevanta issues med exempelvis `Closes #25` eller `Refs #30`,
- beskriva vad som ändrats och varför,
- redovisa automatiska och manuella tester,
- nämna kända begränsningar eller återstående arbete,
- begära granskning från minst en annan teammedlem.

Använd `Closes #...` bara när hela issuens checklista är verifierad. Annars används `Refs #...`, och issuen lämnas öppen.

### Kontrollista

- [ ] Ändringen är avgränsad och innehåller inga orelaterade filer.
- [ ] Berörda tester är gröna.
- [ ] `makemigrations --check --dry-run` rapporterar inga nya migrationer.
- [ ] Dokumentationen stämmer med faktisk funktion.
- [ ] Synliga ändringar är kontrollerade på relevanta skärmstorlekar.
- [ ] CI är grön.
- [ ] Minst en teammedlem har granskat.

## Merge-strategi

- `feature/*` till `development`: **Squash and merge**.
- `development` till `Testing`: vanlig merge commit så integrationshistoriken bevaras.
- `Testing` till `main`: vanlig merge commit efter gemensam verifiering.

Stäng inte en PR utan merge om ändringen ska behållas. Om PR:n ersätts av en annan ska det förklaras och den nya PR:n länkas.

## Release och demo

Inför `development → Testing`:

1. Kör hela testsviten.
2. Prova HTTP-flödet från simulator till dashboard.
3. Prova MQTT-flödet om sprintens mål kräver det.
4. Kontrollera dashboard på dator och mobil.
5. Kontrollera att README-kommandona fortfarande fungerar.
6. Dokumentera resultat och eventuella avvikelser i PR:n.

`Testing → main` görs först när teamet har verifierat den samlade versionen och inga blockerande fel återstår.
