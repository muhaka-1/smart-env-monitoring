# AI-funktionalitet (lokal modell)

Plattformen kan använda en **lokal** AI-modell via [Ollama](https://ollama.com). Inget skickas till externa tjänster och det kostar inget. Allt utom avvikelsedetektionen är **avstängt som standard** (`AI_ENABLED=0`) och plattformen fungerar som förut utan modell.

| Funktion | Kräver modell | Beskrivning |
| --- | --- | --- |
| Avvikelsedetektion och sensorfelsmarkering | Nej (statistik) | Markerar mätvärden som misstänkt sensorfel eller statistisk avvikelse |
| Ollama-klient, konfiguration, reservläge | – | Gemensam grund för textfunktionerna |
| "Läget just nu" på dashboarden | Ja, med reservtext | Kort sammanfattning, märkt som AI-genererad |
| Förklaring i avvikelsemejl | Ja, utelämnas annars | Två meningar om värdet och trenden |
| Modelljämförelse | Ja | Kommando som provar flera modeller på samma indata |

## Principer

- **Fakta från data.** Modellen får färdiga värden (sensor, värde, enhet, gräns, status, trend), aldrig fri databasåtkomst. Numeriska svar kontrolleras som hela sensorbundna meningar, inte som en lös mängd tillåtna tal. Innehåller svaret ett annat tal, ett badråd (till exempel "säkert att bada"), är tomt eller för långt används det inte.
- **Alltid en reserv.** Är AI avstängd, långsam, nere eller opålitlig visas en vanlig text byggd på mätdatan (dashboard) eller så utelämnas AI-stycket (mejl). Mejl skickas alltid.
- **Tydlig märkning.** AI-text märks "AI-genererad". Statusen är projektets gränsregel, inte ett badråd.
- **Integritet.** Inga användare, e-postadresser eller andra personuppgifter skickas till modellen. Loggarna innehåller bara feltyp, aldrig prompt eller svar.
- **Paus vid fel.** Efter ett misslyckat anrop pausas AI i `AI_COOLDOWN_SECONDS` så att en nedsläckt modell inte gör sidor eller utskick långsamma.

## Installera Ollama och en modell

1. Installera Ollama från <https://ollama.com/download> (Windows, macOS, Linux).
2. Hämta en liten modell, till exempel: `ollama pull llama3.2:3b`.
3. Kontrollera: `ollama list` ska visa modellen, och `http://127.0.0.1:11434` ska svara "Ollama is running".

Små modeller (1–4 miljarder parametrar) går att köra på en vanlig bärbar dator men kan vara långsamma på CPU och skriva sämre svenska. Se modelljämförelsen nedan.

## Aktivera

Lägg i `.env` i projektroten (se `.env.example`) och starta om servern:

```
AI_ENABLED=1
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
```

| Variabel | Standard | Betydelse |
| --- | --- | --- |
| `AI_ENABLED` | `0` | `1` slår på textfunktionerna |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Endast http/https utan inloggning; annars används standardadressen |
| `OLLAMA_MODEL` | `llama3.2:3b` | Modellnamn enligt `ollama list` |
| `AI_TIMEOUT` | `30` | Sekunder för sammanfattningen |
| `AI_MAIL_TIMEOUT` | `8` | Sekunder för mejlförklaringen (blockerar utskicket) |
| `AI_COOLDOWN_SECONDS` | `60` | Paus efter fel |
| `AI_SUMMARY_CACHE_SECONDS` | `300` | Hur länge en sammanfattning återanvänds |

**Stänga av:** sätt `AI_ENABLED=0` (eller ta bort raden) och starta om. Detektionen fortsätter då, men inga modellanrop görs.

## Avvikelsedetektion (statistik)

Varje ny mätning jämförs med medianen av sensorns 30 senaste mätningar av samma mätstorhet (minst 8 krävs). Skalan är MAD (robust spridning) med en minsta nivå, så jämna serier ger inga falsklarm.

| Utfall | Regel | `quality` |
| --- | --- | --- |
| Misstänkt sensorfel, fastfruset värde | 6 lika värden i rad efter en varierande serie | `suspect` |
| Misstänkt sensorfel, nollvärde | exakt 0 när sensorn annars ligger över 1 | `suspect` |
| Misstänkt sensorfel, orimligt hopp | robust z-värde ≥ 10 | `suspect` |
| Statistisk avvikelse | robust z-värde ≥ 3,5 | oförändrad |

Bedömningen sparas i `ReadingAssessment` och är **skild från gränsvärdet** (`status`). Ett misstänkt sensorfel **stoppar inte** varning eller mejl; mejlet får i stället en vanlig (icke-AI) rad: "Obs: mätvärdet misstänks vara ett sensorfel". Tröskelvärdena finns överst i `backend/monitoring/ai/anomaly.py`.

- API: `GET /api/ai/assessments/?limit=20&sensor_id=…` (kräver en inloggad session).
- Redan sparade mätningar: `python backend/manage.py assess_readings [--sensor ID] [--dry-run]`.
- Dashboarden visar senaste markeringarna under "Datakvalitet".

## "Läget just nu"

`GET /api/ai/summary/` returnerar `text`, `source` (`ai` eller `fallback`), `model`, `ai_enabled` och `generated_at`. Texten följer användarens språk (sv/en/de). AI-texten cachas i `AI_SUMMARY_CACHE_SECONDS`; medan den skapas får övriga förfrågningar den gamla texten eller reservtexten, så sidan blockeras inte.

## Förklaring i mejl

Vid en avvikelse tillägger mejlet (om `AI_ENABLED=1`) en kort förklaring på mottagarens språk. Förklaringen skapas en gång per varning och språk, med den korta tidsgränsen `AI_MAIL_TIMEOUT`. Misslyckas den skickas mejlet utan förklaring.

## Tester

Alla AI-tester mockar Ollama; CI behöver varken Ollama eller modell:

```bash
cd backend
python manage.py test monitoring.tests.test_ai_client monitoring.tests.test_ai_anomaly monitoring.tests.test_ai_summary monitoring.tests.test_ai_mail monitoring.tests.test_ai_compare
```

Manuell provning med riktig modell:

1. `ollama pull llama3.2:3b`, sätt `AI_ENABLED=1`, starta servern och simulatorn.
2. Öppna dashboarden: "Läget just nu" ska visa en text märkt "AI-genererad" (första gången kan det ta en stund).
3. Stäng Ollama: panelen ska visa "Automatisk sammanfattning" med vanlig text och ingen felsida.
4. Skicka ett värde över gränsen (se `docs/api-requests.http`) med `EMAIL_BACKEND` satt till konsolen: mejlet ska innehålla förklaringen, och utan Ollama ska det skickas utan den.

## Modelljämförelse

```bash
python backend/manage.py ai_compare_models --models llama3.2:3b,qwen2.5:3b,gemma2:2b --language sv --output docs/ai-model-comparison.md
```

Kommandot ställer samma tre scenarier (alla OK, gräns överskriden, misstänkt sensorfel) till varje modell och skriver en tabell med svarstid, giltig JSON, att alla tal kommer ur datan, att inget badråd ges och en enkel språkkontroll. Ett uppvärmningsanrop (modellen laddas) görs först och räknas inte. Kolumnen "Manuell bedömning (1–5)" fylls i av teamet efter att ha läst texterna; språkkontrollen ersätter inte en mänsklig bedömning.

### Resultat

> **Ej körd ännu.** Jämförelsen kräver Ollama och modellerna på teamets datorer. Kör kommandot ovan, klistra in tabellen här och skriv en kort slutsats (svenskans kvalitet, hastighet, minnesbehov, vald standardmodell).

| Modell | Medeltid (s) | Godkända kontroller | Slutsats |
| --- | --- | --- | --- |
|  |  |  |  |

## Kända begränsningar

- Detektionen är enkla statistiska regler, inte en tränad modell, och kan missa eller överdriva. Reglerna är gjorda för att vara förklarliga.
- Sammanfattningen kan blockera den enskilda förfrågan som startar en ny generering i upp till `AI_TIMEOUT`; mejlförklaringen kan fördröja utskicket i upp till `AI_MAIL_TIMEOUT` en gång per varning och språk. Bakgrundsjobb vore en förbättring.
- Cachen ligger i processens minne (Djangos standard); flera processer har varsin.
- Ett misstänkt sensorfel undertrycker inte varningar. Vill kommunen det är det ett separat beslut.

### Skydd av historik och aktuellt underlag

`/api/ai/assessments/` kräver en inloggad session, även för HEAD. Den publika
panelen hämtar endast sammanfattningen och visar inte historiska bedömningar.
Sammanfattningens cache är knuten till de senaste mätningarna och upphör senast
när en ingående mätning blir inaktuell enligt `READING_STALE_SECONDS`. Vid ändrade
eller inaktuella mätningar, timeout eller upptagen modell används aktuell reservtext;
en utgången AI-text återanvänds inte. Underlaget innehåller mätningarnas tidsstämplar.

Tal i fritt genererad prosa kan inte kontrolleras semantiskt med en mängd tillåtna
tal. Svar måste därför väljas bland hela, ordagranna meningar som servern skapar
från faktaunderlaget. Alternativen skickas både i prompten och som `enum` i
Ollamas JSON-schema. Sammanfattningar innehåller ett komplett stycke per strand med alla tillgängliga
mätstorheter, status och trend; mejlförklaringar gäller bara den aktuella varningen. Varje mening binder sensor, mätstorhet, värde,
enhet och gräns till samma mätning. Ändrade tecken, värden, enheter eller sensorer
avvisas. Annan numerisk text ger reservsammanfattning eller utelämnad mejlförklaring.
Django kontrollerar även svaret efter generering: exakt fält, strängtyp, valt
alternativ, språk och sifferbindning. Även sifferfri fritext utanför alternativen
avvisas. Modellen prioriterar vilken verifierad text som visas; den skriver inte
fri numerisk prosa. Ett modellsvar som avviker ger fortfarande reservtext.

Se [Ollamas dokumentation om strukturerade svar](https://docs.ollama.com/capabilities/structured-outputs).

### Trend i avvikelsemejl

Förklaringen anger att värdet överskrider projektets gräns och jämför det med
medelvärdet för samma sensor och mätstorhet under de tre timmarna före varningen
(inklusive periodens början, exklusive varningens tid). Alla mätningar i perioden
ingår i databasens medelvärde; historiken skickas inte till modellen. Minst tre
tidigare mätningar krävs, annars anges att underlaget inte räcker. Högre/lägre
avser skillnaden mot periodens medelvärde, inte en beräknad regressionslutning.
Befintlig tolerans används: fem procent av medelvärdets absolutvärde, dock minst
mätstorhetens `MIN_SCALE`. Gränsvärden och larmregler ändras inte.

Texten finns på svenska, engelska och tyska och binds till samma verifierade
faktaunderlag som mätvärdet. AI-avstängning, otillgänglig modell eller ogiltigt
svar lämnar det vanliga avvikelsemejlet oförändrat. Inga personuppgifter ingår
i modellunderlaget. Gamla förklaringar återanvänds inte från föregående cacheversion.

### Sammanfattning per strand

Dashboarden visar ett eget stycke för Ohio Street Beach, 63rd Street Beach och
Rainbow Beach när mätningar finns. Varje tillgänglig mätstorhet har sensor-ID,
värde, enhet, projektgräns, status och trend. Trenden jämför det senaste värdet
med medelvärdet av högst sex tidigare mätningar enligt befintlig tolerans; färre
än tre ger otillräckligt underlag. Saknad gräns eller inaktuell mätning anges
uttryckligen. Inaktuella mätningar presenteras inte som aktuella trender.

Modellen får välja ordningen mellan kompletta strandstycken, men får inte
utelämna stränder eller mätstorheter, ändra status, trend eller tal. Samma
fullständiga underlag visas deterministiskt vid avstängd eller otillgänglig AI.
`source` styr märkningen AI-genererad respektive Automatisk sammanfattning.
Cachetiden är högst 300 sekunder även om en högre tid konfigureras, och begränsas
även av mätningarnas aktualitet. För stort underlag ger reservtext utan modellanrop.
