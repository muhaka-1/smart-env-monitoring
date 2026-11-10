# Gemensam e-posttjänst

Issue #67 ger gemensam konfiguration, leverans och svenska textmallar för kontoinbjudan, lösenordsåterställning och datavarning. Tjänsten använder Djangos SMTP-backend. `python-dotenv` läser den lokala konfigurationen.

Konton, inloggning, token, giltighetstid, omskickade inbjudningar, mottagarurval och sparade varningar hanteras i respektive issue (#62–#64 och #68). Tjänsten skapar inga konton eller varningar och har inga egna URL-routes. Inbjudningsmallen beskriver tredagarsregeln; #64 måste faktiskt verkställa den.

## Konfiguration

Lägg SMTP-uppgifterna i `.env` i projektroten (bredvid `.env.example`, inte i `backend/`). Filen läses när Django startar, oavsett aktuell arbetskatalog. Den är ignorerad av Git. Processens befintliga miljövariabler har företräde och `${...}` expanderas inte i filens värden. Starta om Django efter ändringar.

Installera backendberoendena med `python -m pip install -r backend/requirements.txt`. Kopiera `.env.example` till `.env` om den lokala filen inte redan finns. Fyll i SMTP-värd, inloggning, nyckel och verifierad avsändare. Lägg aldrig den riktiga nyckeln i `.env.example` eller `settings.py`.

| Variabel | Lokalt standardvärde | Betydelse |
| --- | --- | --- |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` | SMTP i applikationen; minnesbackend används isolerat i automatiska tester |
| `EMAIL_HOST` | `localhost` | SMTP-värd |
| `EMAIL_PORT` | `25` | SMTP-port |
| `EMAIL_HOST_USER` | tomt | SMTP-användare |
| `EMAIL_HOST_PASSWORD` | tomt | SMTP-lösenord eller SMTP-nyckel |
| `EMAIL_USE_TLS` | `0` | `1` för STARTTLS, annars `0` |
| `EMAIL_USE_SSL` | `0` | `1` för implicit TLS, annars `0`; kombinera inte med STARTTLS |
| `EMAIL_TIMEOUT` | `10` | SMTP-timeout i sekunder |
| `DEFAULT_FROM_EMAIL` | `no-reply@example.com` | Avsändare; byt till en godkänd adress hos SMTP-leverantören |
| `PLATFORM_BASE_URL` | `http://127.0.0.1:8000` | Plattformens HTTP(S)-adress, eventuellt med sökvägsprefix |

SMTP är standard; inget meddelande skrivs automatiskt till terminalen om leveransen misslyckas. Sätt värd, port, autentisering och TLS enligt leverantörens instruktioner. För Brevo används `smtp-relay.brevo.com`, port `587`, `EMAIL_USE_TLS=1` och `EMAIL_USE_SSL=0`. Använd SMTP-login och SMTP-nyckel från samma Brevo-konto, en verifierad avsändare och en auktoriserad utgående IP-adress om IP-blockering är aktiverad.

Använd `PLATFORM_BASE_URL=http://127.0.0.1:8000` för länkar som öppnas på samma utvecklingsdator. I drift ska basadressen vara plattformens riktiga HTTPS-adress. Lägg aldrig autentiseringsuppgifter i Git. SMTP-transporten är inte bunden till en viss leverantör.

## Konfigurationskontroll vid start

Djangos systemkontroller stoppar `runserver` vid saknad SMTP-värd, inloggning eller nyckel, lokala/exempelvärdar, saknad eller motstridig TLS/SSL, ogiltig port eller timeout samt saknad eller ogiltig avsändare. Felen visar inställningarnas namn utan deras värden. Kör `python backend/manage.py check --tag email` för samma kontroll. Kontrollen gör inget nätverksanrop och bevisar inte att nyckeln eller avsändaren godkänns av leverantören.

SMTP är fortfarande standard. CI använder uttryckligen minnesbackend för kontroller och tester utan riktiga nycklar eller utskick. Även andra startmetoder än `runserver` ska köra `manage.py check` före trafik; `django.setup()` ensamt kör inte systemkontrollerna.

## Anrop från andra funktioner

```python
from monitoring.emails import EmailDeliveryError, send_platform_email

send_platform_email(
    "user@example.com",
    "invitation",
    action_path=activation_path,
)
```

`activation_path` kommer från kontoflödet, exempelvis genom `reverse()` med dess skapade token. Anroparen skickar en lokal sökväg som börjar med `/`, inklusive eventuell URL-kodad query. Tjänsten lägger till `PLATFORM_BASE_URL`; externa adresser avvisas. Med basen `https://example.com/platform` och sökvägen `/activate/.../` blir länken `https://example.com/platform/activate/.../`.

| `kind` | Obligatorisk `context` |
| --- | --- |
| `invitation` | Ingen; aktiveringslänken ges som `action_path` |
| `password_reset` | Ingen; återställningslänken ges som `action_path` |
| `data_alert` | `sensor_id`, `metric`, `timestamp`, `value`, `unit`, `threshold`, `status` |

Varje anrop skickar till en mottagare, så användares e-postadresser exponeras inte för andra mottagare. Data i `context` visas som vanlig text. Användaren av tjänsten ansvarar för att länken leder till rätt funktion och att destinationen kontrollerar behörighet och token. #63 använder Djangos återställningsflöde med denna tjänst, se [`password.md`](password.md); inbjudningar till konton utan användbart lösenord behöver det separata flödet i #64.

En lyckad leverans till vald backend returnerar `None`. SMTP- och nätverksfel, eller noll skickade meddelanden, loggas med meddelandetyp och ger `EmailDeliveryError` med en neutral feltext. Innehåll, mottagare, token och serverns feltext loggas inte. Validerings- och konfigurationsfel avvisas före leverans. Anroparen hanterar felet utan att rapportera falsk framgång. #68 ansvarar för att mätningen och varningen bevaras vid leveransfel samt för leveransstatus och eventuell återförsökning.

## Verifiera SMTP

När `.env` är ifylld, starta Django och begär lösenordsåterställning för ett aktivt konto med användbart lösenord och en e-postadress som du kontrollerar. Kontrollera att meddelandet når inkorgen eller skräpposten och att länken öppnar den lokala plattformen. En neutral bekräftelse i gränssnittet bevisar inte att mejlet levererades; granska även leveransfel i serverloggen och leverantörens leveransstatus. Loggar ska inte innehålla nycklar eller återställningslänkar.

För en separat kontroll av transporten kan följande köras i Djangos shell, med en egen mottagaradress:

```python
from django.core.mail import send_mail

send_mail(
    "SMTP-test",
    "Detta är ett test av projektets e-postleverans.",
    None,
    ["din-egen-mottagaradress@example.com"],
    fail_silently=False,
)
```

Detta skickar ett riktigt testmejl när mottagaradressen har bytts ut. Ett returvärde på `1` betyder att SMTP-servern accepterade meddelandet, inte att det säkert nådde inkorgen. Testet ändrar inget konto eller lösenord.

Automatiska tester:

```powershell
python -B backend/manage.py test monitoring.tests.test_emails
python -B backend/manage.py test monitoring.tests
```

Testerna använder Djangos minnesbackend eller simulerad SMTP och skickar inget till externa mottagare. De kontrollerar mottagare, ämne, mallinnehåll, länkar, laddning av `.env`, miljövariablernas företräde och säkra leveransfel utan reservleverans. Det verifierar inte leverans till en riktig inkorg; verklig SMTP-leverans kontrolleras separat med det konfigurerade kontot.
