import math
import re

from rest_framework import serializers

from .models import Reading

SENSOR_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,99}$")


class ReadingSerializer(serializers.ModelSerializer):
    """Validerar inkommande sensordata och serialiserar utdata."""

    class Meta:
        model = Reading
        fields = ["id", "sensor_id", "timestamp", "value", "unit", "quality", "status"]
        read_only_fields = ["id", "status"]

    def validate_sensor_id(self, value):
        if not SENSOR_ID_RE.match(value):
            raise serializers.ValidationError("sensor_id får bara innehålla a-z, 0-9, '-' och '_'.")
        return value

    def validate_value(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("value måste vara ett ändligt tal.")
        return value
