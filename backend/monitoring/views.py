import hmac
from datetime import timezone as dt_timezone
from io import BytesIO

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection, transaction
from django.utils import formats, timezone
from django.utils.translation import get_language, gettext as _
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
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
from .notifications import messages_for

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
        if dt is None:
            raise ValueError
        dt = timezone.make_aware(dt, dt_timezone.utc) if timezone.is_naive(dt) else dt
        return dt.astimezone(dt_timezone.utc)
    except (ValueError, OverflowError):
        raise ValidationError(
            {field: "Ogiltigt datumformat eller datum utanför tillåtet intervall, använd ISO 8601."}) from None


def _api_key_ok(request):
    expected = settings.INGEST_API_KEY
    if not expected:
        return True
    return hmac.compare_digest(request.headers.get("X-API-Key", "").encode("utf-8"), expected.encode("utf-8"))


@method_decorator(never_cache, name="dispatch")
class DashboardView(TemplateView):
    template_name = "monitoring/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reading_stale_seconds"] = max(
            1, settings.READING_STALE_SECONDS)
        context["dashboard_i18n"] = {
            "locale": get_language() or settings.LANGUAGE_CODE,
            "turbidity": _("Turbiditet"),
            "temperature": _("Temperatur"),
            "measurement": _("Mätvärde"),
            "range_hour": _("senaste timmen"),
            "range_day": _("senaste dygnet"),
            "range_week": _("senaste 7 dagarna"),
            "range_all": _("senaste 200 mätningarna"),
            "fetch_error": _("Mätvärdena kunde inte hämtas."),
            "no_readings": _("Inga mätvärden ännu."),
            "latest_status": _("Senaste status: "),
            "anomaly": _("Avvikelse"),
            "threshold": _("gräns"),
            "stale": _("Mätningen är inaktuell eller saknar giltig tid."),
            "show_history": _("Visa historik"),
            "show_history_for": _("Visa historik för %(sensor)s"),
            "mixed_history": _("Historiken innehåller olika mätstorheter och kan inte visas i samma diagram."),
            "no_interval_readings": _("Inga mätvärden finns för det valda intervallet."),
            "threshold_label": _("Gränsvärde"),
            "chart_explanation": _("● OK · ▲ Avvikelse. Statusen följer projektets konfigurerade gränsregel och är inte en officiell bedömning av badvattnet."),
            "time_local": _("Tid (lokal tid)"),
            "value": _("Värde"),
            "choose_both": _("Välj både Från och Till, eller använd ett snabbval."),
            "invalid_date": _("Tidsintervallet innehåller ett ogiltigt datum."),
            "from_before_to": _("Från måste vara tidigare än Till."),
            "interval": _("Intervall: %(range)s."),
            "custom_interval": _("Eget intervall: %(start)s – %(end)s."),
            "custom_incomplete": _("Eget intervall är inte komplett."),
            "choose_sensor": _("Välj en sensor innan rapporten skapas."),
            "session_expired": _("Din session har gått ut eller saknar behörighet. Logga in igen för att visa historiken."),
            "unavailable": _("Mätvärdena är inte tillgängliga just nu."),
            "updated": _("Uppdaterad %(time)s"),
            "update_failed": _("Uppdateringen misslyckades"),
            "refresh_error": _("Kunde inte hämta nya mätvärden. Kontrollera anslutningen eller logga in igen. Ett nytt försök görs automatiskt."),
        }
        if self.request.user.is_authenticated and self.template_name == "monitoring/dashboard.html":
            context["recent_notifications"] = messages_for(self.request.user)[:3]
        return context


class HistoryView(LoginRequiredMixin, DashboardView):
    template_name = "monitoring/history.html"


class ReportListView(LoginRequiredMixin, TemplateView):
    template_name = "monitoring/reports.html"


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

    matches = Reading.objects.filter(sensor_id=sensor_id)
    if start is not None:
        matches = matches.filter(timestamp__gte=start)
    if end is not None:
        matches = matches.filter(timestamp__lte=end)
    # Antal och urval ska beskriva samma databasögonblick även under inmatning.
    with transaction.atomic():
        total = matches.count()
        rows = list(matches.order_by("-timestamp", "-pk")[:200])
    rows.reverse()

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=_("Historiska mätvärden - Senaste 200"),
    )
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#183247")
    story = [
        Paragraph(_("Badvattenkvalitet | Miljöövervakning"), styles["Normal"]),
        Paragraph(_("Historiska mätvärden - Senaste 200"), styles["Title"]),
        Paragraph(
            _("Visar %(shown)d av %(total)d matchande mätningar.")
            % {"shown": len(rows), "total": total},
            styles["BodyText"],
        ),
        Paragraph(
            _("%(omitted)d matchande mätningar ingår inte. Rapporten visar högst de senaste 200, inte nödvändigtvis hela tidsintervallet.")
            % {"omitted": total - len(rows)},
            styles["BodyText"],
        ),
        Spacer(1, 5 * mm),
        Paragraph(_("<b>Sensor-ID:</b> %(sensor_id)s") % {"sensor_id": sensor_id}, styles["BodyText"]),
    ]

    if rows:
        metric_labels = {
            str(metric): label for metric, label in Reading.Metric.choices
        }
        metric_names = {
            metric_labels.get(row.metric, row.metric)
            for row in rows
        }
        metric_name = next(iter(metric_names)) if len(metric_names) == 1 else _("Blandade mätstorheter")
        story.append(Paragraph(_("<b>Mätstorhet:</b> %(metric)s") % {"metric": metric_name}, styles["BodyText"]))
    else:
        story.append(Paragraph(_("<b>Mätstorhet:</b> Ingen data"), styles["BodyText"]))

    interval_start = (
        start.astimezone(dt_timezone.utc).strftime("%Y-%m-%d %H:%M")
        if start else _("Ingen startgräns")
    )
    interval_end = (
        end.astimezone(dt_timezone.utc).strftime("%Y-%m-%d %H:%M")
        if end else _("Ingen slutgräns")
    )

    story.extend([
        Paragraph(
            _("<b>Tidsintervall (UTC):</b> %(start)s – %(end)s")
            % {"start": interval_start, "end": interval_end},
            styles["BodyText"],
        ),
        Paragraph(
            _("<b>Rapport skapad (UTC):</b> %(created)s")
            % {"created": timezone.now().astimezone(dt_timezone.utc).strftime("%Y-%m-%d %H:%M")},
            styles["BodyText"],
        ),
        Spacer(1, 6 * mm),
    ])

    if rows:
        table_data = [[_("Tid (UTC)"), _("Värde"), _("Enhet"), _("Status")]]

        status_labels = {
            str(status): label for status, label in Reading.Status.choices
        }
        for row in rows:
            table_data.append([
                row.timestamp.astimezone(dt_timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                formats.number_format(row.value, decimal_pos=1, use_l10n=True),
                row.unit,
                str(status_labels.get(str(row.status), row.status)),
            ])

        table = Table(
            table_data,
            repeatRows=1,
            colWidths=[52 * mm, 35 * mm, 30 * mm, 38 * mm],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#124d61")),
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
            _("Inga mätvärden finns för den valda sensorn och tidsperioden."),
            styles["BodyText"],
        ))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#536578"))
        canvas.drawString(18 * mm, 10 * mm, _("Badvattenkvalitet | Simulerade data"))
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, _("Sida %(page)d") % {"page": doc.page})
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="historik-{sensor_id}.pdf"'
    )
    return response
