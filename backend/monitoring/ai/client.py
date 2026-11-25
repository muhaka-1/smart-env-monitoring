"""Klient mot Ollamas lokala HTTP-API (``POST /api/chat``).

Alla fel blir ``AIUnavailable`` så att anroparen kan välja reservtext. Efter ett fel
pausas anropen (``AI_COOLDOWN_SECONDS``) så att en nedsläckt modell inte gör varje
utskick eller sidvisning långsam. Loggar innehåller aldrig prompt eller svar.
"""
import json
import logging
import time

import requests
from django.core.cache import cache

from . import config

log = logging.getLogger(__name__)
_COOLDOWN_KEY = "monitoring-ai-cooldown-until"


class AIUnavailable(RuntimeError):
    """AI är avstängd, pausad eller modellen svarade inte med ett användbart svar."""


def available() -> bool:
    return config.enabled() and not _cooling_down()


def _cooling_down() -> bool:
    until = cache.get(_COOLDOWN_KEY)
    return bool(until) and time.time() < until


def _start_cooldown():
    seconds = config.cooldown_seconds()
    if seconds > 0:
        cache.set(_COOLDOWN_KEY, time.time() + seconds, timeout=seconds)


def reset_cooldown():
    cache.delete(_COOLDOWN_KEY)


def chat_json(system: str, user: str, schema: dict, *, timeout: float | None = None,
              model: str | None = None, standalone: bool = False) -> dict:
    """Ber modellen svara med JSON enligt ``schema`` och returnerar det tolkade svaret.

    ``standalone=True`` används av modelljämförelsen: den ignorerar AI_ENABLED och
    felpausen så att flera modeller kan provas efter varandra.
    """
    if not standalone:
        if not config.enabled():
            raise AIUnavailable("AI är avstängd.")
        if _cooling_down():
            raise AIUnavailable("AI pausas efter ett tidigare fel.")
    body = {
        "model": model or config.model(),
        "stream": False,
        "format": schema,
        "options": {"temperature": 0.2},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    try:
        response = requests.post(
            config.base_url() + "/api/chat", json=body,
            timeout=timeout or config.timeout(), allow_redirects=False,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        result = json.loads(content) if isinstance(content, str) else content
        if not isinstance(result, dict):
            raise ValueError("svaret är inte ett JSON-objekt")
    except (requests.RequestException, OSError) as exc:
        _fail("kunde inte nå Ollama", exc, standalone)
    except (ValueError, KeyError, TypeError) as exc:
        _fail("ogiltigt svar från Ollama", exc, standalone)
    return result


def _fail(reason, exc, standalone=False):
    if not standalone:
        _start_cooldown()
    # Endast feltypen loggas: texten kan innehålla adresser eller delar av innehållet.
    log.warning("AI-anrop misslyckades: %s (%s).", reason, type(exc).__name__)
    raise AIUnavailable(reason) from None
