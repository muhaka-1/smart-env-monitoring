"""Public latest summary and authenticated historical assessments."""
from datetime import datetime, timezone

from django.utils.translation import get_language
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import ReadingAssessment
from . import config, summary

MAX_ASSESSMENTS = 50


@method_decorator(never_cache, name="dispatch")
class AISummaryView(APIView):
    def get(self, request):
        data = summary.get_summary(get_language() or "sv")
        return Response({
            "text": data["text"], "source": data["source"], "model": data["model"],
            "ai_enabled": config.enabled(),
            "generated_at": datetime.fromtimestamp(data["generated_at"], timezone.utc).isoformat(),
        })


@method_decorator(never_cache, name="dispatch")
class AIAssessmentListView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            limit = min(max(int(request.query_params.get("limit", 20)), 1), MAX_ASSESSMENTS)
        except ValueError:
            limit = 20
        rows = ReadingAssessment.objects.select_related("reading")
        if request.query_params.get("sensor_id"):
            rows = rows.filter(reading__sensor_id=request.query_params["sensor_id"])
        results = []
        for item in rows[:limit]:
            reading = item.reading
            results.append({
                "reading_id": reading.pk, "sensor_id": reading.sensor_id, "metric": reading.metric,
                "metric_label": reading.get_metric_display(), "timestamp": reading.timestamp,
                "value": reading.value, "unit": reading.unit, "quality": reading.quality,
                "kind": item.kind, "kind_label": item.get_kind_display(),
                "reason": item.reason, "reason_label": item.get_reason_display(), "score": item.score,
            })
        return Response({"results": results})
