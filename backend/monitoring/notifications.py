"""Sparade avvikelser och användarmeddelanden med separat e-postleverans."""
import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .emails import EmailDeliveryError, send_platform_email
from .models import Alert, Notification, Reading

log = logging.getLogger(__name__)


def valid_recipient(user):
    if not user.is_active:
        return False
    try:
        validate_email(user.email)
    except ValidationError:
        return False
    return True


@transaction.atomic
def create_alert(reading, threshold):
    if reading.status != Reading.Status.ANOMALY:
        return
    alert, created = Alert.objects.get_or_create(
        reading=reading,
        defaults={
            "sensor_id": reading.sensor_id, "metric": reading.metric,
            "timestamp": reading.timestamp, "value": reading.value,
            "unit": reading.unit, "threshold": threshold, "status": reading.status,
        },
    )
    if not created:
        return
    users = get_user_model().objects.filter(is_active=True).exclude(email="").iterator()
    Notification.objects.bulk_create([
        Notification(alert=alert, user=user) for user in users if valid_recipient(user)
    ])
    transaction.on_commit(lambda: deliver_alert(alert.pk))


def deliver_alert(alert_id):
    ids = Notification.objects.filter(alert_id=alert_id, delivery_status=Notification.DeliveryStatus.PENDING).values_list("pk", flat=True)
    for notification_id in ids.iterator():
        deliver_notification(notification_id)


def deliver_notification(notification_id):
    # En villkorad uppdatering låter bara en av samtidiga anropare försöka skicka.
    claimed = Notification.objects.filter(
        pk=notification_id, delivery_status=Notification.DeliveryStatus.PENDING,
    ).update(delivery_status=Notification.DeliveryStatus.SENDING)
    if not claimed:
        return
    message = Notification.objects.select_related("alert", "user").filter(pk=notification_id).first()
    if message is None:
        return
    if not valid_recipient(message.user):
        Notification.objects.filter(pk=notification_id).update(
            delivery_status=Notification.DeliveryStatus.FAILED,
            delivery_error="Mottagaren är inte längre aktiv eller saknar giltig e-postadress.",
        )
        return
    alert = message.alert
    try:
        send_platform_email(
            message.user.email, "data_alert", action_path=reverse("message-list"),
            context={field: getattr(alert, field) for field in (
                "sensor_id", "metric", "timestamp", "value", "unit", "threshold", "status",
            )},
        )
    except (EmailDeliveryError, ImproperlyConfigured, ValidationError):
        Notification.objects.filter(pk=notification_id).update(
            delivery_status=Notification.DeliveryStatus.FAILED,
            delivery_error="E-postförsöket misslyckades. Meddelandet finns kvar i plattformen.",
        )
        log.warning("E-postförsök misslyckades för meddelande %s.", notification_id)
    else:
        Notification.objects.filter(pk=notification_id).update(
            delivery_status=Notification.DeliveryStatus.SENT, email_sent_at=timezone.now(),
        )


def messages_for(user):
    return Notification.objects.filter(user=user).select_related("alert")
