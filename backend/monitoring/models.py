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

    sensor_id = models.CharField(max_length=100)
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
