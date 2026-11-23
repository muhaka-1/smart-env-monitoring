"""Statussammanfattning ("Läget just nu"): AI-text med kontrollerade siffror, annars vanlig text."""
import json
import logging
import time

from django.core.cache import cache
from django.utils.translation import gettext as _, ngettext, override

from . import client, config, facts as facts_module

log = logging.getLogger(__name__)
MAX_LENGTH = 700
SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string", "maxLength": MAX_LENGTH}},
    "required": ["summary"],
}
_KEEP_SECONDS = 24 * 3600


def _metric_label(metric):
    return {"temperature": _("Temperatur"), "turbidity": _("Turbiditet")}.get(metric, metric)


def fallback_text(facts: dict, language: str) -> str:
    """Deterministisk sammanfattning som bara bygger på mätdatan."""
    with override(language):
        if not facts["sensor_points"]:
            return _("Inga mätvärden ännu.")
        parts = [ngettext(
            "%(n)d mätpunkt har ett senaste mätvärde.",
            "%(n)d mätpunkter har ett senaste mätvärde.", facts["sensor_points"]) % {"n": facts["sensor_points"]}]
        over = [i for i in facts["items"] if i["status"] == "ANOMALY"]
        if over:
            parts.append(ngettext(
                "%(n)d mätpunkt överskrider projektets gräns:",
                "%(n)d mätpunkter överskrider projektets gräns:", len(over)) % {"n": len(over)})
            for item in over:
                parts.append(_("%(sensor)s (%(metric)s) %(value)s %(unit)s, gräns %(threshold)s.") % {
                    "sensor": item["sensor"], "metric": _metric_label(item["metric"]).lower(),
                    "value": f"{item['value']:.1f}", "unit": item["unit"], "threshold": f"{item['threshold']:.1f}"})
        else:
            parts.append(_("Inget mätvärde överskrider projektets gränser."))
        faults = [i for i in facts["items"] if i["data_quality"] == "sensor_fault"]
        if faults:
            parts.append(_("Misstänkt sensorfel: %(sensors)s.") % {"sensors": ", ".join(i["sensor"] for i in faults)})
        return " ".join(parts)


def _prompt(facts: dict, language: str):
    system = (
        "Du sammanfattar mätdata för en kommuns övervakning av badvatten. "
        f"Skriv 2–3 korta meningar på {facts_module.language_name(language)}. "
        "Använd ENDAST de tal och sensornamn som finns i underlaget. Hitta inte på värden. "
        "Ge inga badråd och bedöm inte om vattnet är säkert; statusen är projektets gränsregel. "
        "Svara som JSON med fältet summary."
    )
    user = "Underlag (JSON):\n" + json.dumps(facts, ensure_ascii=False)
    return system, user


def generate(facts: dict, language: str, *, timeout=None) -> str:
    """Anropar modellen och kontrollerar svaret. Kastar AIUnavailable vid fel eller otillåtet innehåll."""
    system, user = _prompt(facts, language)
    result = client.chat_json(system, user, SCHEMA, timeout=timeout)
    text = result.get("summary")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_LENGTH:
        raise client.AIUnavailable("tomt eller för långt svar")
    text = text.strip()
    if not facts_module.numbers_are_grounded(text, facts):
        log.warning("AI-sammanfattning avvisades: innehåller tal som inte finns i mätdatan.")
        raise client.AIUnavailable("ogrundade tal")
    if facts_module.contains_bathing_advice(text):
        log.warning("AI-sammanfattning avvisades: innehåller badråd.")
        raise client.AIUnavailable("badråd")
    return text


def _language(language):
    return (language or "sv")[:2]


def get_summary(language: str) -> dict:
    """Returnerar {'text', 'source': 'ai'|'fallback', 'generated_at', 'model'}."""
    language = _language(language)
    facts = facts_module.latest_facts()
    now = time.time()
    fallback = {"text": fallback_text(facts, language), "source": "fallback", "generated_at": now, "model": None}
    if not config.enabled() or not facts["sensor_points"]:
        return fallback
    key = f"ai-summary:{language}"
    cached = cache.get(key)
    if cached and now - cached["generated_at"] < config.summary_cache_seconds():
        return cached
    lock = f"{key}:lock"
    if not client.available() or not cache.add(lock, 1, timeout=config.timeout() + 5):
        return cached or fallback          # annan förfrågan genererar redan, eller AI pausas
    try:
        text = generate(facts, language)
    except client.AIUnavailable:
        return cached or fallback
    finally:
        cache.delete(lock)
    result = {"text": text, "source": "ai", "generated_at": now, "model": config.model()}
    cache.set(key, result, timeout=_KEEP_SECONDS)
    return result
