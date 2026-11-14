from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib.auth.decorators import login_required
from django.core.paginator import InvalidPage, Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from .error_reports import ErrorReportFilters, filter_alerts, filter_query, user_alerts, utc_text


def report_context(request):
    available = user_alerts(request.user)
    sensors = available.order_by("sensor_id").values_list("sensor_id", flat=True).distinct()
    form = ErrorReportFilters(request.GET, sensor_ids=sensors)
    context = {"form": form, "generated_at": utc_text(timezone.now())}
    if not form.is_valid():
        return context, None
    filters = form.cleaned_data
    display = {key: value.replace(tzinfo=None) if key in ("start", "end") and value is not None else value
               for key, value in filters.items()}
    display["as_of"] = filters["as_of"].isoformat()
    context.update(
        form=ErrorReportFilters(initial=display, sensor_ids=sensors),
        filters=filters,
        start_text=utc_text(filters["start"]) if filters["start"] else _("Ingen startgräns"),
        end_text=utc_text(filters["end"]) if filters["end"] else _("Ingen slutgräns"),
        filter_query=filter_query(filters),
    )
    return context, filter_alerts(available, filters)


@login_required
@require_GET
@never_cache
def error_report(request):
    context, alerts = report_context(request)
    if alerts is None:
        return render(request, "monitoring/error_report.html", context, status=400)
    paginator = Paginator(alerts, 20)
    try:
        page = paginator.page(request.GET.get("page", 1))
    except InvalidPage:
        raise Http404(_("Rapportsidan finns inte."))
    context.update(page_obj=page, total=paginator.count,
                   pdf_url=reverse("error-report-pdf") + "?" + context["filter_query"])
    return render(request, "monitoring/error_report.html", context)


@login_required
@require_GET
@never_cache
def error_report_pdf(request):
    context, alerts = report_context(request)
    if alerts is None:
        return render(request, "monitoring/error_report.html", context, status=400)
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                                 leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=16*mm,
                                 title="Felrapport")
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#183247")
    cell_style = ParagraphStyle("ReportCell", fontName="Helvetica", fontSize=8, leading=10, splitLongWords=True)
    header_style = ParagraphStyle("ReportHeader", parent=cell_style, fontName="Helvetica-Bold", textColor=colors.white)
    def paragraph(value, style=cell_style):
        return Paragraph(escape(str(value)), style)
    filters = context["filters"]
    story = [paragraph("Badvattenkvalitet | Miljöövervakning"),
             Paragraph("Felrapport", styles["Title"]),
             paragraph("Sensor: " + (filters["sensor_id"] or "Alla sensorer")),
             paragraph(f"Tidsintervall (UTC): {context['start_text']} - {context['end_text']}"),
             paragraph("Rapport skapad (UTC): " + context["generated_at"]),
             paragraph("Sparade projektavvikelser, inte en myndighetsbedömning av badvattenkvalitet."),
             Spacer(1, 5*mm)]
    headers = ["Sensor-ID", "Mätstorhet", "Tid (UTC)", "Värde", "Enhet", "Gränsvärde", "Status"]
    rows = [[paragraph(title, header_style) for title in headers]]
    for alert in alerts.iterator(chunk_size=500):
        rows.append([paragraph(value) for value in (
            alert.sensor_id, alert.get_metric_display(), utc_text(alert.timestamp),
            alert.value, alert.unit, alert.threshold, alert.get_status_display(),
        )])
    if len(rows) == 1:
        story.append(paragraph("Inga sparade avvikelser finns för valt filter."))
    else:
        story.append(paragraph(f"Antal händelser: {len(rows)-1}"))
        story.append(Spacer(1, 3*mm))
        table = LongTable(rows, repeatRows=1, colWidths=[69*mm, 26*mm, 40*mm, 28*mm, 15*mm, 37*mm, 32*mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#124d61")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#536578"))
        canvas.drawString(14*mm, 9*mm, "Badvattenkvalitet | Simulerade data")
        canvas.drawRightString(landscape(A4)[0]-14*mm, 9*mm, f"Sida {doc.page}")
        canvas.restoreState()
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="felrapport.pdf"'
    return response
