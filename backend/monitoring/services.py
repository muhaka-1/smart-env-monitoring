"""Affärslogik, oberoende av transport (HTTP eller MQTT)."""
from django.conf import settings

from .models import Reading
from .serializers import ReadingSerializer


def get_threshold(metric: str) -> float | None:
    return settings.ANOMALY_THRESHOLDS.get(metric)


def evaluate_status(value: float, metric: str = Reading.Metric.TURBIDITY, threshold: float | None = None) -> str:
    """Returnerar 'ANOMALY' om värdet överskrider mätstorhetens gränsvärde, annars 'OK'."""
    limit = get_threshold(metric) if threshold is None else threshold
    if limit is None:
        return Reading.Status.OK
    return Reading.Status.ANOMALY if value > limit else Reading.Status.OK


def ingest_reading(payload: dict) -> Reading:
    """Validerar och sparar en mätning. Kastar ValidationError vid felaktig data."""
    serializer = ReadingSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    metric = data.get("metric", Reading.Metric.TURBIDITY)
    return serializer.save(status=evaluate_status(data["value"], metric))


def get_latest(sensor_id: str):
    return Reading.objects.filter(sensor_id=sensor_id).order_by("-timestamp").first()


def get_sensor_ids():
    return list(Reading.objects.values_list("sensor_id", flat=True).distinct().order_by("sensor_id"))


def get_latest_per_sensor():
    return [r for r in (get_latest(s) for s in get_sensor_ids()) if r]


def query_history(sensor_id=None, start=None, end=None, limit=500, descending=False):
    qs = Reading.objects.all()
    if sensor_id:
        qs = qs.filter(sensor_id=sensor_id)
    if start:
        qs = qs.filter(timestamp__gte=start)
    if end:
        qs = qs.filter(timestamp__lte=end)
    rows = list(qs.order_by("-timestamp")[:limit])  # senaste N i intervallet
    if not descending:
        rows.reverse()
    return rows
