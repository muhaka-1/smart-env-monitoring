"""Faktaunderlag för AI-texter. Modellen får bara dessa värden, aldrig fri databasåtkomst."""
import re
from statistics import mean

from django.conf import settings
from django.utils import timezone

from .grounding import numeric_text_is_grounded

from ..models import Reading
from .anomaly import MIN_SCALE, DEFAULT_MIN_SCALE

TREND_WINDOW = 6
LANGUAGE_NAMES = {"sv": "svenska", "en": "English", "de": "Deutsch"}


def language_name(language: str) -> str:
    return LANGUAGE_NAMES.get((language or "sv")[:2], LANGUAGE_NAMES["sv"])


def trend(previous: list[float], value: float, metric: str) -> str:
    """'rising', 'falling', 'steady' eller 'unknown' jämfört med medelvärdet av tidigare värden."""
    if len(previous) < 3:
        return "unknown"
    base = mean(previous[-TREND_WINDOW:])
    limit = max(0.05 * abs(base), MIN_SCALE.get(metric, DEFAULT_MIN_SCALE))
    if value - base > limit:
        return "rising"
    if base - value > limit:
        return "falling"
    return "steady"


def _previous_values(sensor_id, metric, before, limit=TREND_WINDOW):
    rows = (Reading.objects.filter(sensor_id=sensor_id, metric=metric, timestamp__lt=before)
            .order_by("-timestamp").values_list("value", flat=True)[:limit])
    return list(rows)[::-1]


def _quality(reading):
    assessment = getattr(reading, "assessment", None)
    return assessment.kind if assessment else None


def latest_facts() -> dict:
    """Senaste mätvärde per sensor och mätstorhet med gränsvärde, status och trend."""
    pairs = Reading.objects.order_by().values_list("sensor_id", "metric").distinct()
    items = []
    for sensor_id, metric in sorted(pairs):
        reading = (Reading.objects.select_related("assessment")
                   .filter(sensor_id=sensor_id, metric=metric).order_by("-timestamp").first())
        if reading is None:
            continue
        threshold = settings.ANOMALY_THRESHOLDS.get(metric)
        items.append({
            "sensor": sensor_id, "metric": metric,
            "timestamp": reading.timestamp.isoformat(),
            "stale": (timezone.now() - reading.timestamp).total_seconds() > max(1, settings.READING_STALE_SECONDS),
            "value": round(reading.value, 1), "unit": reading.unit,
            "threshold": None if threshold is None else round(threshold, 1),
            "status": reading.status,
            "trend": trend(_previous_values(sensor_id, metric, reading.timestamp), reading.value, metric),
            "data_quality": _quality(reading),
        })
    return {
        "sensor_points": len(items),
        "over_threshold": sum(1 for i in items if i["status"] == Reading.Status.ANOMALY),
        "suspected_sensor_faults": sum(1 for i in items if i["data_quality"] == "sensor_fault"),
        "items": items,
    }


def numbers_are_grounded(text: str, facts: dict) -> bool:
    """Numeric text must preserve complete sensor/metric/value/threshold statements."""
    return numeric_text_is_grounded(text, facts)


# Modellen får inte formulera badråd (plattformen är "inte ett badråd").
_ADVICE = re.compile(
    r"säker(?:t)? att bada|kan (?:du )?bada|bada (?:utan|här)|safe to (?:swim|bathe)|safe for (?:swim|bath)"
    r"|okay to (?:swim|bathe)|ok to (?:swim|bathe)|sicher(?:\w*)? (?:zu )?baden|baden (?:ist|kann)",
    re.IGNORECASE,
)


def contains_bathing_advice(text: str) -> bool:
    return bool(_ADVICE.search(text))
