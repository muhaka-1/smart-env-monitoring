"""Jämför lokala Ollama-modeller på samma indata (hastighet och automatiska kontroller)."""
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from monitoring.ai import client, config, facts, summary

# Fasta scenarier i samma form som ``facts.latest_facts()`` ger.
SCENARIOS = {
    "alla_ok": {
        "sensor_points": 2, "over_threshold": 0, "suspected_sensor_faults": 0,
        "items": [
            {"sensor": "calumet-beach-temperature", "metric": "temperature", "value": 19.4, "unit": "°C",
             "threshold": 25.0, "status": "OK", "trend": "steady", "data_quality": None},
            {"sensor": "calumet-beach-turbidity", "metric": "turbidity", "value": 4.2, "unit": "NTU",
             "threshold": 30.0, "status": "OK", "trend": "falling", "data_quality": None},
        ],
    },
    "gräns_överskriden": {
        "sensor_points": 2, "over_threshold": 1, "suspected_sensor_faults": 0,
        "items": [
            {"sensor": "ohio-street-beach-turbidity", "metric": "turbidity", "value": 41.7, "unit": "NTU",
             "threshold": 30.0, "status": "ANOMALY", "trend": "rising", "data_quality": "deviation"},
            {"sensor": "ohio-street-beach-temperature", "metric": "temperature", "value": 22.7, "unit": "°C",
             "threshold": 25.0, "status": "OK", "trend": "steady", "data_quality": None},
        ],
    },
    "misstänkt_sensorfel": {
        "sensor_points": 2, "over_threshold": 1, "suspected_sensor_faults": 1,
        "items": [
            {"sensor": "rainbow-beach-turbidity", "metric": "turbidity", "value": 0.0, "unit": "NTU",
             "threshold": 30.0, "status": "OK", "trend": "falling", "data_quality": "sensor_fault"},
            {"sensor": "rainbow-beach-temperature", "metric": "temperature", "value": 26.3, "unit": "°C",
             "threshold": 25.0, "status": "ANOMALY", "trend": "rising", "data_quality": None},
        ],
    },
}
# Ordlistor för en enkel språkkontroll; ersätter inte en mänsklig bedömning.
LANGUAGE_WORDS = {
    "sv": {" och ", " är ", " inte ", " mätpunkt", " värde", " gräns", " över ", " ett ", " en "},
    "en": {" and ", " the ", " is ", " are ", " not ", " limit", " above ", " reading"},
    "de": {" und ", " der ", " die ", " ist ", " nicht ", " grenzwert", " über ", " messwert"},
}


def language_ok(text: str, language: str) -> bool:
    lowered = f" {text.lower()} "
    return sum(word in lowered for word in LANGUAGE_WORDS[language]) >= 2


class Command(BaseCommand):
    help = "Jämför lokala modeller på fasta scenarier och skriver en tabell (valfritt som markdown)."

    def add_arguments(self, parser):
        parser.add_argument("--models", help="Kommaseparerad lista, till exempel llama3.2:3b,qwen2.5:3b.")
        parser.add_argument("--language", default="sv", choices=sorted(LANGUAGE_WORDS))
        parser.add_argument("--no-warmup", action="store_true", help="Hoppa över uppvärmningsanropet.")
        parser.add_argument("--output", help="Skriv resultatet som markdown till denna fil.")

    def handle(self, *args, **options):
        models = [m.strip() for m in (options["models"] or config.model()).split(",") if m.strip()]
        if not models:
            raise CommandError("Ange minst en modell med --models.")
        language = options["language"]
        rows = []
        for model in models:
            self.stdout.write(f"Provar {model} …")
            if not options["no_warmup"]:
                self._ask(model, next(iter(SCENARIOS.values())), language)   # laddar modellen, ej mätt
            for name, scenario in SCENARIOS.items():
                rows.append({"model": model, "scenario": name, **self._ask(model, scenario, language)})
        report = self._markdown(rows, language)
        self.stdout.write(report)
        if options["output"]:
            Path(options["output"]).write_text(report, encoding="utf-8")
            self.stdout.write(f"Sparade {options['output']}.")

    def _ask(self, model, scenario, language):
        system, user = summary._prompt(scenario, language)
        started = time.perf_counter()
        try:
            result = client.chat_json(system, user, summary.SCHEMA, model=model, standalone=True,
                                      timeout=config.timeout() * 4)
        except client.AIUnavailable as exc:
            return {"seconds": time.perf_counter() - started, "json": False, "numbers": False,
                    "advice_free": False, "codes_free": False, "language": False, "text": f"(fel: {exc})"}
        seconds = time.perf_counter() - started
        text = str(result.get("summary", "")).strip()
        return {
            "seconds": seconds, "json": bool(text), "numbers": bool(text) and facts.numbers_are_grounded(text, scenario),
            "advice_free": not facts.contains_bathing_advice(text),
            "codes_free": not facts.contains_raw_codes(text), "language": language_ok(text, language),
            "text": text,
        }

    @staticmethod
    def _markdown(rows, language):
        mark = lambda ok: "✔" if ok else "✘"  # noqa: E731
        lines = [f"# Modelljämförelse ({language})", "",
                 "| Modell | Scenario | Tid (s) | JSON | Tal ur data | Inget badråd | Inga koder | Språk | Manuell bedömning (1–5) | Text |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in rows:
            text = r["text"].replace("|", "/").replace("\n", " ")
            lines.append(f"| {r['model']} | {r['scenario']} | {r['seconds']:.1f} | {mark(r['json'])} | "
                         f"{mark(r['numbers'])} | {mark(r['advice_free'])} | {mark(r['codes_free'])} | {mark(r['language'])} |  | {text} |")
        lines += ["", "## Sammanfattning per modell", "", "| Modell | Medeltid (s) | Godkända kontroller |", "| --- | --- | --- |"]
        for model in dict.fromkeys(r["model"] for r in rows):
            own = [r for r in rows if r["model"] == model]
            passed = sum(all(r[k] for k in ("json", "numbers", "advice_free", "codes_free", "language")) for r in own)
            lines.append(f"| {model} | {sum(r['seconds'] for r in own) / len(own):.1f} | {passed}/{len(own)} |")
        return "\n".join(lines) + "\n"
