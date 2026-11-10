# PDF-rapport för historiska mätvärden

Det här dokumentet beskriver PDF-exporten för issue #66.

## Åtkomst

- Endast inloggade användare kan skapa en PDF-rapport.
- Obehöriga användare skickas till inloggningssidan.
- Admin-knappen visas endast för användare med personalstatus.

## Användning

1. Logga in på dashboarden.
2. Välj plats och mätstorhet.
3. Välj ett snabbintervall eller ange start- och sluttid.
4. Klicka på **Ladda ned PDF**.

Rapporten använder samma sensor- och tidsfilter som dashboardens historik.

## Rapportens innehåll

Rapporten visar:

- sensor-ID,
- mätstorhet,
- valt tidsintervall,
- rapportens skapandetid,
- mätningarnas tid, värde, enhet och status.

Om intervallet saknar mätvärden visas ett begripligt tomt resultat.

## Verifiering

- Automatiska tester kontrollerar autentisering, filter, PDF-svar, filnamn och centralt innehåll.
- Turbiditet och temperatur har kontrollerats.
- PDF med flera tabellrader har kontrollerats visuellt.
- Text och tabeller klipps eller överlappar inte.
- PDF-knappen har kontrollerats på mobil-, mellan- och datorbredd.
