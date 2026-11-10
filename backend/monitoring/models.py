from django.conf import settings
from django.db import models


class Reading(models.Model):
    """Ett tidsstämplat mätvärde från en sensor (tidsserie)."""

    class Quality(models.TextChoices):
        GOOD = "good", "Good"
        SUSPECT = "suspect", "Suspect"
        BAD = "bad", "Bad"

    class Status(models.TextChoices):
        OK = "OK", "OK"
        ANOMALY = "ANOMALY", "Avvikelse"

    class Metric(models.TextChoices):
        TURBIDITY = "turbidity", "Turbiditet"
        TEMPERATURE = "temperature", "Temperatur"

    sensor_id = models.CharField(max_length=100)
    metric = models.CharField(max_length=20, choices=Metric.choices, default=Metric.TURBIDITY)
    timestamp = models.DateTimeField()
    value = models.FloatField()
    unit = models.CharField(max_length=20, default="NTU", blank=True)
    quality = models.CharField(max_length=10, choices=Quality.choices, default=Quality.GOOD)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OK)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            models.UniqueConstraint(fields=["sensor_id", "timestamp"], name="uniq_sensor_timestamp")
        ]
        indexes = [
            models.Index(fields=["timestamp"], name="idx_reading_timestamp"),
            models.Index(fields=["sensor_id", "-timestamp"], name="idx_reading_sensor_ts"),
        ]

    def __str__(self):
        return f"{self.sensor_id} @ {self.timestamp:%Y-%m-%d %H:%M:%S} = {self.value}"


class AccountInvitation(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_digest = models.CharField(max_length=64, blank=True)
    issued_at = models.DateTimeField()


class Alert(models.Model):
    reading = models.OneToOneField(Reading, on_delete=models.PROTECT)
    sensor_id = models.CharField(max_length=100)
    metric = models.CharField(max_length=20, choices=Reading.Metric.choices)
    timestamp = models.DateTimeField()
    value = models.FloatField()
    unit = models.CharField(max_length=20)
    threshold = models.FloatField()
    status = models.CharField(max_length=10, choices=Reading.Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    class DeliveryStatus(models.TextChoices):
        PENDING = "pending", "Väntar på e-postförsök"
        SENDING = "sending", "Påbörjat utskick, utfall ännu inte bekräftat"
        SENT = "sent", "Accepterat av e-postservern"
        FAILED = "failed", "E-postförsöket misslyckades"

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    delivery_status = models.CharField(max_length=10, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)
    delivery_error = models.CharField(max_length=255, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["alert", "user"], name="uniq_alert_user")]
