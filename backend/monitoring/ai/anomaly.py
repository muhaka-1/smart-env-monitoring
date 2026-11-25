"""Statistisk avvikelsedetektion mot sensorns egen historik (ingen modell behövs).

För varje ny mätning jämförs värdet med medianen av sensorns senaste mätningar av
samma mätstorhet. Resultatet är antingen
  * ``sensor_fault`` (misstänkt sensorfel): fastfrusset värde, plötsligt nollvärde
    eller ett orimligt hopp, eller
  * ``deviation`` (statistisk avvikelse): värdet avviker tydligt men rimligt.
Detta är skilt från gränsvärdet (``Reading.status``) och är ingen myndighetsbedömning.
"""
import logging
from dataclasses import dataclass
from statistics import median

log = logging.getLogger(__name__)

WINDOW = 30            # antal tidigare mätningar som utgör referens
MIN_HISTORY = 8        # färre tidigare mätningar ger ingen bedömning
FLATLINE_COUNT = 6     # så många lika värden i rad (inklusive det nya) = fastfrusset
DEVIATION_Z = 3.5      # robust z-värde för statistisk avvikelse
FAULT_Z = 10.0         # robust z-värde för orimligt hopp
# Minsta skala per mätstorhet så att mycket jämna serier inte ger falsklarm.
MIN_SCALE = {"turbidity": 0.5, "temperature": 0.2}
DEFAULT_MIN_SCALE = 0.5


@dataclass(frozen=True)
class Finding:
    kind: str      # "sensor_fault" | "deviation"
    reason: str    # "flatline" | "zero" | "jump" | "outlier"
    score: float


def assess_value(history: list[float], value: float, metric: str) -> Finding | None:
    """Bedömer ett nytt värde mot tidigare värden (äldst först). None = inget anmärkningsvärt."""
    history = list(history)[-WINDOW:]
    if len(history) < MIN_HISTORY:
        return None
    ref = median(history)
    mad = median(abs(v - ref) for v in history)
    scale = max(1.4826 * mad, 0.02 * abs(ref), MIN_SCALE.get(metric, DEFAULT_MIN_SCALE))
    z = (value - ref) / scale

    recent = history[-(FLATLINE_COUNT - 1):] + [value]
    if len(recent) == FLATLINE_COUNT and len(set(recent)) == 1 and len(set(history)) > 1:
        return Finding("sensor_fault", "flatline", 0.0)
    if value == 0 and ref > 1:
        return Finding("sensor_fault", "zero", round(abs(z), 2))
    if abs(z) >= FAULT_Z:
        return Finding("sensor_fault", "jump", round(abs(z), 2))
    if abs(z) >= DEVIATION_Z:
        return Finding("deviation", "outlier", round(abs(z), 2))
    return None


def analyse_series(values: list[float], metric: str) -> list[Finding | None]:
    """Bedömer en hel tidsserie i tidsordning, utan att titta framåt."""
    return [assess_value(values[:i], v, metric) for i, v in enumerate(values)]


def _history_for(reading):
    from ..models import Reading
    rows = (Reading.objects
            .filter(sensor_id=reading.sensor_id, metric=reading.metric, timestamp__lt=reading.timestamp)
            .order_by("-timestamp").values_list("value", flat=True)[:WINDOW])
    return list(rows)[::-1]


def record(reading, finding: Finding | None):
    """Sparar eller rensar bedömningen och sätter ``quality`` vid misstänkt sensorfel."""
    from ..models import Reading, ReadingAssessment
    if finding is None:
        ReadingAssessment.objects.filter(reading=reading).delete()
        return None
    assessment, _ = ReadingAssessment.objects.update_or_create(
        reading=reading, defaults={"kind": finding.kind, "reason": finding.reason, "score": finding.score})
    if finding.kind == ReadingAssessment.Kind.SENSOR_FAULT and reading.quality != Reading.Quality.SUSPECT:
        Reading.objects.filter(pk=reading.pk).update(quality=Reading.Quality.SUSPECT)
        reading.quality = Reading.Quality.SUSPECT
    return assessment


def assess_reading(reading):
    """Anropas efter att en mätning sparats. Får aldrig stoppa inmatningen av data."""
    from django.db import transaction
    try:
        with transaction.atomic():  # savepoint: ett databasfel här ska inte förstöra yttre transaktion
            return record(reading, assess_value(_history_for(reading), reading.value, reading.metric))
    except Exception as exc:  # noqa: BLE001 - detektionen är ett tillägg, inte en förutsättning
        log.warning("Avvikelsedetektion misslyckades för mätning %s (%s).", reading.pk, type(exc).__name__)
        return None
