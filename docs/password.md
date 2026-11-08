# Glömt lösenord och byte av lösenord (issue #63)

Flödena bygger på Djangos inbyggda vyer i `django.contrib.auth`. Endast leveransen av återställningsmejlet är anpassad och går via den gemensamma e-posttjänsten från #67 (`monitoring/emails.py`). Koden finns i `backend/monitoring/accounts.py` och mallarna i `backend/monitoring/templates/accounts/`.

## Adresser

| Adress | Vy | Kräver inloggning |
| --- | --- | --- |
| `/accounts/password-reset/` | Begär återställning med e-postadress | Nej |
| `/accounts/password-reset/sent/` | Neutral bekräftelse | Nej |
| `/accounts/reset/<uidb64>/<token>/` | Välj nytt lösenord via länken i mejlet | Nej |
| `/accounts/reset/complete/` | Bekräftelse efter återställning | Nej |
| `/accounts/password-change/` | Byt lösenord (kräver nuvarande lösenord) | Ja |
| `/accounts/password-change/done/` | Bekräftelse efter byte | Ja |

Inloggningssidan länkar till *Glömt lösenord?* och dashboarden visar *Byt lösenord* för inloggade användare.

## Säkerhetsegenskaper

- **Neutral bekräftelse.** Formuläret visar alltid samma sida, oavsett om adressen finns, kontot är inaktivt, kontot saknar användbart lösenord eller leveransen misslyckas. Endast aktiva konton med användbart lösenord får mejl (e-postmatchningen är skiftlägesokänslig).
- **Säker, tidsbegränsad token.** Token skapas av `PasswordResetTokenGenerator`, signeras med `SECRET_KEY` och slutar gälla efter `PASSWORD_RESET_TIMEOUT` sekunder (standard 3600 = 1 timme, kan sättas som miljövariabel).
- **Engångsanvändning.** Token bygger på lösenordshashen och senaste inloggning, så den blir ogiltig så fort lösenordet ändras.
- **Token läcker inte via Referer.** Django flyttar token till sessionen och omdirigerar till `/accounts/reset/<uidb64>/set-password/`; sidorna har även `referrer`-policyn `same-origin`, så att adressen inte skickas till andra webbplatser. Använd inte `no-referrer`: då skickar webbläsaren `Origin: null` vid formulärinlämning och Djangos CSRF-kontroll svarar 403.
- **Begripligt fel.** En ogiltig, utgången eller redan använd länk visar *”Återställningslänken är ogiltig, har gått ut eller har redan använts.”* och en länk för att begära en ny.
- **Lösenordsvalidering.** `AUTH_PASSWORD_VALIDATORS` i `settings.py`: minst 10 tecken, inte för likt användarnamn/e-post, inte vanligt lösenord och inte enbart siffror. Gäller både återställning och byte.
- **Inga lösenord i klartext.** Lösenord lagras endast som hash (Djangos standardhasher). Mejlet innehåller bara länken, aldrig något lösenord. Leveransfel loggas utan mottagare eller token.
- **Sessioner.** Vid byte behålls den aktuella sessionen (`update_session_auth_hash`) medan andra sessioner för kontot loggas ut. Efter återställning loggas användaren inte in automatiskt.
- **CSRF.** Alla formulär är POST med CSRF-skydd.

## Lokal kontroll

```powershell
python backend/manage.py migrate
python backend/manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_user('anna', 'anna@example.com', 'Strandlosen-2026')"
python backend/manage.py runserver
```

1. Öppna `http://127.0.0.1:8000/accounts/login/` och välj *Glömt lösenord?*.
2. Ange `anna@example.com`. Med console-backend skrivs mejlet ut i terminalen där servern körs.
3. Öppna länken, välj ett nytt lösenord och logga in med det.
4. Öppna samma länk igen – felmeddelandet ska visas.
5. Logga in, välj *Byt lösenord* på dashboarden och byt lösenordet.

Console-utdata innehåller giltiga återställningslänkar och ska bara användas med testdata.

## Tester

```powershell
python -B backend/manage.py test monitoring.tests.test_password
```

`test_password.py` täcker begäran, neutral bekräftelse (befintlig, okänd, inaktiv och lösenordslös adress samt leveransfel), giltig, ogiltig, använd och utgången token, lösenordsvalidering, hashad lagring, lösenordsbyte (inloggningskrav, fel nuvarande lösenord, svagt lösenord, andra sessioner utloggade) och CSRF.

## Utanför scope

Hastighetsbegränsning av återställningsförfrågningar och skydd mot tidsbaserad uppräkning av konton ingår inte i #63. Inbjudan av konton utan lösenord hanteras i #64.
