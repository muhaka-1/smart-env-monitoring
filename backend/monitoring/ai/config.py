"""AI-inställningar. Värden läses från Django-inställningar och annars från miljön."""
import os
from urllib.parse import urlsplit

from django.conf import settings

DEFAULTS = {
    "AI_ENABLED": "0",
    "OLLAMA_URL": "http://127.0.0.1:11434",
    "OLLAMA_MODEL": "llama3.2:3b",
    "AI_TIMEOUT": "30",             # sekunder för sammanfattning på dashboarden
    "AI_MAIL_TIMEOUT": "8",         # sekunder för förklaring i mejl (blockerar utskicket)
    "AI_COOLDOWN_SECONDS": "60",    # paus efter fel innan modellen anropas igen
    "AI_SUMMARY_CACHE_SECONDS": "300",
}


def _raw(name):
    value = getattr(settings, name, None)
    if value is None:
        value = os.getenv(name, DEFAULTS[name])
    return value


def _number(name, minimum):
    try:
        value = float(_raw(name))
    except (TypeError, ValueError):
        value = float(DEFAULTS[name])
    return max(value, minimum)


def enabled() -> bool:
    return str(_raw("AI_ENABLED")).strip().lower() in {"1", "true", "yes", "on"}


def model() -> str:
    return str(_raw("OLLAMA_MODEL")).strip() or DEFAULTS["OLLAMA_MODEL"]


def base_url() -> str:
    """Ollama-adressen. Endast http/https utan inloggning, annars används standardadressen."""
    raw = str(_raw("OLLAMA_URL")).strip().rstrip("/")
    try:
        parts = urlsplit(raw)
        ok = parts.scheme in {"http", "https"} and parts.hostname and not (
            parts.username or parts.password or parts.query or parts.fragment)
    except ValueError:
        ok = False
    return raw if ok else DEFAULTS["OLLAMA_URL"]


def timeout() -> float:
    return _number("AI_TIMEOUT", 1)


def mail_timeout() -> float:
    return _number("AI_MAIL_TIMEOUT", 1)


def cooldown_seconds() -> float:
    return _number("AI_COOLDOWN_SECONDS", 0)


def summary_cache_seconds() -> float:
    return _number("AI_SUMMARY_CACHE_SECONDS", 0)
