from io import BytesIO
from datetime import datetime
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String

BLUE = colors.HexColor("#123C69")
GOLD = colors.HexColor("#F2B705")
LIGHT = colors.HexColor("#EEF3F8")
GREEN = colors.HexColor("#16A34A")
AMBER = colors.HexColor("#F59E0B")
RED = colors.HexColor("#DC2626")
GRAY = colors.HexColor("#5F6B78")

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(APP_ROOT, "static", "img", "logo_univalle.png")

REPORT_TITLES = {
    "ejecutivo": "Resumen Ejecutivo Institucional",
    "alertas_intervenciones": "Reporte de Alertas e Intervenciones",
    "efectividad": "Reporte de Efectividad de Intervenciones",
}

def _safe(value, default="—"):
    if value is None or value == "":
        return default
    return str(value)

def _pct(value):
    try:
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "—"

def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("TitleSIAT", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=20, leading=24, textColor=BLUE, alignment=TA_CENTER, spaceAfter=8),
        "subtitle": ParagraphStyle("SubtitleSIAT", parent=base["Normal"], fontSize=10,
            leading=14, textColor=GRAY, alignment=TA_CENTER, spaceAfter=14),
        "h1": ParagraphStyle("H1SIAT", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=13, leading=16, textColor=BLUE, spaceBefore=10, spaceAfter=7),
        "body": ParagraphStyle("BodySIAT", parent=base["BodyText"], fontSize=9,
            leading=13, textColor=colors.HexColor("#263442")),
        "small": ParagraphStyle("SmallSIAT", parent=base["BodyText"], fontSize=7.5,
            leading=10, textColor=colors.HexColor("#263442")),
        "note": ParagraphStyle("NoteSIAT", parent=base["BodyText"], fontSize=8,
            leading=11, textColor=GRAY, backColor=LIGHT, borderPadding=7),
    }

