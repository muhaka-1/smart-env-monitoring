"""Statussammanfattning ("Läget just nu"): AI-text med kontrollerade siffror, annars vanlig text."""
import hashlib
import json
import logging
import time

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _, ngettext, override

from . import client, config, facts as facts_module
from .grounding import response_schema, selected_text

log = logging.getLogger(__name__)
MAX_LENGTH = 700



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
        over = [i for i in facts["items"] if i["status"] == "ANOMALY" and not i.get("stale", False)]
        if over:
            parts.append(ngettext(
                "%(n)d mätpunkt överskrider projektets gräns:",
                "%(n)d mätpunkter överskrider projektets gräns:", len(over)) % {"n": len(over)})
            for item in over:
                parts.append(_("%(sensor)s (%(metric)s) %(value)s %(unit)s, gräns %(threshold)s.") % {
                    "sensor": item["sensor"], "metric": _metric_label(item["metric"]).lower(),
                    "value": f"{item['value']:.1f}", "unit": item["unit"], "threshold": f"{item['threshold']:.1f}"})
        elif not any(i.get("stale", False) for i in facts["items"]):
            parts.append(_("Inget mätvärde överskrider projektets gränser."))
        if any(i.get("stale", False) for i in facts["items"]):
            parts.append(_("Mätningen är inaktuell eller saknar giltig tid."))
        faults = [i for i in facts["items"] if i["data_quality"] == "sensor_fault" and not i.get("stale", False)]
        if faults:
            parts.append(_("Misstänkt sensorfel: %(sensors)s.") % {"sensors": ", ".join(i["sensor"] for i in faults)})
        return " ".join(parts)


def _prompt(facts: dict, language: str):
    schema = response_schema("summary", facts, language, MAX_LENGTH)
    system = (
        "Välj den mest relevanta sammanfattningen från enum-alternativen i schemat. "
        "Prioritera projektavvikelser och misstänkta sensorfel. Ändra inte text, tal eller sensornamn. "
        f"Alternativen är på {facts_module.language_name(language)}. "
        "Ge inga badråd. Svara enbart som JSON enligt schemat: "
        + json.dumps(schema, ensure_ascii=False)
    )
    user = "Underlag (JSON):\n" + json.dumps(facts, ensure_ascii=False)
    return system, user


def generate(facts: dict, language: str, *, timeout=None) -> str:
    """Anropar modellen och kontrollerar svaret. Kastar AIUnavailable vid fel eller otillåtet innehåll."""
    system, user = _prompt(facts, language)
    schema = response_schema("summary", facts, language, MAX_LENGTH)
    result = client.chat_json(system, user, schema, timeout=timeout)
    text = selected_text(result, "summary", schema)
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
    if not config.enabled() or not facts["sensor_points"] or any(i.get("stale", False) for i in facts["items"]):
        return fallback
    signature = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
    key = f"ai-summary:v3:{language}:{signature}"
    cached = cache.get(key)
    if cached and now - cached["generated_at"] < config.summary_cache_seconds():
        return cached
    lock = f"{key}:lock"
    if not client.available() or not cache.add(lock, 1, timeout=config.timeout() + 5):
        return fallback
    try:
        text = generate(facts, language)
    except client.AIUnavailable:
        current = facts_module.latest_facts()
        return {"text": fallback_text(current, language), "source": "fallback",
                "generated_at": time.time(), "model": None}
    finally:
        cache.delete(lock)
    current = facts_module.latest_facts()
    if current != facts:
        return {"text": fallback_text(current, language), "source": "fallback",
                "generated_at": time.time(), "model": None}
    result = {"text": text, "source": "ai", "generated_at": now, "model": config.model()}
    remaining = min((timezone.datetime.fromisoformat(i["timestamp"]) - timezone.now()).total_seconds()
                    + max(1, settings.READING_STALE_SECONDS) for i in facts["items"])
    ttl = min(config.summary_cache_seconds(), max(0, remaining))
    if ttl > 0:
        cache.set(key, result, timeout=ttl)
    return result
