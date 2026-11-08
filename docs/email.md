# Gemensam e-posttjänst

Issue #67 ger gemensam konfiguration, leverans och svenska textmallar för kontoinbjudan, lösenordsåterställning och datavarning. Tjänsten använder Djangos e-postbackend utan extra bibliotek.

Konton, inloggning, token, giltighetstid, omskickade inbjudningar, mottagarurval och sparade varningar hanteras i respektive issue (#62–#64 och #68). Tjänsten skapar inga konton eller varningar och har inga egna URL-routes. Inbjudningsmallen beskriver tredagarsregeln; #64 måste faktiskt verkställa den.

## Konfiguration

Variablerna läses från processens miljö. `.env.example` är endast en exempelkonfiguration; Django läser inte automatiskt en `.env`-fil.

| Variabel | Lokalt standardvärde | Betydelse |
| --- | --- | --- |
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` | Console lokalt, locmem i tester eller SMTP för verklig leverans |
| `EMAIL_HOST` | `localhost` | SMTP-värd |
| `EMAIL_PORT` | `25` | SMTP-port |
| `EMAIL_HOST_USER` | tomt | SMTP-användare |
| `EMAIL_HOST_PASSWORD` | tomt | SMTP-lösenord eller SMTP-nyckel |
| `EMAIL_USE_TLS` | `0` | `1` för STARTTLS, annars `0` |
| `EMAIL_USE_SSL` | `0` | `1` för implicit TLS, annars `0`; kombinera inte med STARTTLS |
| `EMAIL_TIMEOUT` | `10` | SMTP-timeout i sekunder |
| `DEFAULT_FROM_EMAIL` | `no-reply@example.com` | Avsändare; byt till en godkänd adress hos SMTP-leverantören |
| `PLATFORM_BASE_URL` | `http://127.0.0.1:8000` | Plattformens HTTP(S)-adress, eventuellt med sökvägsprefix |

För verklig leverans: välj `django.core.mail.backends.smtp.EmailBackend` och sätt värd, port, autentisering och TLS enligt leverantörens instruktioner. Använd plattformens riktiga HTTPS-adress som basadress. Lägg aldrig autentiseringsuppgifter i Git. Inget särskilt SMTP-företag är hårdkodat.

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

## Lokal kontroll utan utskick

PowerShell från projektroten:

```powershell
$env:EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
$env:PLATFORM_BASE_URL = "http://127.0.0.1:8000"
python -B backend/manage.py shell -c "from monitoring.emails import send_platform_email; send_platform_email('user@example.com', 'invitation', action_path='/')"
```

Meddelandet visas i terminalen och skickas inte till en riktig adress. `/` är en befintlig startsida för kontroll av leverans och länkbyggnad, inte ett aktiveringsflöde. Console-utdata innehåller hela meddelandet och är endast för lokal utveckling med testdata; publicera inte utdata som innehåller riktiga länkar eller token.

Automatiska tester:

```powershell
python -B backend/manage.py test monitoring.tests.test_emails
python -B backend/manage.py test monitoring.tests
```

Testerna använder Djangos minnesbackend, fångad console-utdata eller simulerad SMTP och skickar inget över nätverket. De kontrollerar mottagare, ämne, mallinnehåll, länkar, miljökonfiguration och säkra leveransfel. Det verifierar inte leverans till en riktig inkorg; verklig SMTP-leverans kontrolleras separat när kontoflödena integreras.
