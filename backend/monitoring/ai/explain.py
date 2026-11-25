"""Förklaring av en avvikelse i e-post, samt en vanlig varning vid misstänkt sensorfel."""
import json
import logging

from django.core.cache import cache
from django.utils.translation import gettext as _, override

from . import client, config, facts as facts_module
from .grounding import numeric_statements

log = logging.getLogger(__name__)
MAX_LENGTH = 400
SCHEMA = {
    "type": "object",
    "properties": {"explanation": {"type": "string", "maxLength": MAX_LENGTH}},
    "required": ["explanation"],
}
_CACHE_SECONDS = 24 * 3600


def alert_facts(alert) -> dict:
    from ..models import Reading
    previous = facts_module._previous_values(alert.sensor_id, alert.metric, alert.timestamp)
    over = None
    if alert.threshold:
        over = round((alert.value - alert.threshold) / abs(alert.threshold) * 100, 1)
    return {
        "sensor": alert.sensor_id, "metric": alert.metric,
        "value": round(alert.value, 1), "unit": alert.unit, "threshold": round(alert.threshold, 1),
        "percent_over_threshold": over,
        "previous_values": [round(v, 1) for v in previous],
        "trend": facts_module.trend(previous, alert.value, alert.metric),
        "data_quality": getattr(getattr(alert.reading, "assessment", None), "kind", None),
        "status": Reading.Status.ANOMALY,
    }


def explain_alert(alert, language: str) -> str | None:
    """AI-förklaring för ett mejl, eller None om AI är av, pausad eller svaret inte kan lita på."""
    if not config.enabled():
        return None
    language = (language or "sv")[:2]
    key = f"ai-explain:{alert.pk}:{language}"
    cached = cache.get(key)
    if cached:
        return cached
    if not client.available():
        return None
    facts = alert_facts(alert)
    system = (
        "Du förklarar en datavarning från en kommuns miljöövervakning för en handläggare. "
        f"Skriv högst två korta meningar på {facts_module.language_name(language)}: vad värdet betyder i förhållande "
        "till gränsvärdet och hur de senaste värdena har utvecklats. Använd ENDAST tal och namn som finns i underlaget. "
        "Hitta inte på orsaker. Ge inga badråd. Svara som JSON med fältet explanation."
    )
    system += " Om svaret innehåller siffror, använd endast hela meningar från denna lista, ordagrant: " + json.dumps(numeric_statements(facts, language), ensure_ascii=False)
    user = "Underlag (JSON):\n" + json.dumps(facts, ensure_ascii=False)
    try:
        result = client.chat_json(system, user, SCHEMA, timeout=config.mail_timeout())
    except client.AIUnavailable:
        return None
    text = result.get("explanation")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_LENGTH:
        return None
    text = text.strip()
    if not facts_module.numbers_are_grounded(text, facts) or facts_module.contains_bathing_advice(text):
        log.warning("AI-förklaring avvisades för varning %s.", alert.pk)
        return None
    cache.set(key, text, timeout=_CACHE_SECONDS)
    return text


def quality_note(alert, language: str) -> str:
    """Vanlig (ej AI) varningstext om mätvärdet misstänks vara ett sensorfel."""
    assessment = getattr(getattr(alert, "reading", None), "assessment", None)
    if assessment is None or assessment.kind != "sensor_fault":
        return ""
    with override(language):
        return _("Obs: mätvärdet misstänks vara ett sensorfel (%(reason)s). Kontrollera sensorn innan åtgärd.") % {
            "reason": str(assessment.get_reason_display()).lower()}
