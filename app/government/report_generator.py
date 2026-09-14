"""Decision-focused PDF reporting for the Hakiki Hire Government Dashboard.

The report intentionally differs from the operational Overview page. It
summarises review outcomes, resolution progress, verification exposure,
confirmed scams, watchlist cases, key findings, and the complete case register.

This module is self-contained and does not import app.py, analytics.py, or the
API client, which prevents circular imports.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

NAVY = colors.HexColor("#071F33")
DARK_BLUE = colors.HexColor("#0A3A59")
CYAN = colors.HexColor("#38BDF8")
GREEN = colors.HexColor("#22C55E")
AMBER = colors.HexColor("#F59E0B")
ORANGE = colors.HexColor("#F97316")
RED = colors.HexColor("#EF4444")
SLATE = colors.HexColor("#64748B")
PALE_BLUE = colors.HexColor("#E8F4FA")
PALE_GREEN = colors.HexColor("#ECFDF5")
PALE_RED = colors.HexColor("#FEF2F2")
LIGHT_GREY = colors.HexColor("#F4F7FB")
BORDER = colors.HexColor("#DBE3EC")
TEXT = colors.HexColor("#10233B")
WHITE = colors.white

RISK_LABELS = {
    "lower_risk": "Lower risk",
    "suspicious": "Suspicious",
    "high_risk": "High risk",
}
VERIFICATION_LABELS = {
    "verified": "Verified",
    "unverified": "Unverified",
    "blacklisted": "Blacklisted",
    "possible_impersonation": "Possible impersonation",
    "not_applicable": "Not applicable",
}
STATUS_LABELS = {
    "open": "Open",
    "resolved": "Resolved",
}
OUTCOME_LABELS = {
    "confirmed_legitimate": "Confirmed legitimate",
    "confirmed_scam": "Confirmed scam",
    "needs_more_evidence": "Needs more evidence",
    "duplicate": "Duplicate report",
}
OUTCOME_ORDER = [
    "Confirmed legitimate",
    "Confirmed scam",
    "Needs more evidence",
    "Duplicate report",
    "Not yet decided",
]
OUTCOME_COLORS = [GREEN, RED, AMBER, SLATE, colors.HexColor("#CBD5E1")]
VERIFICATION_ORDER = [
    "Verified",
    "Unverified",
    "Blacklisted",
    "Possible impersonation",
    "Not applicable",
]
VERIFICATION_COLORS = [GREEN, AMBER, RED, ORANGE, SLATE]


def _display(value: Any, fallback: str = "Not provided") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan"}:
        return fallback
    return text


def _html(value: Any, fallback: str = "Not provided") -> str:
    return escape(_display(value, fallback)).replace("\n", "<br/>")


def _label(value: Any, labels: Mapping[str, str], fallback: str = "Not provided") -> str:
    raw = _display(value, fallback)
    if raw == fallback:
        return fallback
    return labels.get(raw, raw.replace("_", " ").strip().capitalize())


def _format_datetime(value: Any) -> str:
    if value is None:
        return "Not provided"
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return "Not provided"
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    return parsed.strftime("%d %b %Y %H:%M")


def _format_percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.0%"
    return "{:.1f}%".format((numerator / denominator) * 100)


def _normalise_cases(cases: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(case) for case in cases if isinstance(case, Mapping)]


def report_filename(
    prefix: str = "hakiki-hire-government-report",
    generated_at: datetime | None = None,
) -> str:
    """Return a safe timestamped PDF filename."""
    timestamp = generated_at or datetime.now(timezone.utc)
    safe_prefix = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in prefix.strip().lower()
    ).strip("-")
    if not safe_prefix:
        safe_prefix = "hakiki-hire-government-report"
    return "{}-{}.pdf".format(
        safe_prefix,
        timestamp.strftime("%Y%m%d-%H%M%S"),
    )


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "HakikiHireReportTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=25,
            textColor=WHITE,
            alignment=TA_LEFT,
            spaceAfter=5,
        ),
        "subtitle": ParagraphStyle(
            "HakikiHireReportSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#D7EEFA"),
            spaceAfter=2,
        ),
        "heading": ParagraphStyle(
            "HakikiHireReportHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=7,
        ),
        "section_label": ParagraphStyle(
            "HakikiHireSectionLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=DARK_BLUE,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "HakikiHireReportBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=TEXT,
        ),
        "small": ParagraphStyle(
            "HakikiHireReportSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.5,
            textColor=SLATE,
        ),
        "table": ParagraphStyle(
            "HakikiHireReportTable",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=6.7,
            leading=8.5,
            textColor=TEXT,
        ),
        "metric_label": ParagraphStyle(
            "HakikiHireMetricLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=6.6,
            leading=8,
            textColor=SLATE,
            alignment=TA_CENTER,
        ),
        "metric_value": ParagraphStyle(
            "HakikiHireMetricValue",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "finding": ParagraphStyle(
            "HakikiHireFinding",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=14,
            textColor=TEXT,
            leftIndent=7,
            bulletIndent=0,
        ),
    }


def _page_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.line(15 * mm, 12 * mm, 282 * mm, 12 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(SLATE)
    canvas.drawString(15 * mm, 7.5 * mm, "Hakiki Hire Government Portal")
    canvas.drawRightString(
        282 * mm,
        7.5 * mm,
        "Page {}".format(document.page),
    )
    canvas.restoreState()


def _header(
    styles: Mapping[str, ParagraphStyle],
    generated: datetime,
    reviewer: Mapping[str, Any],
) -> Table:
    reviewer_name = _display(
        reviewer.get("display_name") or reviewer.get("username"),
        "Authenticated reviewer",
    )
    reviewer_role = _display(reviewer.get("role"), "reviewer").capitalize()
    left = [
        Paragraph("HAKIKI HIRE INTELLIGENCE REPORT", styles["title"]),
        Paragraph(
            "Government review outcomes, integrity findings, and case register",
            styles["subtitle"],
        ),
    ]
    right = [
        Paragraph(
            "Generated: <b>{}</b> UTC".format(
                generated.strftime("%d %b %Y %H:%M")
            ),
            styles["subtitle"],
        ),
        Paragraph(
            "Prepared for: <b>{}</b> ({})".format(
                escape(reviewer_name),
                escape(reviewer_role),
            ),
            styles["subtitle"],
        ),
    ]
    table = Table([[left, right]], colWidths=[175 * mm, 95 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return table


def _report_metrics(cases: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    total = len(cases)
    outcomes = Counter(case.get("review_outcome") for case in cases)
    statuses = Counter(case.get("review_status") for case in cases)
    resolved = statuses.get("resolved", 0)
    return {
        "Total analysed": total,
        "Confirmed legitimate": outcomes.get("confirmed_legitimate", 0),
        "Confirmed scams": outcomes.get("confirmed_scam", 0),
        "Needs more evidence": outcomes.get("needs_more_evidence", 0),
        "Duplicate reports": outcomes.get("duplicate", 0),
        "Resolution rate": _format_percent(resolved, total),
    }


def _metric_cards(
    metrics: Mapping[str, Any],
    styles: Mapping[str, ParagraphStyle],
) -> Table:
    labels = list(metrics.keys())
    cells = []
    for label in labels:
        value = metrics[label]
        value_color = NAVY
        if label == "Confirmed legitimate":
            value_color = GREEN
        elif label == "Confirmed scams":
            value_color = RED
        elif label == "Needs more evidence":
            value_color = AMBER
        value_style = ParagraphStyle(
            "metric_{}".format(label.replace(" ", "_")),
            parent=styles["metric_value"],
            textColor=value_color,
        )
        cells.append(
            [
                Paragraph(escape(label.upper()), styles["metric_label"]),
                Paragraph(escape(str(value)), value_style),
            ]
        )
    table = Table([cells], colWidths=[45 * mm] * len(cells))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.7, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _filters_table(
    filters: Mapping[str, Any],
    styles: Mapping[str, ParagraphStyle],
) -> Table | Paragraph:
    active = [
        (key, value)
        for key, value in filters.items()
        if value not in {None, "", "All"} and key != "dates_invalid"
    ]
    if not active:
        return Paragraph("No filters were applied.", styles["body"])

    rows = []
    for key, value in active:
        rows.append(
            [
                Paragraph(
                    escape(key.replace("_", " ").title()),
                    styles["small"],
                ),
                Paragraph(_html(value), styles["body"]),
            ]
        )
    table = Table(rows, colWidths=[48 * mm, 222 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _outcome_counts(cases: Sequence[Mapping[str, Any]]) -> List[int]:
    counts = Counter(
        _label(case.get("review_outcome"), OUTCOME_LABELS, "Not yet decided")
        for case in cases
    )
    return [counts.get(label, 0) for label in OUTCOME_ORDER]


def _outcome_donut(cases: Sequence[Mapping[str, Any]]) -> Drawing:
    values = _outcome_counts(cases)
    drawing = Drawing(245, 175)
    drawing.add(String(8, 158, "DECISION OUTCOME DISTRIBUTION", fontName="Helvetica-Bold", fontSize=8, fillColor=NAVY))
    chart = Pie()
    chart.x = 20
    chart.y = 20
    chart.width = 130
    chart.height = 125
    chart.data = values
    chart.labels = ["{} ({})".format(label, value) for label, value in zip(OUTCOME_ORDER, values)]
    chart.slices.strokeWidth = 1
    chart.slices.strokeColor = WHITE
    for index, color in enumerate(OUTCOME_COLORS):
        chart.slices[index].fillColor = color
    chart.simpleLabels = 0
    chart.innerRadiusFraction = 0.58
    drawing.add(chart)
    drawing.add(String(173, 101, "TOTAL", fontName="Helvetica-Bold", fontSize=7, fillColor=SLATE))
    drawing.add(String(176, 79, str(sum(values)), fontName="Helvetica-Bold", fontSize=20, fillColor=NAVY))
    return drawing


def _confirmed_scams_by_country(cases: Sequence[Mapping[str, Any]]) -> Drawing:
    counts = Counter(
        _display(case.get("destination_country"), "Local or not provided")
        for case in cases
        if case.get("review_outcome") == "confirmed_scam"
    )
    top = counts.most_common(8)
    drawing = Drawing(285, 175)
    drawing.add(String(8, 158, "CONFIRMED SCAMS BY DESTINATION", fontName="Helvetica-Bold", fontSize=8, fillColor=NAVY))
    if not top:
        drawing.add(String(25, 83, "No confirmed scams in this reporting scope.", fontName="Helvetica", fontSize=9, fillColor=SLATE))
        return drawing

    labels = [label for label, _ in reversed(top)]
    values = [value for _, value in reversed(top)]
    chart = HorizontalBarChart()
    chart.x = 92
    chart.y = 24
    chart.width = 165
    chart.height = 115
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 6.5
    chart.categoryAxis.strokeColor = BORDER
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) + 1
    chart.valueAxis.valueStep = 1
    chart.valueAxis.labels.fontSize = 6
    chart.valueAxis.strokeColor = BORDER
    chart.bars[0].fillColor = RED
    drawing.add(chart)
    return drawing


def _verification_exposure(cases: Sequence[Mapping[str, Any]]) -> Drawing:
    counts = Counter(
        _label(case.get("verification_status"), VERIFICATION_LABELS)
        for case in cases
    )
    values = [counts.get(label, 0) for label in VERIFICATION_ORDER]
    drawing = Drawing(270, 185)
    drawing.add(String(8, 168, "VERIFICATION EXPOSURE", fontName="Helvetica-Bold", fontSize=8, fillColor=NAVY))
    chart = VerticalBarChart()
    chart.x = 38
    chart.y = 40
    chart.width = 210
    chart.height = 105
    chart.data = [values]
    chart.categoryAxis.categoryNames = ["Verified", "Unverified", "Blacklist", "Impersonation", "N/A"]
    chart.categoryAxis.labels.angle = 20
    chart.categoryAxis.labels.fontSize = 6
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values + [1]) + 1
    chart.valueAxis.valueStep = 1
    chart.valueAxis.labels.fontSize = 6
    chart.bars[0].fillColor = DARK_BLUE
    drawing.add(chart)
    return drawing


def _resolution_progress(cases: Sequence[Mapping[str, Any]]) -> Drawing:
    total = len(cases)
    resolved = sum(case.get("review_status") == "resolved" for case in cases)
    open_cases = total - resolved
    percentage = 0 if total == 0 else resolved / total

    drawing = Drawing(260, 185)
    drawing.add(String(8, 168, "REVIEW COMPLETION", fontName="Helvetica-Bold", fontSize=8, fillColor=NAVY))
    drawing.add(String(20, 119, "Resolved", fontName="Helvetica-Bold", fontSize=8, fillColor=GREEN))
    drawing.add(String(20, 99, str(resolved), fontName="Helvetica-Bold", fontSize=20, fillColor=NAVY))
    drawing.add(String(178, 119, "Open", fontName="Helvetica-Bold", fontSize=8, fillColor=SLATE))
    drawing.add(String(178, 99, str(open_cases), fontName="Helvetica-Bold", fontSize=20, fillColor=NAVY))
    drawing.add(String(20, 67, "Resolution rate: {}".format(_format_percent(resolved, total)), fontName="Helvetica-Bold", fontSize=9, fillColor=TEXT))
    from reportlab.graphics.shapes import Rect
    drawing.add(Rect(20, 38, 210, 14, fillColor=colors.HexColor("#E2E8F0"), strokeColor=None))
    drawing.add(Rect(20, 38, 210 * percentage, 14, fillColor=GREEN, strokeColor=None))
    return drawing


def _risk_outcome_table(
    cases: Sequence[Mapping[str, Any]],
    styles: Mapping[str, ParagraphStyle],
) -> Table:
    matrix: Dict[str, Counter] = defaultdict(Counter)
    for case in cases:
        risk = _label(case.get("risk_level"), RISK_LABELS)
        outcome = _label(case.get("review_outcome"), OUTCOME_LABELS, "Not yet decided")
        matrix[risk][outcome] += 1

    risk_order = ["High risk", "Suspicious", "Lower risk", "Not provided"]
    header = ["Risk level", *OUTCOME_ORDER, "Total"]
    rows: List[List[Any]] = [[Paragraph(escape(item), styles["table"]) for item in header]]
    for risk in risk_order:
        if risk not in matrix:
            continue
        values = [matrix[risk].get(outcome, 0) for outcome in OUTCOME_ORDER]
        rows.append(
            [Paragraph(escape(risk), styles["table"])]
            + [Paragraph(str(value), styles["table"]) for value in values]
            + [Paragraph(str(sum(values)), styles["table"])]
        )
    if len(rows) == 1:
        rows.append([Paragraph("No cases", styles["table"])] + [Paragraph("0", styles["table"])] * 6)

    table = Table(rows, colWidths=[34 * mm, 39 * mm, 34 * mm, 39 * mm, 32 * mm, 32 * mm, 18 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _key_findings(cases: Sequence[Mapping[str, Any]]) -> List[str]:
    if not cases:
        return ["No cases matched the selected reporting scope."]

    total = len(cases)
    outcomes = Counter(case.get("review_outcome") for case in cases)
    verification = Counter(case.get("verification_status") for case in cases)
    risk = Counter(case.get("risk_level") for case in cases)
    resolved = sum(case.get("review_status") == "resolved" for case in cases)

    findings = [
        "{} of {} analysed cases were confirmed scams ({}).".format(
            outcomes.get("confirmed_scam", 0),
            total,
            _format_percent(outcomes.get("confirmed_scam", 0), total),
        ),
        "{} cases involved blacklisted entities, and {} were marked as possible impersonation.".format(
            verification.get("blacklisted", 0),
            verification.get("possible_impersonation", 0),
        ),
        "{} of {} cases were resolved, producing a resolution rate of {}.".format(
            resolved,
            total,
            _format_percent(resolved, total),
        ),
    ]

    country_counts = Counter(
        _display(case.get("destination_country"), "Local or not provided")
        for case in cases
        if case.get("review_outcome") == "confirmed_scam"
    )
    if country_counts:
        country, count = country_counts.most_common(1)[0]
        findings.append(
            "{} had the highest confirmed-scam count in this report, with {} case{}.".format(
                country,
                count,
                "" if count == 1 else "s",
            )
        )

    labelled_risks = {
        _label(key, RISK_LABELS): value
        for key, value in risk.items()
        if key is not None
    }
    if labelled_risks:
        most_common_risk = max(labelled_risks, key=labelled_risks.get)
        findings.append(
            "{} was the most common risk category, covering {} case{}.".format(
                most_common_risk,
                labelled_risks[most_common_risk],
                "" if labelled_risks[most_common_risk] == 1 else "s",
            )
        )

    return findings


def _register_table(
    cases: Sequence[Mapping[str, Any]],
    styles: Mapping[str, ParagraphStyle],
    title: str,
) -> List[Any]:
    elements: List[Any] = [Paragraph(title, styles["heading"])]
    if not cases:
        elements.append(Paragraph("No cases in this section.", styles["body"]))
        return elements

    headers = [
        "Case ID",
        "Posting / entity",
        "Destination",
        "Risk",
        "Verification",
        "Status",
        "Outcome",
        "Reviewer",
        "Reviewed",
    ]
    rows: List[List[Any]] = [[Paragraph(item, styles["table"]) for item in headers]]
    for case in cases:
        rows.append(
            [
                Paragraph(_html(case.get("case_id"), "Unknown"), styles["table"]),
                Paragraph(
                    "<b>{}</b><br/>{}".format(
                        _html(case.get("title"), "Title not provided"),
                        _html(case.get("entity_name"), "Entity not provided"),
                    ),
                    styles["table"],
                ),
                Paragraph(_html(case.get("destination_country")), styles["table"]),
                Paragraph(escape(_label(case.get("risk_level"), RISK_LABELS)), styles["table"]),
                Paragraph(escape(_label(case.get("verification_status"), VERIFICATION_LABELS)), styles["table"]),
                Paragraph(escape(_label(case.get("review_status"), STATUS_LABELS)), styles["table"]),
                Paragraph(escape(_label(case.get("review_outcome"), OUTCOME_LABELS, "Not yet decided")), styles["table"]),
                Paragraph(_html(case.get("reviewer")), styles["table"]),
                Paragraph(escape(_format_datetime(case.get("reviewed_at"))), styles["table"]),
            ]
        )

    table = Table(
        rows,
        repeatRows=1,
        colWidths=[22 * mm, 56 * mm, 30 * mm, 25 * mm, 34 * mm, 22 * mm, 34 * mm, 30 * mm, 30 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GREY]),
                ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(table)
    return elements


def generate_summary_report_pdf(
    cases: Sequence[Mapping[str, Any]],
    stats: Mapping[str, Any] | None = None,
    filters: Mapping[str, Any] | None = None,
    reviewer: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> bytes:
    """Generate a stakeholder-ready Hakiki Hire intelligence report PDF.

    The optional ``stats`` argument is retained for compatibility with older
    dashboard calls. Report metrics are calculated from the filtered cases so
    the exported PDF always matches the visible report scope.
    """
    del stats

    case_rows = _normalise_cases(cases)
    generated = generated_at or datetime.now(timezone.utc)
    report_filters = dict(filters or {})
    reviewer_profile = dict(reviewer or {})
    styles = _styles()
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=17 * mm,
        title="Hakiki Hire Government Report",
        author="Hakiki Hire Government Portal",
        subject="Government review outcomes and case intelligence",
    )

    story: List[Any] = [
        _header(styles, generated, reviewer_profile),
        Spacer(1, 9),
        _metric_cards(_report_metrics(case_rows), styles),
        Paragraph("REPORT SCOPE", styles["heading"]),
        _filters_table(report_filters, styles),
        Spacer(1, 8),
    ]

    visual_table = Table(
        [[_outcome_donut(case_rows), _confirmed_scams_by_country(case_rows)]],
        colWidths=[133 * mm, 137 * mm],
    )
    visual_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([visual_table, Spacer(1, 8)])

    exposure_table = Table(
        [[_verification_exposure(case_rows), _resolution_progress(case_rows)]],
        colWidths=[137 * mm, 133 * mm],
    )
    exposure_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend(
        [
            exposure_table,
            Paragraph("RISK LEVEL VERSUS FINAL OUTCOME", styles["heading"]),
            _risk_outcome_table(case_rows, styles),
            Paragraph("KEY FINDINGS", styles["heading"]),
        ]
    )

    finding_elements = [
        Paragraph(escape(finding), styles["finding"], bulletText="•")
        for finding in _key_findings(case_rows)
    ]
    findings_box = Table([[finding_elements]], colWidths=[270 * mm])
    findings_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([findings_box, PageBreak()])

    watchlist = [
        case
        for case in case_rows
        if case.get("verification_status")
        in {"blacklisted", "possible_impersonation"}
    ]
    confirmed_scams = [
        case
        for case in case_rows
        if case.get("review_outcome") == "confirmed_scam"
    ]

    story.extend(_register_table(watchlist, styles, "Blacklist and impersonation watchlist"))
    story.append(Spacer(1, 10))
    story.extend(_register_table(confirmed_scams, styles, "Confirmed scam register"))
    story.append(PageBreak())
    story.extend(_register_table(case_rows, styles, "Complete report case register"))

    document.build(
        story,
        onFirstPage=_page_footer,
        onLaterPages=_page_footer,
    )
    return buffer.getvalue()
