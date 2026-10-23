import hmac
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import ReadingSerializer


def _parse_dt(raw, field):
    dt = parse_datetime(raw) if raw else None
    if dt is None:
        raise ValidationError({field: "Ogiltigt datumformat, använd ISO 8601."})
    return timezone.make_aware(dt, dt_timezone.utc) if timezone.is_naive(dt) else dt


def _api_key_ok(request):
    expected = settings.INGEST_API_KEY
    if not expected:
        return True
    return hmac.compare_digest(request.headers.get("X-API-Key", ""), expected)


class DashboardView(TemplateView):
    template_name = "monitoring/dashboard.html"


class HealthView(APIView):
    def get(self, request):
        connection.ensure_connection()
        return Response({"status": "ok"})


class SensorListView(APIView):
    def get(self, request):
        return Response({"results": services.get_sensor_ids()})


class LatestReadingView(APIView):
    def get(self, request):
        sensor_id = request.query_params.get("sensor_id")
        if sensor_id:
            reading = services.get_latest(sensor_id)
            if reading is None:
                return Response({"detail": "Inga mätvärden hittades."}, status=status.HTTP_404_NOT_FOUND)
            return Response(ReadingSerializer(reading).data)
        return Response({"results": ReadingSerializer(services.get_latest_per_sensor(), many=True).data})


class ReadingListCreateView(APIView):
    def get(self, request):
        q = request.query_params
        start = _parse_dt(q["start"], "start") if "start" in q else None
        end = _parse_dt(q["end"], "end") if "end" in q else None
        try:
            limit = int(q.get("limit", settings.HISTORY_DEFAULT_LIMIT))
        except ValueError:
            raise ValidationError({"limit": "Måste vara ett heltal."})
        limit = max(1, min(limit, settings.HISTORY_MAX_LIMIT))
        order = q.get("order", "asc")
        if order not in ("asc", "desc"):
            raise ValidationError({"order": "Använd 'asc' eller 'desc'."})
        rows = services.query_history(q.get("sensor_id"), start, end, limit, order == "desc")
        return Response(
            {
                "threshold": settings.ANOMALY_THRESHOLD,
                "count": len(rows),
                "results": ReadingSerializer(rows, many=True).data,
            }
        )

    def post(self, request):
        if not _api_key_ok(request):
            return Response({"detail": "Ogiltig API-nyckel."}, status=status.HTTP_401_UNAUTHORIZED)
        reading = services.ingest_reading(request.data)  # ValidationError -> HTTP 400
        return Response(ReadingSerializer(reading).data, status=status.HTTP_201_CREATED)
