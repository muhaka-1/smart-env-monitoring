# PDF-rapport för historiska mätvärden

Det här dokumentet beskriver PDF-exporten för issue #66.

## Åtkomst

- Endast inloggade användare kan skapa en PDF-rapport.
- Obehöriga användare skickas till inloggningssidan.
- Admin-knappen visas endast för användare med personalstatus.

## Användning

1. Logga in på dashboarden.
2. Öppna Historik och välj plats och mätstorhet.
3. Välj ett snabbintervall eller ange start- och sluttid.
4. Klicka på **Ladda ned PDF**.

Rapporten använder samma sensor- och tidsfilter som historikdiagrammet. Den innehåller **högst de senaste 200 matchande mätningarna**, sorterade i stigande tidsordning. PDF-titel och innehåll anger begränsningen, antalet inkluderade och totalt matchande rader samt antalet utelämnade. Rapporten gör därför inte anspråk på att alltid innehålla hela perioden.

## Rapportens innehåll

Rapporten visar:

- sensor-ID,
- mätstorhet,
- valt tidsintervall,
- rapportens skapandetid,
- mätningarnas tid, värde, enhet och status.

Alla tider i PDF (periodens gränser, rader och skapandetid) anges uttryckligen i **UTC**, oavsett serverns tidszonsinställning. ISO 8601 med offset omvandlas till UTC, och tider utan zon tolkas som UTC. Webbläsarens datumfält och diagram använder lokal tid och skickar ISO-tider med tidszon.

Om intervallet saknar mätvärden visas ett begripligt tomt resultat. Historik-PDF är separat från felrapportens PDF, som innehåller alla matchande händelser.

## Verifiering

- Automatiska tester kontrollerar autentisering, filter, PDF-svar, filnamn och centralt innehåll.
- Turbiditet och temperatur har kontrollerats.
- PDF med flera tabellrader har kontrollerats visuellt.
- Text och tabeller klipps eller överlappar inte.
- PDF-knappen har kontrollerats på mobil-, mellan- och datorbredd.
