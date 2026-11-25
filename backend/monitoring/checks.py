"""Kontrollerar SMTP lokalt utan nätverksanrop eller hemligheter i feltexten."""
from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


@register("email")
def smtp_configuration_checks(app_configs, **kwargs):
    if settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend":
        return []
    errors = []
    for field in ("EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD"):
        value = getattr(settings, field)
        if not isinstance(value, str) or not value.strip():
            errors.append(Error(
                f"{field} måste anges för SMTP.",
                hint="Ange värdet i projektrotens .env eller processens miljö.",
                id="monitoring.E001",
            ))
    if settings.EMAIL_HOST in ("localhost", "127.0.0.1", "::1", "smtp.example.com"):
        errors.append(Error("EMAIL_HOST måste ange den avsedda SMTP-leverantören.", id="monitoring.E002"))
    if settings.EMAIL_USE_TLS == settings.EMAIL_USE_SSL:
        errors.append(Error("Aktivera exakt en av EMAIL_USE_TLS och EMAIL_USE_SSL för SMTP.", id="monitoring.E003"))
    if not isinstance(settings.EMAIL_PORT, int) or not 1 <= settings.EMAIL_PORT <= 65535:
        errors.append(Error("EMAIL_PORT måste vara ett heltal mellan 1 och 65535.", id="monitoring.E004"))
    if not isinstance(settings.EMAIL_TIMEOUT, (int, float)) or settings.EMAIL_TIMEOUT <= 0:
        errors.append(Error("EMAIL_TIMEOUT måste vara ett positivt antal sekunder.", id="monitoring.E005"))
    try:
        validate_email(settings.DEFAULT_FROM_EMAIL)
        if settings.DEFAULT_FROM_EMAIL == "no-reply@example.com":
            raise ValidationError("Exempeladress")
    except ValidationError:
        errors.append(Error("DEFAULT_FROM_EMAIL måste vara en giltig avsändaradress, inte exempeladressen.", id="monitoring.E006"))
    return errors
