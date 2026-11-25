"""Statussammanfattning ("Läget just nu"): AI-text med kontrollerade siffror, annars vanlig text."""
import hashlib
import json
import logging
import time

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _, override

from . import client, config, facts as facts_module
from .grounding import numeric_statements, response_schema, selected_text
from .beach_summary import beach_blocks

log = logging.getLogger(__name__)
MAX_LENGTH = 2000



def fallback_text(facts: dict, language: str) -> str:
    """Show every beach even when generation is disabled or unavailable."""
    with override(language):
        if not facts["sensor_points"]:
            return _("Inga mätvärden ännu.")
        count, *measurements = numeric_statements(facts, language)
        blocks = beach_blocks(facts["items"], measurements, language)
        return "\n\n".join([count, *blocks])


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
    try:
        system, user = _prompt(facts, language)
        schema = response_schema("summary", facts, language, MAX_LENGTH)
    except ValueError as exc:
        raise client.AIUnavailable("underlaget ryms inte i sammanfattningen") from exc
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
    key = f"ai-summary:v4:{language}:{signature}"
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
