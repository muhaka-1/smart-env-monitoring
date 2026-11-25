"""Förklaring av en avvikelse i e-post, samt en vanlig varning vid misstänkt sensorfel."""
import json
import logging
from datetime import timedelta

from django.db.models import Avg, Count

from django.core.cache import cache
from django.utils.translation import gettext as _, override

from . import client, config, facts as facts_module
from .grounding import response_schema, selected_text

log = logging.getLogger(__name__)
MAX_LENGTH = 400
TREND_HOURS = 3
_CACHE_SECONDS = 24 * 3600


def alert_facts(alert) -> dict:
    from ..models import Reading
    history = Reading.objects.filter(
        sensor_id=alert.sensor_id, metric=alert.metric,
        timestamp__gte=alert.timestamp - timedelta(hours=TREND_HOURS),
        timestamp__lt=alert.timestamp,
    ).aggregate(count=Count("pk"), baseline=Avg("value"))
    trend = "unknown"
    if history["count"] >= 3:
        trend = facts_module.trend_from_baseline(history["baseline"], alert.value, alert.metric)
    over = None
    if alert.threshold:
        over = round((alert.value - alert.threshold) / abs(alert.threshold) * 100, 1)
    return {
        "sensor": alert.sensor_id, "metric": alert.metric,
        "value": round(alert.value, 1), "unit": alert.unit, "threshold": round(alert.threshold, 1),
        "percent_over_threshold": over,
        "trend_window_hours": TREND_HOURS,
        "trend_sample_count": history["count"],
        "trend": trend,
        "data_quality": getattr(getattr(alert.reading, "assessment", None), "kind", None),
        "status": Reading.Status.ANOMALY,
    }


def explain_alert(alert, language: str) -> str | None:
    """AI-förklaring för ett mejl, eller None om AI är av, pausad eller svaret inte kan lita på."""
    if not config.enabled():
        return None
    language = (language or "sv")[:2]
    key = f"ai-explain:v3:{alert.pk}:{language}"
    cached = cache.get(key)
    if cached:
        return cached
    if not client.available():
        return None
    facts = alert_facts(alert)
    schema = response_schema("explanation", facts, language, MAX_LENGTH)
    system = (
        "Välj förklaringen från enum-alternativen i schemat utan att ändra text, tal eller sensornamn. "
        f"Texten är på {facts_module.language_name(language)} och beskriver projektets gränsregel. "
        "Ge inga badråd eller påhittade orsaker. Svara enbart som JSON enligt schemat: "
        + json.dumps(schema, ensure_ascii=False)
    )
    user = "Underlag (JSON):\n" + json.dumps(facts, ensure_ascii=False)
    try:
        result = client.chat_json(system, user, schema, timeout=config.mail_timeout())
    except client.AIUnavailable:
        return None
    text = selected_text(result, "explanation", schema)
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