def _header_footer(pdf_canvas, doc, meta):
    pdf_canvas.saveState()
    width, height = doc.pagesize
    pdf_canvas.setFillColor(BLUE)
    pdf_canvas.rect(0, height - 1.45 * cm, width, 1.45 * cm, fill=1, stroke=0)
    if os.path.exists(LOGO_PATH):
        try:
            pdf_canvas.drawImage(LOGO_PATH, 1.35 * cm, height - 1.25 * cm,
                                 width=2.15 * cm, height=0.9 * cm,
                                 preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    pdf_canvas.setFillColor(colors.white)
    pdf_canvas.setFont("Helvetica-Bold", 9)
    pdf_canvas.drawRightString(width - 1.35 * cm, height - 0.65 * cm, "SIAT-DE")
    pdf_canvas.setFont("Helvetica", 7)
    pdf_canvas.drawRightString(width - 1.35 * cm, height - 0.98 * cm,
                               "Sistema Inteligente de Alerta Temprana")
    pdf_canvas.setStrokeColor(BLUE)
    pdf_canvas.line(1.35 * cm, 1.25 * cm, width - 1.35 * cm, 1.25 * cm)
    pdf_canvas.setFillColor(GRAY)
    pdf_canvas.setFont("Helvetica", 7)
    pdf_canvas.drawString(1.35 * cm, 0.82 * cm,
                          f"Generado: {meta['fecha']} · Usuario: {meta['usuario']}")
    pdf_canvas.drawRightString(width - 1.35 * cm, 0.82 * cm, f"Página {doc.page}")
    pdf_canvas.restoreState()

def _kpi_table(items, styles):
    cells = []
    for label, value in items:
        cells.append(Paragraph(
            f"<font size='8' color='#5F6B78'>{label}</font><br/>"
            f"<font size='17' color='#123C69'><b>{value}</b></font>", styles["body"]
        ))
    table = Table([cells], colWidths=[17.3 * cm / max(1, len(cells))] * len(cells))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return table

def _data_table(headers, rows, widths=None):
    data = [[Paragraph(f"<b>{h}</b>", _styles()["small"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(_safe(v), _styles()["small"]) for v in row])
    if len(data) == 1:
        data.append([Paragraph("No existen registros para los filtros aplicados.", _styles()["small"])] +
                    [""] * (len(headers) - 1))
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table

def _risk_chart(kpis):
    values = [int(kpis.get("bajo", 0)), int(kpis.get("medio", 0)), int(kpis.get("alto", 0))]
    labels = ["Bajo", "Medio", "Alto"]
    palette = [GREEN, AMBER, RED]
    maximum = max(values) or 1
    drawing = Drawing(470, 105)
    for idx, (label, value, color) in enumerate(zip(labels, values, palette)):
        y = 76 - idx * 30
        drawing.add(String(0, y + 4, label, fontName="Helvetica-Bold", fontSize=8, fillColor=GRAY))
        width = 335 * value / maximum
        drawing.add(Rect(60, y, 335, 15, fillColor=colors.HexColor("#E5E7EB"), strokeColor=None))
        drawing.add(Rect(60, y, width, 15, fillColor=color, strokeColor=None))
        drawing.add(String(405, y + 4, str(value), fontName="Helvetica-Bold", fontSize=8, fillColor=BLUE))
    return drawing

def _document(report_type, meta):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), rightMargin=1.35 * cm, leftMargin=1.35 * cm,
        topMargin=1.9 * cm, bottomMargin=1.55 * cm,
        title=REPORT_TITLES[report_type], author="SIAT-DE"
    )
    return buffer, doc

def _opening(story, title, meta, styles):
    story.extend([
        Spacer(1, 0.2 * cm),
        Paragraph(title, styles["title"]),
        Paragraph("Sistema Inteligente de Alerta Temprana para la Deserción Estudiantil",
                  styles["subtitle"]),
        Paragraph(
            f"<b>Fecha de corte:</b> {meta.get('fecha_corte', meta['fecha'])} &nbsp;&nbsp; "
            f"<b>Filtros:</b> {meta.get('filtros', 'Todos los registros')}",
            styles["note"]
        ),
        Spacer(1, 0.3 * cm),
    ])

def generate_executive_pdf(df, kpis, insights, meta):
    styles = _styles(); buffer, doc = _document("ejecutivo", meta); story = []
    _opening(story, REPORT_TITLES["ejecutivo"], meta, styles)
    story.append(_kpi_table([
        ("Estudiantes analizados", kpis.get("total", 0)),
        ("Riesgo alto", f"{kpis.get('alto', 0)} ({kpis.get('alto_pct', 0)}%)"),
        ("Riesgo medio", f"{kpis.get('medio', 0)} ({kpis.get('medio_pct', 0)}%)"),
        ("Riesgo bajo", f"{kpis.get('bajo', 0)} ({kpis.get('bajo_pct', 0)}%)"),
    ], styles))
    story.extend([Spacer(1, 0.3 * cm), Paragraph("Distribución institucional del riesgo", styles["h1"]),
                  _risk_chart(kpis), Paragraph("Hallazgos principales", styles["h1"])])
    if insights:
        for item in insights:
            story.append(Paragraph(
                f"<b>{_safe(item.get('titulo'))}:</b> {_safe(item.get('valor'))}. "
                f"{_safe(item.get('detalle'), '')}", styles["body"]))
    else:
        story.append(Paragraph("No se identificaron hallazgos para los filtros aplicados.", styles["body"]))
    story.append(Paragraph("Estudiantes críticos priorizados", styles["h1"]))
    critical = df.sort_values("probabilidad_desercion", ascending=False).head(15)
    rows = [[r.get("codigo_estudiante"), r.get("carrera"), r.get("semestre"),
             _pct(r.get("probabilidad_desercion")), r.get("nivel_riesgo"),
             r.get("accion_sugerida")] for _, r in critical.iterrows()]
    story.append(_data_table(["Código", "Carrera", "Sem.", "Probabilidad", "Riesgo", "Acción sugerida"],
                             rows, [2.2*cm, 4.5*cm, 1.4*cm, 2.2*cm, 1.7*cm, 12.5*cm]))
    story.extend([Paragraph("Conclusión ejecutiva", styles["h1"]),
                  Paragraph("Los resultados permiten priorizar la atención institucional según el nivel de riesgo observado. Se recomienda concentrar el seguimiento en los casos de riesgo alto, coordinar las acciones académicas y de bienestar, y verificar periódicamente la evolución de cada estudiante.", styles["body"])])
    doc.build(story, onFirstPage=lambda c,d:_header_footer(c,d,meta),
              onLaterPages=lambda c,d:_header_footer(c,d,meta))
    buffer.seek(0); return buffer

def generate_alerts_pdf(alerts, interventions, meta):
    styles = _styles(); buffer, doc = _document("alertas_intervenciones", meta); story = []
    _opening(story, REPORT_TITLES["alertas_intervenciones"], meta, styles)
    states = {}
    for a in alerts: states[a.get("estado", "Sin estado")] = states.get(a.get("estado", "Sin estado"), 0) + 1
    pending_followups = sum(1 for i in interventions if i.get("estado") != "Finalizada")
    story.append(_kpi_table([
        ("Alertas registradas", len(alerts)), ("Pendientes", states.get("Pendiente", 0)),
        ("Intervenciones", len(interventions)), ("Seguimientos activos", pending_followups)
    ], styles))
    story.append(Paragraph("Alertas prioritarias", styles["h1"]))
    alert_rows = [[a.get("codigo_estudiante"), a.get("carrera"), a.get("nivel_riesgo"),
                   _pct(a.get("probabilidad")), a.get("estado"), a.get("responsable"),
                   a.get("motivo")] for a in alerts[:30]]
    story.append(_data_table(["Código", "Carrera", "Riesgo", "Prob.", "Estado", "Responsable", "Motivo"],
                             alert_rows, [2*cm, 4*cm, 1.5*cm, 1.6*cm, 2.1*cm, 4.2*cm, 9.4*cm]))
    story.append(PageBreak())
    story.append(Paragraph("Intervenciones y seguimientos", styles["h1"]))
    int_rows = [[i.get("fecha_intervencion"), i.get("codigo_estudiante"), i.get("tipo"),
                 i.get("responsable"), i.get("estado"), i.get("fecha_seguimiento"),
                 i.get("resultado")] for i in interventions[:40]]
    story.append(_data_table(["Fecha", "Código", "Intervención", "Responsable", "Estado", "Seguimiento", "Resultado"],
                             int_rows, [2.1*cm, 2.1*cm, 4.6*cm, 4.3*cm, 2.2*cm, 2.4*cm, 7*cm]))
    story.extend([Paragraph("Recomendación operativa", styles["h1"]),
                  Paragraph("Priorizar las alertas pendientes de riesgo alto y los seguimientos vencidos. Cada intervención debe registrar responsable, fecha, resultado y próxima acción para asegurar trazabilidad institucional.", styles["body"])])
    doc.build(story, onFirstPage=lambda c,d:_header_footer(c,d,meta),
              onLaterPages=lambda c,d:_header_footer(c,d,meta))
    buffer.seek(0); return buffer

def generate_effectiveness_pdf(rows, meta):
    styles = _styles(); buffer, doc = _document("efectividad", meta); story = []
    _opening(story, REPORT_TITLES["efectividad"], meta, styles)
    evaluated = [r for r in rows if r.get("reduccion_probabilidad") is not None]
    effective = [r for r in evaluated if r.get("efectiva") == "Sí"]
    avg = sum(float(r["reduccion_probabilidad"]) for r in evaluated) / len(evaluated) if evaluated else 0
    story.append(_kpi_table([
        ("Intervenciones", len(rows)), ("Casos evaluados", len(evaluated)),
        ("Con mejoría", len(effective)), ("Reducción promedio", f"{avg:.1f} puntos")
    ], styles))
    story.append(Paragraph("Resultados individuales", styles["h1"]))
    result_rows = [[r.get("codigo_estudiante"), r.get("tipo"), r.get("responsable"),
                    _pct(r.get("probabilidad_inicial")), _pct(r.get("probabilidad_final")),
                    f"{r.get('reduccion_probabilidad')} pp" if r.get("reduccion_probabilidad") is not None else "—",
                    r.get("efectiva"), r.get("resultado")] for r in rows[:45]]
    story.append(_data_table(["Código", "Intervención", "Responsable", "Inicial", "Posterior", "Cambio", "Efectiva", "Resultado"],
                             result_rows, [2.1*cm, 4.2*cm, 4.2*cm, 1.7*cm, 1.7*cm, 1.7*cm, 1.8*cm, 7.3*cm]))
    story.append(Paragraph("Conclusión", styles["h1"]))
    if evaluated:
        rate = len(effective) / len(evaluated) * 100
        conclusion = f"Se evaluaron {len(evaluated)} intervenciones; el {rate:.1f}% presentó reducción de la probabilidad de riesgo. La reducción promedio observada fue de {avg:.1f} puntos porcentuales. Estos resultados describen el seguimiento registrado y deben interpretarse junto con el contexto académico de cada caso."
    else:
        conclusion = "Todavía no existen suficientes seguimientos con probabilidad posterior registrada para calcular efectividad. Se recomienda completar la evaluación final de las intervenciones antes de emitir conclusiones."
    story.append(Paragraph(conclusion, styles["body"]))
    doc.build(story, onFirstPage=lambda c,d:_header_footer(c,d,meta),
              onLaterPages=lambda c,d:_header_footer(c,d,meta))
    buffer.seek(0); return buffer
