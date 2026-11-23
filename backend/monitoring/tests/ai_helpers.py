"""Gemensamma hjälpmedel för AI-tester. Ollama anropas aldrig på riktigt."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import requests
from django.core.cache import cache

from monitoring.models import Reading

START = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


def ollama_response(payload):
    """Ett svar i samma form som Ollamas /api/chat ger (innehållet är en JSON-sträng)."""
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"message": {"role": "assistant", "content": json.dumps(payload)}}
    return response


def raw_response(content):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"message": {"content": content}}
    return response


def http_error():
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    return response


def make_readings(sensor_id, metric, values, unit=None, start=START):
    """Sparar mätningar direkt (utan inmatningsflödet) med en minut mellan varje."""
    unit = unit or ("NTU" if metric == "turbidity" else "°C")
    return [Reading.objects.create(sensor_id=sensor_id, metric=metric, value=v, unit=unit,
                                   timestamp=start + timedelta(minutes=i)) for i, v in enumerate(values)]


def steady(center, count=12, wobble=0.2):
    """Jämn serie med små, deterministiska variationer runt ett värde."""
    pattern = [0, wobble, -wobble, wobble / 2, -wobble / 2, 0, -wobble, wobble]
    return [round(center + pattern[i % len(pattern)], 3) for i in range(count)]


def clean_state():
    cache.clear()
