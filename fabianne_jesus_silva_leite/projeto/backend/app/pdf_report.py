from html import escape
from io import BytesIO
from re import sub
from unicodedata import normalize
from urllib.parse import urlparse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.briefing import build_flight_plan, shorten_quote
from app.rag.schemas import FullAnalysisResponse


PDF_TEXT_PRIMARY = colors.HexColor("#000000")
PDF_TEXT_SECONDARY = colors.HexColor("#3F3F3D")
PDF_TEXT_MUTED = colors.HexColor("#5E5C63")
PDF_TEXT_ACCENT = colors.HexColor("#557B1E")


class PdfReportError(Exception):
    pass


def safe_pdf_filename(startup_name: str) -> str:
    normalized = normalize("NFKD", startup_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-")

    return slug.lower() or "startup"


def short_url(url: str, max_length: int = 62) -> str:
    parsed = urlparse(url)
    value = f"{parsed.netloc}{parsed.path}".strip("/")

    if len(value) <= max_length:
        return value

    return f"{value[:max_length - 3]}..."


def format_datetime(value) -> str:
    return value.strftime("%d/%m/%Y %H:%M UTC")


def build_styles():
    styles = getSampleStyleSheet()

    return {
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=29,
            textColor=PDF_TEXT_PRIMARY,
            spaceAfter=8,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=PDF_TEXT_MUTED,
            spaceAfter=12,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=20,
            textColor=PDF_TEXT_PRIMARY,
            spaceBefore=16,
            spaceAfter=9,
        ),
        "subsection": ParagraphStyle(
            "Subsection",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=PDF_TEXT_ACCENT,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=14,
            textColor=PDF_TEXT_SECONDARY,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=11.5,
            textColor=PDF_TEXT_MUTED,
            spaceAfter=5,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=PDF_TEXT_MUTED,
            alignment=TA_CENTER,
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=PDF_TEXT_PRIMARY,
            alignment=TA_CENTER,
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=styles["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8.7,
            leading=12.5,
            leftIndent=10,
            textColor=PDF_TEXT_MUTED,
            spaceAfter=5,
        ),
    }


def add_page_number(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#E3E8F0"))
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)

    canvas.setFillColor(PDF_TEXT_MUTED)
    canvas.setFont("Helvetica", 8)

    canvas.drawString(
        18 * mm,
        9 * mm,
        "NVIDIA Startup AI Radar",
    )

    canvas.drawRightString(
        A4[0] - 18 * mm,
        9 * mm,
        f"Página {document.page}",
    )

    canvas.restoreState()


def bullet_story(items: list[str], styles):
    return [
        Paragraph(f"- {escape(item)}", styles["body"])
        for item in items
    ]


def add_evidence_section(
    story,
    title: str,
    evidences,
    styles,
) -> None:
    if not evidences:
        return

    story.append(Paragraph(title, styles["subsection"]))

    for evidence in evidences[:1]:
        quote = Paragraph(
            escape(shorten_quote(evidence.quote)[:220]),
            styles["quote"],
        )

        url = escape(evidence.source_url, quote=True)
        label = escape(short_url(evidence.source_url, 48))

        source = Paragraph(
            (
                '<font color="#557B1E">'
                f'Fonte: <link href="{url}">{label}</link>'
                "</font>"
            ),
            styles["small"],
        )

        story.append(
            KeepTogether(
                [
                    quote,
                    source,
                    Spacer(1, 4),
                ],
            ),
        )


def build_metric_table(
    analysis: FullAnalysisResponse,
    styles,
) -> Table:
    classification = analysis.research.classification

    data = [
        [
            Paragraph("Classificação", styles["metric_label"]),
            Paragraph("AI-native", styles["metric_label"]),
            Paragraph("Wrapper risk", styles["metric_label"]),
            Paragraph("Oportunidade NVIDIA", styles["metric_label"]),
        ],
        [
            Paragraph(
                escape(classification.category),
                styles["metric_value"],
            ),
            Paragraph(
                str(classification.ai_native_score),
                styles["metric_value"],
            ),
            Paragraph(
                str(classification.wrapper_risk_score),
                styles["metric_value"],
            ),
            Paragraph(
                str(classification.nvidia_opportunity_score),
                styles["metric_value"],
            ),
        ],
    ]

    table = Table(data, colWidths=[42 * mm] * 4)

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.HexColor("#F8FAFF"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.6,
                    colors.HexColor("#D5DDEB"),
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    colors.HexColor("#E3E8F0"),
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ],
        ),
    )

    return table


def add_flight_plan(
    story,
    flight_plan,
    styles,
) -> None:
    story.extend(
        [
            PageBreak(),
            Paragraph(
                "NVIDIA Flight Plan - 90 dias",
                styles["section"],
            ),
            Paragraph(
                escape(flight_plan.summary),
                styles["body"],
            ),
        ],
    )

    for phase in flight_plan.phases:
        phase_content = [
            Paragraph(
                f"{escape(phase.period)} - {escape(phase.title)}",
                styles["subsection"],
            ),
            Paragraph(
                (
                    "<b>Objetivo:</b> "
                    f"{escape(phase.objective)}"
                ),
                styles["body"],
            ),
            Paragraph("<b>Ações:</b>", styles["body"]),
            *bullet_story(phase.actions, styles),
            Paragraph(
                "<b>Tecnologias NVIDIA relacionadas:</b>",
                styles["body"],
            ),
            *bullet_story(
                phase.nvidia_technologies,
                styles,
            ),
            Paragraph(
                "<b>Critérios de sucesso:</b>",
                styles["body"],
            ),
            *bullet_story(
                phase.success_criteria,
                styles,
            ),
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#E3E8F0"),
                spaceBefore=8,
                spaceAfter=8,
            ),
        ]

        story.append(KeepTogether(phase_content))

