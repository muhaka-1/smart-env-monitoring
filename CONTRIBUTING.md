# Arbetssätt (Development Workflow)

## Grenar
```
feature/*  →  development  →  testing  →  main
```

| Gren | Syfte | Hur ändras den |
|---|---|---|
| `feature/*` | Ett avgränsat arbete (en funktion eller fix) | Direkt av utvecklaren |
| `development` | Integration av färdiga features | Pull Request från `feature/*` (squash and merge) |
| `testing` | Verifiering innan release | Pull Request från `development` (merge commit) |
| `main` | Stabil, inlämningsbar version | Pull Request från `testing` (merge commit) |

Ingen pushar direkt till `development`, `testing` eller `main`.

## Dagligt arbete
```bash
git checkout development && git pull
git checkout -b feature/<kort-beskrivning>
# ... arbeta, committa ofta ...
git push -u origin feature/<kort-beskrivning>
```
Öppna en Pull Request mot `development`, be en kollega granska, merga och radera grenen.
Håll grenen uppdaterad: `git fetch origin && git merge origin/development`.

## Namngivning av grenar
`feature/sensor-turbidity`, `feature/mqtt-retry`, `fix/api-validation`, `docs/architecture`.

## Commit-meddelanden
Format: `typ(scope): beskrivning` i imperativ, gemener, utan punkt.

**Typer:** `feat`, `fix`, `test`, `docs`, `refactor`, `chore`

**Scopes:**
| Scope | Modul |
|---|---|
| `sensor`, `firmware` | 1. ESP32-sensor |
| `mqtt`, `http` | 2. Datakommunikation |
| `api`, `backend` | 3. Backend / API |
| `database` | 4. Databas |
| `dashboard` | 5. Frontend |

**Exempel:**
```
feat(sensor): add sensor simulator
feat(mqtt): add MQTT publisher
feat(api): add readings endpoint
feat(database): add time-series reading model
feat(dashboard): add monitoring chart
fix(mqtt): retry transient errors
test(api): add readings tests
docs: update IoT architecture
```

## Ansvarsfördelning
| Ansvarig | Moduler | Främst filer |
|---|---|---|
| Muhammad | 1 ESP32-sensor, 2 Datakommunikation, 3 Backend/API | `sensor/`, `firmware/`, `mqtt_consumer.py`, `services.py`, `serializers.py`, `views.py`, `urls.py` |
| Pat | 4 Databas, 5 Frontend/Dashboard | `models.py`, `migrations/`, `admin.py`, `templates/`, `static/` |

**Regler för att undvika konflikter**
- Bara databasansvarig ändrar `models.py` och skapar migrationer. Behövs ett nytt fält, be om det i en issue eller PR.
- Committa alltid genererade migrationer och kör `python manage.py makemigrations --check` före PR.
- Kör `git pull` på `development` innan du skapar en ny feature-gren.

## Innan du öppnar en Pull Request
```bash
cd backend && python manage.py test
cd ../sensor && python -m unittest discover -s tests -t .
```
CI kör samma tester automatiskt, och en PR med röda tester ska inte mergas.

## Release
1. `development` → `testing`: kör tester och prova hela flödet (sensor → API → dashboard).
2. `testing` → `main`: när allt är verifierat. Sätt gärna en tagg: `git tag v1.0.0 && git push --tags`.
