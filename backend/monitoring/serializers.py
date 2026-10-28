import math
import re

from django.conf import settings
from rest_framework import serializers

from .models import Reading

SENSOR_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,99}$")
DEFAULT_UNITS = {"turbidity": "NTU", "temperature": "°C"}


class ReadingSerializer(serializers.ModelSerializer):
    """Validerar inkommande sensordata och serialiserar utdata."""

    threshold = serializers.SerializerMethodField()

    class Meta:
        model = Reading
        fields = ["id", "sensor_id", "metric", "timestamp", "value", "unit", "quality", "status", "threshold"]
        read_only_fields = ["id", "status"]

    def get_threshold(self, obj):
        return settings.ANOMALY_THRESHOLDS.get(obj.metric)

    def validate_sensor_id(self, value):
        if not SENSOR_ID_RE.match(value):
            raise serializers.ValidationError("sensor_id får bara innehålla a-z, 0-9, '-' och '_'.")
        return value

    def validate_value(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("value måste vara ett ändligt tal.")
        return value

    def validate(self, attrs):
        metric = attrs.get("metric", Reading.Metric.TURBIDITY)
        if not attrs.get("unit"):
            attrs["unit"] = DEFAULT_UNITS[metric]  # enhet följer mätstorheten om den saknas
        return attrs
