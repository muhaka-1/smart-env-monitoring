# Användartest med medborgarperspektiv

Det här protokollet hör till issue #28. Syftet är att kontrollera att en person
utan teknisk projektkunskap kan förstå dashboardens senaste mätvärden, status
och historik.

## Teststatus

- Expertgranskning genomförd: 2026-11-05.
- Prioriterade förbättringar implementerade på `feature/28-user-test`.
- Test med en extern deltagare återstår innan issue #28 kan stängas.

## Förberedelser

1. Starta Django och simulatorn så att dashboarden innehåller flera platser och
   mätvärden.
2. Öppna dashboarden i en webbläsare på dator eller mobil.
3. Ge inte deltagaren en rundtur före testet.
4. Be deltagaren tänka högt och notera var hen tvekar.

## Uppgifter till deltagaren

Läs upp en uppgift i taget utan att peka ut rätt kontroll.

1. Hitta vilken plats som har den senaste avvikelsen.
2. Förklara med egna ord vad **OK** och **Avvikelse** betyder. Fråga därefter om
   statusen är ett badråd.
3. Hitta det senaste turbiditetsvärdet för Oak Street Beach.
4. Visa historiken för en annan plats och välj senaste dygnet.
5. Välj ett eget tidsintervall och återställ sedan filtret.
6. Förklara vad varningen om en inaktuell mätning betyder.

## Observationsmall

| Uppgift | Klar utan hjälp | Tid eller hjälp | Observation eller citat | Allvar |
| --- | --- | --- | --- | --- |
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 |  |  |  |  |
| 5 |  |  |  |  |
| 6 |  |  |  |  |

Använd allvarlighetsgraderna hög, medel och låg. Ett högprioriterat problem
hindrar en central uppgift eller kan ge en felaktig tolkning av informationen.

## Expertgranskning 2026-11-05

| Observation | Prioritet | Åtgärd |
| --- | --- | --- |
| Tekniska sensor-ID:n var den tydligaste platsangivelsen. | Hög | Korten visar nu läsbara platsnamn och sensorns ID som sekundär information. |
| Ordet `ANOMALY` krävde teknisk förkunskap. | Hög | Informationstexten använder nu **Avvikelse** och förklarar tydligt att statusen inte är ett badråd. |
| Historikdelen saknade rubrik och instruktion. | Medel | En rubrik och en kort vägledning har lagts till före filtren. |
| Status visades redan med både symbol och text. | Bra | Behålls eftersom betydelsen inte är beroende av enbart färg. |
| Fel, tom historik och blandade mätstorheter hade tydliga meddelanden. | Bra | Behålls och täcks av automatiska tester. |

## Resultat från deltagartest

Fylls i efter testet:

- Datum:
- Deltagare och relevant bakgrund:
- Enhet och skärmstorlek:
- Uppgifter klara utan hjälp:
- Viktigaste observation:
- Prioriterad åtgärd eller länk till ny issue:

## Klart för att stänga issue #28

- [ ] Minst en person har genomfört de definierade uppgifterna.
- [x] Observationer och expertgranskning är dokumenterade.
- [x] Minst en prioriterad förbättring är implementerad.

Issue #28 ska vara öppen tills den första rutan kan markeras med ett verkligt
testunderlag.
