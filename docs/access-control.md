# Publik och skyddad åtkomst

Det här dokumentet beskriver åtkomstmodellen för issue #65 och PR #71. Målet är att den publika dashboarden ska visa aktuella mätvärden utan konto, medan historik och kommande användarfunktioner skyddas på serversidan.

## Åtkomstmatris

| Funktion eller endpoint | Publik användare | Inloggad användare | Skydd |
| --- | ---: | ---: | --- |
| `GET /` och senaste sensorkort | Ja | Ja | Publik Django-vy |
| `GET /api/readings/latest/` | Ja | Ja | Publikt senaste-värde-API |
| `GET /api/sensors/` | Ja | Ja | Publik sensorlista; den publika dashboarden anropar den inte |
| `GET`/`HEAD /api/readings/` | Nej | Ja | Django-session och DRF `IsAuthenticated` |
| `POST /api/readings/` | Sensorflöde | Sensorflöde | Valfri `INGEST_API_KEY`, inte användarsession |
| Historikpanel och tidsfilter | Nej | Ja | Renderas endast för autentiserad användare |
| Sparade meddelanden och varningar | Nej | Planerat | Implementeras och verifieras i #68 |
| Historik-PDF | Nej | Planerat | Implementeras och verifieras i #66 |
| Felrapport på skärm och som PDF | Nej | Planerat | Implementeras och verifieras i #69 |

Ett nekande svar från historik-API:t ska vara HTTP 401 eller 403 beroende på autentiseringsklass och klient. Det viktiga är att ingen historikdata returneras.

## Serverskydd och webbläsarbeteende

- Dashboardmallen renderar inte historikpanelen för en anonym användare.
- JavaScript läser `data-can-view-history` och gör inga anrop till sensorlistan eller historik-API:t för en anonym användare.
- `GET` och `HEAD /api/readings/` kontrolleras på serversidan. Det går därför inte att kringgå skyddet genom att ändra CSS eller JavaScript i webbläsaren.
- `POST /api/readings/` är separerat från användarinloggningen eftersom simulatorn är en maskinklient. När `INGEST_API_KEY` är konfigurerad måste klienten skicka den i `X-API-Key`.
- Senaste värde förblir offentligt eftersom det är innehållet i den publika dashboarden.

## Inloggning och navigation

PR #71 visar om dashboarden är publik eller autentiserad men skapar inte själva inloggnings- och utloggningsvyerna. Issue #62 och PR #74 ansvarar för:

- `/accounts/login/`,
- POST-baserad `/accounts/logout/`,
- säker hantering av `next`,
- synliga kontroller för **Logga in** och **Logga ut**.

PR #74 ska mergas före den slutliga integrationen av PR #71. Efter integrationen ska en anonym användare kunna gå till inloggningssidan och en inloggad användare kunna avsluta sessionen från dashboarden.

## Automatiska kontroller

Kör från projektroten:

```powershell
python backend\manage.py test monitoring
node backend\monitoring\tests\dashboard.test.cjs
python backend\manage.py makemigrations --check --dry-run
```

`backend/monitoring/tests/test_access_control.py` verifierar bland annat:

- att senaste-värde-vyn är publik,
- att historikpanelen saknas i anonym HTML,
- att anonym `GET` och `HEAD` mot historik-API:t nekas,
- att en inloggad användare kan läsa historik,
- att ingest-flödet fortfarande använder API-nyckelregeln.

## Manuell kontroll före stängning av #65

1. Öppna `/` utan session och kontrollera att senaste värden visas men att historikpanelen saknas.
2. Öppna `/api/readings/` utan session och kontrollera 401/403 utan mätdata.
3. Logga in med ett lokalt testkonto och kontrollera att historik, sensorval och tidsfilter visas.
4. Kontrollera att historik-API:t returnerar 200 efter inloggning.
5. Logga ut via POST och kontrollera att historiken åter blir otillgänglig.
6. Upprepa dashboardkontrollen vid cirka 390, 1024 och 1400 pixlars bredd.
7. När #66, #68 och #69 finns: upprepa samma kontroll för historik-PDF, meddelanden och felrapporter.

Issue #65 stängs först när alla beroenden är integrerade, hela testsviten är grön och den visuella kontrollen är dokumenterad.
