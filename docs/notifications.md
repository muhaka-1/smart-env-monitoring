# E-postvarningar och sparade meddelanden (#68)

Nya godkända mätningar från HTTP och MQTT går genom `services.ingest_reading`.
En mätning med backendstatus `ANOMALY` skapar en `Alert`; normal mätning eller
ogiltig indata skapar ingen varning. Gränslogiken och gränsvärdena ändras inte.
Direkt importerad äldre demodata bearbetas inte i efterhand och utlöser inga utskick.

## Lagring och mottagare

- `Alert` har en unik koppling till `Reading` och sparar sensor-ID, mätstorhet,
  mättid, värde, enhet, status och gränsvärdet som användes vid mottagningen.
  Senare ändringar i konfigurationen ändrar inte den sparade varningen.
- Varje aktiv användare vid händelsen får en intern `Notification`, även utan giltig e-post. E-post försöks bara till giltiga adresser; saknad eller ogiltig adress ger `failed` med feltext medan meddelandet och felrapporten finns kvar.
  Inaktiva konton, inklusive ännu inte aktiverade inbjudningar, får inget utskick.
  Meddelandet tillhör den användaren; nya användare får inte äldre varningar automatiskt.
- Databasen tillåter bara en varning per mätning och ett meddelande per varning
  och användare. En avvisad dubblett skickar inte e-post igen.
- Mätning, varning och användarmeddelanden sparas i en transaktion. Om lagringen
  misslyckas rullas den transaktionen tillbaka. E-postförsöken startas via
  `transaction.on_commit` först efter lyckad lagring.
- En mätning med en sparad varning kan inte raderas så att kopplingen förloras
  (`PROTECT`).

## Leverans

Den gemensamma tjänsten `send_platform_email` och befintliga mallen `data_alert`
används med SMTP-inställningarna från #79. Inga nya beroenden införs.

| Status | Betydelse |
| --- | --- |
| `pending` | Sparat, inget e-postförsök har påbörjats |
| `sending` | Ett försök har tagits i anspråk, utfallet är ännu inte bekräftat |
| `sent` | E-postbackend/SMTP-server har accepterat meddelandet, inte bevis på leverans till inkorgen |
| `failed` | Försöket gav ett fel eller mottagaren var inte längre behörig/giltig |

En villkorad statusuppdatering hindrar två anrop från att skicka samma meddelande.
E-postfel sparas som generiska fel utan SMTP-svar, adresser eller hemligheter.
Mätningen, varningen och meddelandet finns kvar vid leveransfel, och fel hos en
mottagare stoppar inte nästa mottagares e-postförsök.

Utskicken sker efter commit i samma process, utan bakgrundskö. Vid avbruten process
kan `pending` eller `sending` finnas kvar. SMTP-timeout kan innebära ett osäkert
leveransutfall; därför återförsöker systemet inte automatiskt. Exakt en leverans
till en extern inkorg kan inte garanteras av SMTP. Köhantering och återförsök ingår
inte i denna issue.

## Läsa meddelanden

- `/messages/`: inloggningsskyddad sida, nås via **Meddelanden** i dashboarden.
- `/api/messages/?page=1`: sessionsskyddad, skrivskyddad API-lista med `count`,
  `page`, `pages` och `results`. Varje post innehåller varningsdata och leveransstatus.
- Båda visar endast den inloggade användarens poster, 20 per sida, nyaste först.
  Andra användares ID eller e-post exponeras inte. Ogiltig API-sida ger HTTP 400;
  anonym API-åtkomst ger HTTP 403. Webbsidan hänvisar anonyma till inloggning.

## Migration och verifiering

`0004_alert_notification` lägger till två tabeller och ändrar inte befintliga
konton, inbjudningar eller mätdata. Kör `python backend/manage.py migrate` innan
funktionen används i en lokal databas.

```powershell
python -B backend/manage.py test monitoring.tests.test_notifications
```

Testerna täcker normalvärden, båda mätstorheterna, HTTP/MQTT, snapshots,
mottagarurval, dubbletter och databasconstraints, transaktioner, leveransfel,
SMTP-integration, behörighet och sidindelning. Använd minnesbackend eller en
isolerad SMTP-mottagare vid tester; kör inte testdata mot riktiga mottagare utan
uttryckligt godkännande. Felrapport på skärm och som PDF är implementerad separat, se [error-reports.md](error-reports.md). Läst/oläst och prenumerationsinställningar ingår inte.
