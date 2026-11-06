"""Gemensam e-postleverans; anroparen ansvarar för konton, token och varningslogik."""
import logging
from collections.abc import Mapping
from smtplib import SMTPException
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.mail import EmailMessage
from django.core.validators import URLValidator, validate_email
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme

log = logging.getLogger(__name__)

_TEMPLATES = {
    "invitation": ("Din inbjudan till Smart Environmental Monitoring", "monitoring/emails/invitation.txt"),
    "password_reset": ("Återställ ditt lösenord", "monitoring/emails/password_reset.txt"),
    "data_alert": ("Datavarning från Smart Environmental Monitoring", "monitoring/emails/data_alert.txt"),
}
_ALERT_FIELDS = {"sensor_id", "metric", "timestamp", "value", "unit", "threshold", "status"}


class EmailDeliveryError(RuntimeError):
    """Leveransen misslyckades; innehåller inga detaljer från SMTP-servern."""


def _platform_url(action_path: str) -> str:
    base = settings.PLATFORM_BASE_URL.rstrip("/")
    try:
        URLValidator(schemes=["http", "https"])(base)
        parts = urlsplit(base)
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError
    except (ValidationError, ValueError):
        raise ImproperlyConfigured("PLATFORM_BASE_URL måste vara en HTTP(S)-adress utan inloggning, query eller fragment.") from None
    if (
        not action_path.startswith("/")
        or not url_has_allowed_host_and_scheme(action_path, allowed_hosts=set())
        or any(char.isspace() or ord(char) < 32 for char in action_path)
    ):
        raise ValueError("action_path måste vara en lokal URL-sökväg utan blanksteg.")
    return base + action_path


def send_platform_email(recipient: str, kind: str, *, action_path: str, context: Mapping[str, object] | None = None) -> None:
    """Skickar en mall till en mottagare eller kastar EmailDeliveryError vid leveransfel."""
    if kind not in _TEMPLATES:
        raise ValueError("Okänd e-posttyp.")
    validate_email(recipient)
    data = dict(context or {})
    if kind == "data_alert" and not _ALERT_FIELDS.issubset(data):
        raise ValueError("Datavarningen saknar obligatoriska mallfält.")
    data["action_url"] = _platform_url(action_path)
    subject, template = _TEMPLATES[kind]
    message = EmailMessage(
        subject=subject,
        body=render_to_string(template, data).strip() + "\n",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    try:
        if message.send(fail_silently=False) != 1:
            raise EmailDeliveryError("E-postmeddelandet kunde inte skickas.")
    except (SMTPException, OSError, EmailDeliveryError):
        # SMTP-fel kan innehålla mottagare, inloggning eller meddelandeinnehåll.
        log.error("E-postleverans misslyckades (typ=%s).", kind)
        raise EmailDeliveryError("E-postmeddelandet kunde inte skickas.") from None
