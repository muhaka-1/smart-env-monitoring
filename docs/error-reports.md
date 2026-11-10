# Felrapport på skärm och som PDF (#69)

Rapporten visar användarens sparade varningar från #68. Den ändrar inte
gränsvärden, statuslogik, e-postleverans eller kontoflöden och skapar inga nya
varningar för äldre data. Ingen migration eller ny dependency behövs.

## Åtkomst och data

- `/reports/errors/`: inloggningsskyddad skärmrapport, nås via **Felrapport** i
  dashboarden och på meddelandesidan.
- `/api/reports/errors.pdf`: sessionsskyddad PDF-export. Anonyma besökare
  skickas till inloggning även vid direkt URL-anrop.
- Båda är skrivskyddade GET-vyer med cacheförbud. Varje fråga begränsas till
  `Alert` som har en `Notification` för den inloggade användaren. Andra användares
  poster och sensorer exponeras inte. En varning med flera mottagare visas bara
  en gång per användare.
- Kolumnerna är sensor-ID, mätstorhet, mättid, värde, enhet, sparat gränsvärde och
  status. Uppgifterna hämtas från varningens snapshot, inte från dagens
  konfiguration eller en senare ändrad mätning.

## Gemensamma filter

`sensor_id`, `start` och `end` används av samma frågelogik för skärm och PDF.
Sensorn kan lämnas tom för alla egna sensorer. Tidsgränserna är valfria och
inkluderande och gäller mättiden, inte meddelandets skapandetid. Gränser utan
tidszon tolkas som UTC; ISO 8601 med offset normaliseras till UTC. UI och PDF
anger UTC uttryckligen. Ogiltig sensor, tid eller omvänt intervall ger HTTP 400
med begripligt formulärfel.

Skärmen visar 20 händelser per sida, nyaste mättid först med ID som stabil
sekundär sortering. PDF innehåller **alla** matchande händelser i samma ordning,
utan dold radbegränsning. Sidindelning och export behåller filtren. En dold
`as_of`-gräns för varningens lagringstid följer med länkarna så att nya inkommande
varningar inte ändrar urvalet mellan visning och export. Nollställ öppnar ett
nytt urval. Ogiltiga skärmsidnummer ger HTTP 404.

Tomma resultat förklaras både på skärm och i PDF. PDF visar valt sensorfilter,
tidsintervall, UTC-tid för rapportens skapande, antal händelser och sidnummer.
Liggande A4, upprepade kolumnrubriker och radbrutna celler används för längre
sensor-ID. Innehållstypen är `application/pdf` och filnamnet `felrapport.pdf`.

## Verifiering

```powershell
python -B backend/manage.py test monitoring.tests.test_error_reports
```

Testerna täcker direkt och inaktiv åtkomst, användarisolering, sensorval,
tidsgränser/offset, snapshots, validering, tomt resultat, sidindelning, fullständig
PDF-export och oförändrat urval vid nytillkomna händelser. Rapportläsning ska
varken skriva händelser eller skicka e-post.

Kontrollera även rapporten visuellt vid mobil-, mellan- och datorbredd samt PDF
med flera sidor, båda mätstorheterna, långa sensor-ID och tomt resultat. SMTP,
automatiska omskick och nya typer av dataproblem ligger utanför #69.
