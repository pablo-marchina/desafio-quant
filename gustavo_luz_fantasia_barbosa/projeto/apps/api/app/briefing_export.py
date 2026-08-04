from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN_X = 46
MARGIN_TOP = 54
CONTENT_WIDTH = PAGE_WIDTH - MARGIN_X * 2
FOOTER_Y = 30
MIN_Y = 58


@dataclass
class PdfLine:
    text: str
    style: str = "body"


STYLE = {
    "title": {"font": "F2", "size": 18, "leading": 24, "space_before": 0},
    "h2": {"font": "F2", "size": 13, "leading": 18, "space_before": 10},
    "h3": {"font": "F2", "size": 11, "leading": 16, "space_before": 8},
    "bullet": {"font": "F1", "size": 9, "leading": 13, "space_before": 1},
    "quote": {"font": "F1", "size": 9, "leading": 13, "space_before": 2},
    "body": {"font": "F1", "size": 9, "leading": 13, "space_before": 2},
}


def _clean_inline_markdown(value: str) -> str:
    value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    value = re.sub(r"`([^`]*)`", r"\1", value)
    return value.strip()


def _wrap_pdf_line(text: str, style: str) -> list[PdfLine]:
    style_config = STYLE[style]
    size = int(style_config["size"])
    width = max(42, int(CONTENT_WIDTH / (size * 0.52)))
    prefix = "- " if style == "bullet" else ""
    content = text[2:].strip() if prefix and text.startswith("- ") else text
    wrapped = textwrap.wrap(
        content,
        width=width - len(prefix),
        replace_whitespace=True,
        drop_whitespace=True,
    )
    if not wrapped:
        return [PdfLine("", style)]
    lines = [PdfLine(prefix + wrapped[0], style)]
    continuation_prefix = "  " if prefix else ""
    lines.extend(PdfLine(continuation_prefix + part, style) for part in wrapped[1:])
    return lines


def markdown_to_pdf_lines(markdown: str) -> list[PdfLine]:
    lines: list[PdfLine] = []
    for raw_line in markdown.splitlines():
        line = _clean_inline_markdown(raw_line)
        if not line:
            continue
        if line.startswith("# "):
            lines.extend(_wrap_pdf_line(line[2:], "title"))
            continue
        if line.startswith("## "):
            lines.extend(_wrap_pdf_line(line[3:], "h2"))
            continue
        if line.startswith("### "):
            lines.extend(_wrap_pdf_line(line[4:], "h3"))
            continue
        if line.startswith("> "):
            lines.extend(_wrap_pdf_line(f"Fonte: {line[2:]}", "quote"))
            continue
        if line.startswith("- "):
            lines.extend(_wrap_pdf_line(line, "bullet"))
            continue
        lines.extend(_wrap_pdf_line(line, "body"))
    return lines or [PdfLine("Briefing vazio.", "body")]


def pdf_safe_text(value: str) -> str:
    normalized = value.encode("cp1252", errors="replace").decode("cp1252")
    return (
        normalized.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _text_command(text: str, x: int, y: int, font: str, size: int) -> str:
    return f"0 0 0 rg BT /{font} {size} Tf {x} {y} Td ({pdf_safe_text(text)}) Tj ET"


def _line_command(x1: int, y1: int, x2: int, y2: int) -> str:
    return f"0.85 0.87 0.90 RG {x1} {y1} m {x2} {y2} l S"


def paginate_lines(lines: list[PdfLine]) -> list[list[PdfLine]]:
    pages: list[list[PdfLine]] = []
    current: list[PdfLine] = []
    y = PAGE_HEIGHT - MARGIN_TOP - 42

    for line in lines:
        style_config = STYLE[line.style]
        needed = int(style_config["leading"]) + int(style_config["space_before"])
        if current and y - needed < MIN_Y:
            pages.append(current)
            current = []
            y = PAGE_HEIGHT - MARGIN_TOP - 42
        current.append(line)
        y -= needed

    if current:
        pages.append(current)
    return pages or [[PdfLine("Briefing vazio.", "body")]]


def content_stream(lines: list[PdfLine], page_number: int, total_pages: int) -> bytes:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commands = [
        "0.96 0.97 0.95 rg 0 746 612 46 re f",
        _text_command("Seraphim Scout", MARGIN_X, 766, "F2", 12),
        _text_command("Briefing executivo", MARGIN_X, 750, "F1", 9),
        _line_command(MARGIN_X, 737, PAGE_WIDTH - MARGIN_X, 737),
    ]

    y = PAGE_HEIGHT - MARGIN_TOP - 42
    for line in lines:
        style_config = STYLE[line.style]
        y -= int(style_config["space_before"])
        font = str(style_config["font"])
        size = int(style_config["size"])
        leading = int(style_config["leading"])
        x = MARGIN_X + (12 if line.style == "bullet" else 0)
        if line.style == "h2":
            commands.append(_line_command(MARGIN_X, y + 12, PAGE_WIDTH - MARGIN_X, y + 12))
        commands.append(_text_command(line.text, x, y, font, size))
        y -= leading

    footer = f"Gerado em {generated_at} - pagina {page_number}/{total_pages}"
    commands.extend(
        [
            _line_command(MARGIN_X, FOOTER_Y + 14, PAGE_WIDTH - MARGIN_X, FOOTER_Y + 14),
            _text_command(footer, MARGIN_X, FOOTER_Y, "F1", 8),
        ]
    )
    return "\n".join(commands).encode("cp1252", errors="replace")


def build_pdf(markdown: str) -> bytes:
    pages = paginate_lines(markdown_to_pdf_lines(markdown))
    objects: list[bytes] = []
    page_object_ids = []

    # 1: Catalog, 2: Pages, 3: Helvetica, 4: Helvetica-Bold.
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    next_object_id = 5
    for page_lines in pages:
        page_id = next_object_id
        content_id = next_object_id + 1
        page_object_ids.append(page_id)
        next_object_id += 2

        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        stream = content_stream(page_lines, len(page_object_ids), len(pages))
        objects.append(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode(
        "ascii"
    )

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)