def build_full_analysis_pdf(
    analysis: FullAnalysisResponse,
) -> bytes:
    try:
        buffer = BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=23 * mm,
            title=(
                "NVIDIA Startup AI Radar - "
                f"{analysis.research.startup_name}"
            ),
            author="NVIDIA Startup AI Radar",
        )

        styles = build_styles()
        story = []

        research = analysis.research
        briefing = analysis.briefing
        classification = research.classification
        flight_plan = briefing.flight_plan

        if not flight_plan.phases:
            flight_plan = build_flight_plan(
                analysis.recommendations,
            )

        story.extend(
            [
                Paragraph(
                    "NVIDIA Startup AI Radar",
                    styles["cover_subtitle"],
                ),
                Paragraph(
                    (
                        "Startup Briefing - "
                        f"{escape(research.startup_name)}"
                    ),
                    styles["cover_title"],
                ),
                Paragraph(
                    (
                        "Relatório baseado em fontes públicas, "
                        "evidências validadas e documentação "
                        "oficial NVIDIA."
                    ),
                    styles["cover_subtitle"],
                ),
                Paragraph(
                    (
                        "Gerado em "
                        f"{format_datetime(briefing.generated_at)}"
                    ),
                    styles["small"],
                ),
                Spacer(1, 10),
                build_metric_table(analysis, styles),
                Spacer(1, 16),
                Paragraph("Resumo executivo", styles["section"]),
                Paragraph(
                    (
                        f"Foram coletadas "
                        f"{research.sources_successful} fontes públicas "
                        "com sucesso para esta análise. "
                        "A classificação resultante foi "
                        f"{classification.category}."
                    ),
                    styles["body"],
                ),
                Paragraph(
                    "Gaps e limites públicos",
                    styles["subsection"],
                ),
            ],
        )

        if research.gaps:
            story.extend(
                bullet_story(
                    [
                        f"{gap.category}: {gap.message}"
                        for gap in research.gaps
                    ],
                    styles,
                ),
            )
        else:
            story.append(
                Paragraph(
                    (
                        "Nenhum gap público relevante foi identificado "
                        "pelas regras atuais."
                    ),
                    styles["body"],
                ),
            )

        story.append(
            Paragraph(
                "Recomendações NVIDIA",
                styles["section"],
            ),
        )

        for position, recommendation in enumerate(
            analysis.recommendations.recommendations,
            start=1,
        ):
            story.extend(
                [
                    Paragraph(
                        (
                            f"{position}. "
                            f"{escape(recommendation.technology_name)}"
                        ),
                        styles["subsection"],
                    ),
                    Paragraph(
                        (
                            "<b>Prioridade:</b> "
                            f"{escape(recommendation.priority)} "
                            "| <b>Complexidade:</b> "
                            f"{escape(recommendation.complexity)}"
                        ),
                        styles["body"],
                    ),
                    Paragraph(
                        (
                            "<b>Justificativa técnica:</b> "
                            f"{escape(recommendation.technical_reason)}"
                        ),
                        styles["body"],
                    ),
                    Paragraph(
                        (
                            "<b>Justificativa de negócio:</b> "
                            f"{escape(recommendation.business_reason)}"
                        ),
                        styles["body"],
                    ),
                    Paragraph(
                        (
                            "<b>Próxima ação:</b> "
                            f"{escape(recommendation.next_action)}"
                        ),
                        styles["body"],
                    ),
                ],
            )

            add_evidence_section(
                story,
                "Evidências da startup",
                recommendation.startup_evidences,
                styles,
            )

            add_evidence_section(
                story,
                "Evidências NVIDIA",
                recommendation.nvidia_evidences,
                styles,
            )

            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.5,
                    color=colors.HexColor("#E3E8F0"),
                    spaceBefore=8,
                    spaceAfter=8,
                ),
            )

        add_flight_plan(
            story,
            flight_plan,
            styles,
        )

        story.append(
            Paragraph(
                "Limitações da análise",
                styles["section"],
            ),
        )

        if analysis.recommendations.limitations:
            story.extend(
                bullet_story(
                    analysis.recommendations.limitations,
                    styles,
                ),
            )
        else:
            story.append(
                Paragraph(
                    (
                        "A análise considera somente fontes públicas "
                        "e evidências recuperadas no momento da consulta."
                    ),
                    styles["body"],
                ),
            )

        document.build(
            story,
            onFirstPage=add_page_number,
            onLaterPages=add_page_number,
        )

        return buffer.getvalue()

    except Exception as error:
        raise PdfReportError(
            f"Não foi possível gerar o relatório em PDF: {error}",
        ) from error
