from datetime import datetime, timezone

from .data_source import Measurement


def build_message(m: Measurement, now: datetime | None = None) -> dict:
    """Bygger meddelandet. Varje datapunkt får en aktuell tidsstämpel + sensor-ID."""
    now = now or datetime.now(timezone.utc)
    return {
        "sensor_id": m.sensor_id,
        "metric": m.metric,
        "timestamp": now.isoformat(),
        "value": m.value,
        "unit": m.unit,
        "quality": m.quality,
    }
