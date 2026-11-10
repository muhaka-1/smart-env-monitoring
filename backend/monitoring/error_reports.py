"""Gemensamma filter och data för felrapport på skärm och som PDF."""
from datetime import timezone as dt_timezone
from urllib.parse import urlencode

from django import forms
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Alert
from .serializers import SENSOR_ID_RE


class ErrorReportFilters(forms.Form):
    sensor_id = forms.CharField(label="Sensor", required=False, max_length=100, strip=False,
                               widget=forms.Select(attrs={"class": "form-select"}))
    start = forms.CharField(
        label="Från (UTC)", required=False, max_length=64,
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M:%S", attrs={"type": "datetime-local", "step": "1", "class": "form-control"}),
    )
    end = forms.CharField(
        label="Till (UTC)", required=False, max_length=64,
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M:%S", attrs={"type": "datetime-local", "step": "1", "class": "form-control"}),
    )
    as_of = forms.CharField(required=False, max_length=64, widget=forms.HiddenInput())

    def __init__(self, *args, sensor_ids=(), **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(sensor, sensor) for sensor in sensor_ids]
        selected = self.initial.get("sensor_id")
        if selected and selected not in {value for value, _ in choices}:
            choices.append((selected, selected))
        self.fields["sensor_id"].widget.choices = [("", "Alla sensorer"), *choices]

    def clean_sensor_id(self):
        value = self.cleaned_data["sensor_id"]
        if value and not SENSOR_ID_RE.fullmatch(value):
            raise forms.ValidationError("Ange ett giltigt sensor-ID med a-z, 0-9, '-' eller '_'.")
        return value

    def _datetime(self, name):
        raw = self.cleaned_data[name]
        if not raw:
            return None
        try:
            value = parse_datetime(raw)
            if value is not None:
                if timezone.is_naive(value):
                    value = timezone.make_aware(value, dt_timezone.utc)
                return value.astimezone(dt_timezone.utc)
        except (ValueError, OverflowError):
            pass
        raise forms.ValidationError("Ange giltigt datum och tid i ISO 8601-format.")

    def clean_start(self):
        return self._datetime("start")

    def clean_end(self):
        return self._datetime("end")

    def clean_as_of(self):
        return self._datetime("as_of") or timezone.now()

    def clean(self):
        data = super().clean()
        start, end = data.get("start"), data.get("end")
        if start and end and start > end:
            self.add_error("end", "Till måste vara samma tid som eller senare än Från.")
        return data


def user_alerts(user):
    return Alert.objects.filter(notification__user=user).order_by("-timestamp", "-pk")


def filter_alerts(queryset, filters):
    queryset = queryset.filter(created_at__lte=filters["as_of"])
    if filters.get("sensor_id"):
        queryset = queryset.filter(sensor_id=filters["sensor_id"])
    if filters.get("start"):
        queryset = queryset.filter(timestamp__gte=filters["start"])
    if filters.get("end"):
        queryset = queryset.filter(timestamp__lte=filters["end"])
    return queryset


def filter_query(filters):
    return urlencode({key: value.isoformat() if hasattr(value, "isoformat") else value
                      for key, value in filters.items() if value})


def utc_text(value):
    return value.astimezone(dt_timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
