import hmac
from datetime import timezone as dt_timezone
from io import BytesIO

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import SENSOR_ID_RE, ReadingSerializer
from .models import Reading

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _parse_dt(raw, field):
    try:
        dt = parse_datetime(raw) if raw else None
    except ValueError:
        dt = None
    if dt is None:
        raise ValidationError(
            {field: "Ogiltigt datumformat, använd ISO 8601."})
    return timezone.make_aware(dt, dt_timezone.utc) if timezone.is_naive(dt) else dt


def _api_key_ok(request):
    expected = settings.INGEST_API_KEY
    if not expected:
        return True
    return hmac.compare_digest(request.headers.get("X-API-Key", ""), expected)


class DashboardView(TemplateView):
    template_name = "monitoring/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reading_stale_seconds"] = max(
            1, settings.READING_STALE_SECONDS)
        return context


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
    authentication_classes = [SessionAuthentication]

    def get_authenticators(self):
        if self.request.method == "POST":
            # Inmatning autentiseras med API-nyckel, oberoende av webbläsarens session.
            return []
        return super().get_authenticators()

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD"):
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request):
        q = request.query_params
        start = _parse_dt(q["start"], "start") if "start" in q else None
        end = _parse_dt(q["end"], "end") if "end" in q else None
        if start is not None and end is not None and start > end:
            raise ValidationError(
                {"end": "Måste vara samma tid som eller senare än start."})
        sensor_id = q.get("sensor_id")
        if sensor_id is not None and not SENSOR_ID_RE.fullmatch(sensor_id):
            raise ValidationError(
                {"sensor_id": "Använd 1–100 tecken: a-z, 0-9, '-' eller '_', med bokstav eller siffra först."})
        try:
            limit = int(q.get("limit", settings.HISTORY_DEFAULT_LIMIT))
        except ValueError:
            raise ValidationError({"limit": "Måste vara ett heltal."})
        if limit < 1:
            raise ValidationError({"limit": "Måste vara ett positivt heltal."})
        limit = min(limit, settings.HISTORY_MAX_LIMIT)
        order = q.get("order", "asc")
        if order not in ("asc", "desc"):
            raise ValidationError({"order": "Använd 'asc' eller 'desc'."})
        rows = services.query_history(
            sensor_id, start, end, limit, order == "desc")
        first = rows[0] if rows and len(
            {(r.metric, r.unit) for r in rows}) == 1 else None
        return Response(
            {
                "metric": first.metric if first else None,
                "unit": first.unit if first else None,
                "threshold": services.get_threshold(first.metric) if first else None,
                "count": len(rows),
                "results": ReadingSerializer(rows, many=True).data,
            }
        )

    def post(self, request):
        if not _api_key_ok(request):
            return Response({"detail": "Ogiltig API-nyckel."}, status=status.HTTP_401_UNAUTHORIZED)
        reading = services.ingest_reading(
            request.data)  # ValidationError -> HTTP 400
        return Response(ReadingSerializer(reading).data, status=status.HTTP_201_CREATED)


@login_required
def history_pdf(request):
    sensor_id = request.GET.get("sensor_id", "")

    if not SENSOR_ID_RE.fullmatch(sensor_id):
        return HttpResponseBadRequest("Välj ett giltigt sensor-ID.")

    try:
        start = _parse_dt(request.GET["start"], "start") if request.GET.get("start") else None
        end = _parse_dt(request.GET["end"], "end") if request.GET.get("end") else None
    except ValidationError:
        return HttpResponseBadRequest("Start- eller sluttiden har ogiltigt format.")

    if start is not None and end is not None and start > end:
        return HttpResponseBadRequest("Starttiden måste vara tidigare än sluttiden.")

    # Samma gräns och sortering som dashboardens historik.
    rows = services.query_history(
        sensor_id=sensor_id,
        start=start,
        end=end,
        limit=200,
        descending=False,
    )

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Historiska mätvärden",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Historiska mätvärden", styles["Title"]),
        Spacer(1, 5 * mm),
        Paragraph(f"<b>Sensor-ID:</b> {sensor_id}", styles["BodyText"]),
    ]

    if rows:
        metric_labels = {
            str(metric): label for metric, label in Reading.Metric.choices
        }
        metric_names = {
            metric_labels.get(row.metric, row.metric)
            for row in rows
        }
        metric_name = next(iter(metric_names)) if len(metric_names) == 1 else "Blandade mätstorheter"
        story.append(Paragraph(f"<b>Mätstorhet:</b> {metric_name}", styles["BodyText"]))
    else:
        story.append(Paragraph("<b>Mätstorhet:</b> Ingen data", styles["BodyText"]))

    interval_start = (
        timezone.localtime(start).strftime("%Y-%m-%d %H:%M")
        if start else "Ingen startgräns"
    )
    interval_end = (
        timezone.localtime(end).strftime("%Y-%m-%d %H:%M")
        if end else "Ingen slutgräns"
    )

    story.extend([
        Paragraph(
            f"<b>Tidsintervall:</b> {interval_start} – {interval_end}",
            styles["BodyText"],
        ),
        Paragraph(
            f"<b>Rapport skapad:</b> "
            f"{timezone.localtime().strftime('%Y-%m-%d %H:%M')}",
            styles["BodyText"],
        ),
        Spacer(1, 6 * mm),
    ])

    if rows:
        table_data = [["Tid", "Värde", "Enhet", "Status"]]

        status_labels = {
            str(status): label for status, label in Reading.Status.choices
        }
        for row in rows:
            table_data.append([
                timezone.localtime(row.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                f"{row.value:.1f}",
                row.unit,
                str(status_labels.get(str(row.status), row.status)),
            ])

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[52 * mm, 35 * mm, 30 * mm, 38 * mm],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d6efd")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#f2f2f2"),
            ]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
    else:
        story.append(Paragraph(
            "Inga mätvärden finns för den valda sensorn och tidsperioden.",
            styles["BodyText"],
        ))

    document.build(story)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="historik-{sensor_id}.pdf"'
    )
    return response