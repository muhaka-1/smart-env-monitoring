# Validering, förhandsgranskning och dubblettkontroll vid kontoimport (#94)

Administratörer med behörigheten *lägga till användare* kan importera konton från en CSV-fil under
**Admin → Användare → Importera konton** (`/admin/auth/user/import/`).

## Filformat

UTF-8 (BOM tillåten), komma eller semikolon som avgränsare, rubrikrad med `username` och `email`
(även `användarnamn` och `e-post`). Högst 1 MB och 500 rader. Helt tomma rader ignoreras.

## Flöde

1. **Ladda upp.** Filen kontrolleras men ingenting sparas.
2. **Förhandsgranska.** Varje rad visas med radnummer, värden och resultat. Antal giltiga och ogiltiga rader
   står överst. Felen skrivs ut per rad.
3. **Bekräfta.** Först nu skapas konton, och bara av de giltiga raderna. Raderna med fel hoppas över.
   Kontona skapas inaktiva utan lösenord och får en inbjudan via samma flöde som #64.
   Kontrollen görs om vid bekräftelse, så konton som tillkommit sedan förhandsgranskningen leder inte till dubbletter.

## Vad som kontrolleras

| Kontroll | Fel |
| --- | --- |
| Obligatoriska fält | Användarnamn eller e-postadress saknas |
| E-postformat | E-postadressen är ogiltig (eller längre än 254 tecken) |
| Användarnamn | Tillåtna tecken enligt Django, högst 150 tecken |
| Dubblett mot befintliga konton | Användarnamn eller e-post används redan (skiftlägesokänsligt) |
| Dubblett inom filen | Senare rad markeras och pekar på första förekomsten |

Om filen inte går att tolka (fel kodning, saknade kolumner, tom, för stor) visas ett felmeddelande och ingen rapport.
Efter importen visas antal skapade konton, antal skickade inbjudningar och vilka som inte kunde skickas. Bestående status per konto syns i kolumnen *Inbjudan* i användarlistan (se [invitations.md](invitations.md)). Kontot finns kvar vid leveransfel och åtgärden *Skicka ny inbjudan* används.

```bash
python -B backend/manage.py test monitoring.tests.test_account_import
```
