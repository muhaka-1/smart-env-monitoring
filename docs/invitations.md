# Administratörsskapade konton och inbjudningar (#64)

Konton skapas i Django admin, inte via publik registrering. Befintliga konton och
lösenordsåterställningen från #63 behåller sitt tidigare beteende.

## Administratör

1. Logga in på `/admin/` med behörighet att lägga till och ändra användare.
2. Under Användare, välj Lägg till och ange ett unikt användarnamn och en giltig
   e-postadress som inte redan används av ett konto.
3. Spara. Kontot skapas inaktivt med ett oanvändbart lösenord. Efter att
   databastransaktionen har sparats skickas inbjudan via `send_platform_email` och
   den befintliga mallen `monitoring/emails/invitation.txt`. Mejlet innehåller även
   användarnamnet som mottagaren ska logga in med.
4. Vid leveransfel visas ett felmeddelande. Kontot finns kvar inaktivt. Markera
   användaren i listan och välj **Skicka ny inbjudan** för att försöka igen.

Samma åtgärd används när länken har gått ut. Varje omskick skapar en ny länk och
ogiltigförklarar den tidigare, även om den redan är öppen i en webbläsare.
Aktiva konton eller konton med ett användbart lösenord bjuds inte in på nytt.
Administratören kan inte aktivera ett väntande konto eller sätta dess lösenord
via de vanliga ändringsformulären; mottagaren ska först slutföra inbjudan.

## Inbjudningsstatus (#95)

Användarlistan i admin har kolumnen **Inbjudan**:

| Status | Betydelse |
| --- | --- |
| Skickad, giltig till … | E-posttjänsten har accepterat utskicket och länken kan användas |
| Utgången | Länken är äldre än 72 timmar; använd *Skicka ny inbjudan* |
| Ej skickad (leveransfel) | Utskicket misslyckades. Länken har gjorts oanvändbar; skicka ny inbjudan |
| Ingen inbjudan | Inaktivt konto utan lösenord som aldrig har bjudits in |
| Aktiverad | Mottagaren har valt lösenord |
| – | Konton som inte skapats via inbjudan |

`AccountInvitation.sent_at` sätts först när `send_platform_email` har lyckats, och de 72 timmarna räknas från det
bekräftade utskicket (`issued_at` uppdateras då). Misslyckas utskicket töms token och `sent_at` förblir tomt, så en
länk som mottagaren aldrig fick kan inte användas. Ett omskick som misslyckas ogiltigförklarar också den tidigare länken.
Statusen avslöjar aldrig SMTP-felets text. Migreringen `0005_accountinvitation_sent_at` sätter `sent_at` på befintliga
inbjudningar till `issued_at`.

## Mottagare och säkerhet

- `/accounts/invite/<uidb64>/<token>/` kontrollerar länken och flyttar token till
  sessionen innan lösenordsformuläret visas. Formuläret har CSRF-skydd och använder
  samma lösenordsvalidering som lösenordsåterställningen.
- Länken gäller i **72 timmar** från senaste utskicksförsöket, oberoende av
  `PASSWORD_RESET_TIMEOUT`. Vid exakt 72 timmar har länken gått ut.
- Token innehåller 32 kryptografiskt slumpade byte. Databasen lagrar endast en
  SHA-256-digest knuten till mottagaradressen. Ändrad e-postadress ogiltigförklarar
  också den gamla länken; skicka då en ny inbjudan.
- Vid giltig POST förbrukas länken och ett hashat lösenord sparas tillsammans med
  `is_active=True` i samma transaktion. En villkorad uppdatering hindrar att två
  inskick förbrukar samma länk. Användaren loggas inte in automatiskt.
- Ogiltiga, utgångna och använda länkar visar ett begripligt meddelande som
  hänvisar till administratören. Ett inaktivt konto utan lösenord kan inte kringgå
  inbjudan via glömt-lösenord-flödet.

## SMTP och verifiering

Inbjudningar använder samma `EMAIL_*`, `DEFAULT_FROM_EMAIL` och `PLATFORM_BASE_URL`
som den gemensamma e-posttjänsten. Ingen separat leveransimplementation eller
leverantör införs. SMTP-konfiguration och `.env`-inläsning hanteras av SMTP-arbetet
i PR #79; hemligheter ska inte checkas in. `PLATFORM_BASE_URL` ska peka på den
plattform mottagaren faktiskt kan nå (HTTPS i drift).

Ny migration: `0003_accountinvitation`. Den lägger till en separat tabell och
ändrar inte befintliga användare eller mätningar. Kör `python backend/manage.py migrate`
innan flödet används i en egen lokal databas.

```powershell
python -B backend/manage.py test monitoring.tests.test_invitations
```

Testerna körs med isolerad databas och minnesbaserad e-post. SMTP-testet använder
Djangos riktiga SMTP-backend med ersatt nätverksanslutning för att kontrollera
STARTTLS, autentisering och meddelandeinlämning. Det bevisar integrationen men inte
leverans till en verklig inkorg.
