import type { ActionReportResult } from "@/lib/types";

type PdfColor = [number, number, number];

type PdfPage = {
  ops: string[];
};

type ReportSection = {
  title: string;
  lines: string[];
};

const PAGE_WIDTH = 595.28;
const PAGE_HEIGHT = 841.89;
const MARGIN_X = 48;
const FOOTER_Y = 34;
const PRIMARY: PdfColor = [0.462, 0.725, 0];
const TEXT: PdfColor = [0.12, 0.14, 0.12];
const MUTED: PdfColor = [0.38, 0.42, 0.38];
const BORDER: PdfColor = [0.82, 0.86, 0.78];

const WIN_ANSI_OVERRIDES: Record<number, number> = {
  0x20ac: 0x80,
  0x201a: 0x82,
  0x0192: 0x83,
  0x201e: 0x84,
  0x2026: 0x85,
  0x2020: 0x86,
  0x2021: 0x87,
  0x02c6: 0x88,
  0x2030: 0x89,
  0x0160: 0x8a,
  0x2039: 0x8b,
  0x0152: 0x8c,
  0x017d: 0x8e,
  0x2018: 0x91,
  0x2019: 0x92,
  0x201c: 0x93,
  0x201d: 0x94,
  0x2022: 0x95,
  0x2013: 0x96,
  0x2014: 0x97,
  0x02dc: 0x98,
  0x2122: 0x99,
  0x0161: 0x9a,
  0x203a: 0x9b,
  0x0153: 0x9c,
  0x017e: 0x9e,
  0x0178: 0x9f
};

export function exportActionReportPdf(report: ActionReportResult) {
  const builder = new ReportPdfBuilder(report);
  const pdf = builder.render();
  const blob = new Blob([pdf], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${sanitizeFileName(report.company_name || "relatorio-nvidia")}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

class ReportPdfBuilder {
  private readonly pages: PdfPage[] = [];
  private y = 0;

  constructor(private readonly report: ActionReportResult) {}

  render() {
    this.addPage();
    this.addCoverSummary();
    this.addReportSections();
    this.addConfidenceSection();
    this.addFooters();
    return buildPdf(this.pages);
  }

  private addCoverSummary() {
    const title = firstMarkdownTitle(this.report.markdown_report) || this.report.company_name || "Startup analisada";
    this.paragraph("NVIDIA Partnership Intelligence", {
      font: "F2",
      size: 10,
      color: PRIMARY,
      gapAfter: 4
    });
    this.paragraph(title, {
      font: "F2",
      size: 21,
      color: TEXT,
      gapAfter: 6,
      maxWidth: PAGE_WIDTH - MARGIN_X * 2
    });
    this.paragraph("Relatorio executivo de parceria", {
      size: 10,
      color: MUTED,
      gapAfter: 18
    });

    const context = this.report.context || {};
    const profile = objectValue(context.perfil_ideal);
    const focus = textValue(context.produto_alvo) || textValue(context.product) || "recomende voce mesmo";
    const generatedAt = this.report.generated_at
      ? new Date(this.report.generated_at).toLocaleString("pt-BR")
      : new Date().toLocaleString("pt-BR");
    const analystName = analystNameFromContext(this.report.context);
    const score =
      typeof this.report.score_ai_native === "number"
        ? `${Math.round(this.report.score_ai_native)}/100`
        : "Nao informado";

    this.metricGrid([
      { label: "Responsavel", value: analystName || "Nao informado" },
      { label: "Produto NVIDIA", value: focus },
      { label: "Score AI-Native", value: score },
      { label: "Coletado em", value: generatedAt },
      { label: "Setor alvo", value: textValue(profile?.setor) || "Nao informado" }
    ]);

    const summary = this.report.executive_summary || this.report.raw_report;
    if (summary) {
      this.sectionTitle("Resumo executivo");
      this.paragraph(summary, { gapAfter: 12 });
    }
  }

  private addReportSections() {
    const sections = this.sections();
    sections.forEach((section) => {
      this.sectionTitle(section.title);
      section.lines.forEach((line) => {
        if (line.startsWith("- ")) {
          this.bullet(line.replace(/^-\s+/, ""));
          return;
        }
        this.paragraph(cleanMarkdownText(line), { gapAfter: 6 });
      });
    });
  }

  private addConfidenceSection() {
    const benchmark = this.report.benchmark_competitivo;
    if (benchmark?.concorrentes?.length || benchmark?.posicionamento) {
      this.sectionTitle("Benchmark competitivo estruturado");
      benchmark.concorrentes?.forEach((competitor) => {
        const use =
          competitor.usa_nvidia === true
            ? "usa NVIDIA"
            : competitor.usa_nvidia === false
              ? "sem uso NVIDIA evidenciado"
              : "uso NVIDIA desconhecido";
        this.bullet(
          `${competitor.nome || "Concorrente nao informado"}: ${use}${
            competitor.fonte ? `. Fonte: ${competitor.fonte}` : ""
          }`
        );
      });
      if (benchmark.posicionamento) {
        this.paragraph(`Posicionamento: ${benchmark.posicionamento}`, { gapAfter: 10 });
      }
    }

    this.sectionTitle("Confiabilidade da analise");
    this.keyValue("Modelo", this.report.model || "Nao informado");
    this.keyValue("Dados cadastrais", reliabilityValue(this.report.confiabilidade, "dados_cadastrais"));
    this.keyValue("Fit NVIDIA", reliabilityValue(this.report.confiabilidade, "fit_nvidia"));
    this.keyValue(
      "Benchmark competitivo",
      reliabilityValue(this.report.confiabilidade, "benchmark_competitivo")
    );
  }

  private sections() {
    const sections = parseMarkdownSections(this.report.markdown_report || "");
    if (sections.length) return sections;

    const fallback: ReportSection[] = [];
    if (this.report.next_actions?.length) {
      fallback.push({
        title: "Proxima acao sugerida",
        lines: this.report.next_actions.map(
          (item) => `- ${item.action || "Acao nao informada"}: ${item.rationale || "Sem justificativa."}`
        )
      });
    }
    if (this.report.risks?.length) {
      fallback.push({ title: "Riscos e gaps", lines: this.report.risks.map((item) => `- ${item}`) });
    }
    if (this.report.nvidia_focus?.length) {
      fallback.push({
        title: "Fit com NVIDIA",
        lines: this.report.nvidia_focus.map((item) => `- ${item}`)
      });
    }
    return fallback;
  }

  private addPage() {
    const page: PdfPage = { ops: [] };
    this.pages.push(page);
    this.drawHeader(page, this.pages.length);
    this.y = this.pages.length === 1 ? 680 : 724;
  }

  private currentPage() {
    return this.pages[this.pages.length - 1];
  }

  private ensureSpace(height: number) {
    if (this.y - height < FOOTER_Y + 28) {
      this.addPage();
    }
  }

  private drawHeader(page: PdfPage, pageNumber: number) {
    const headerHeight = pageNumber === 1 ? 118 : 74;
    page.ops.push(rect(0, PAGE_HEIGHT - headerHeight, PAGE_WIDTH, headerHeight, [0.035, 0.047, 0.035], true));
    page.ops.push(rect(0, PAGE_HEIGHT - headerHeight, PAGE_WIDTH, 4, PRIMARY, true));
    page.ops.push(
      textOp(
        "F2",
        pageNumber === 1 ? 18 : 11,
        MARGIN_X,
        PAGE_HEIGHT - (pageNumber === 1 ? 48 : 36),
        pageNumber === 1 ? "Relatorio de Parceria NVIDIA" : "NVIDIA Partnership Intelligence",
        [1, 1, 1]
      )
    );
    page.ops.push(
      textOp(
        "F1",
        9,
        MARGIN_X,
        PAGE_HEIGHT - (pageNumber === 1 ? 68 : 52),
        pageNumber === 1
          ? "Benchmark competitivo, fit de produto e proxima acao recomendada"
          : this.report.company_name || "Relatorio executivo",
        [0.76, 0.82, 0.76]
      )
    );
  }

  private addFooters() {
    const total = this.pages.length;
    this.pages.forEach((page, index) => {
      page.ops.push(line(MARGIN_X, 50, PAGE_WIDTH - MARGIN_X, 50, BORDER));
      page.ops.push(textOp("F1", 8, MARGIN_X, FOOTER_Y, "Confidencial - NVIDIA scouting", MUTED));
      page.ops.push(
        textOp("F1", 8, PAGE_WIDTH - MARGIN_X - 64, FOOTER_Y, `Pagina ${index + 1}/${total}`, MUTED)
      );
    });
  }

  private sectionTitle(title: string) {
    this.ensureSpace(44);
    this.y -= 12;
    this.currentPage().ops.push(rect(MARGIN_X, this.y - 5, 4, 18, PRIMARY, true));
    this.currentPage().ops.push(textOp("F2", 13, MARGIN_X + 12, this.y, cleanMarkdownText(title), TEXT));
    this.y -= 22;
  }

  private paragraph(
    text: string,
    options: {
      font?: "F1" | "F2";
      size?: number;
      color?: PdfColor;
      gapAfter?: number;
      maxWidth?: number;
    } = {}
  ) {
    const size = options.size || 10;
    const font = options.font || "F1";
    const maxWidth = options.maxWidth || PAGE_WIDTH - MARGIN_X * 2;
    const lines = wrapText(cleanMarkdownText(text), maxWidth, size, font === "F2");
    const lineHeight = Math.max(12, size + 4);
    lines.forEach((wrappedLine) => {
      this.ensureSpace(lineHeight + (options.gapAfter ?? 8));
      this.currentPage().ops.push(textOp(font, size, MARGIN_X, this.y, wrappedLine, options.color || TEXT));
      this.y -= lineHeight;
    });
    this.y -= options.gapAfter ?? 8;
  }

  private bullet(text: string) {
    const size = 9.5;
    const left = MARGIN_X + 12;
    const lines = wrapText(cleanMarkdownText(text), PAGE_WIDTH - MARGIN_X * 2 - 18, size, false);
    const lineHeight = 13;
    lines.forEach((wrappedLine, index) => {
      this.ensureSpace(lineHeight + 5);
      if (index === 0) {
        this.currentPage().ops.push(textOp("F2", 10, MARGIN_X, this.y, "-", PRIMARY));
      }
      this.currentPage().ops.push(textOp("F1", size, left, this.y, wrappedLine, TEXT));
      this.y -= lineHeight;
    });
    this.y -= 6;
  }

  private keyValue(label: string, value: string) {
    this.ensureSpace(20);
    this.currentPage().ops.push(textOp("F2", 9, MARGIN_X, this.y, `${label}:`, TEXT));
    const lines = wrapText(value || "Nao informado", PAGE_WIDTH - MARGIN_X * 2 - 130, 9, false);
    lines.forEach((wrappedLine, index) => {
      this.currentPage().ops.push(textOp("F1", 9, MARGIN_X + 130, this.y - index * 12, wrappedLine, MUTED));
    });
    this.y -= Math.max(18, lines.length * 12 + 4);
  }

  private metricGrid(items: Array<{ label: string; value: string }>) {
    const gap = 10;
    const width = (PAGE_WIDTH - MARGIN_X * 2 - gap) / 2;
    const height = 54;
    const rows = Math.ceil(items.length / 2);
    this.ensureSpace(height * rows + gap * Math.max(0, rows - 1) + 14);
    items.forEach((item, index) => {
      const col = index % 2;
      const row = Math.floor(index / 2);
      const x = MARGIN_X + col * (width + gap);
      const y = this.y - row * (height + gap) - height;
      this.currentPage().ops.push(rect(x, y, width, height, [0.965, 0.98, 0.95], true));
      this.currentPage().ops.push(rect(x, y, width, height, BORDER, false));
      this.currentPage().ops.push(textOp("F2", 7.5, x + 12, y + height - 18, item.label.toUpperCase(), MUTED));
      wrapText(item.value, width - 24, 10, true)
        .slice(0, 2)
        .forEach((lineText, lineIndex) => {
          this.currentPage().ops.push(textOp("F2", 10, x + 12, y + height - 34 - lineIndex * 12, lineText, TEXT));
        });
    });
    this.y -= height * rows + gap * Math.max(0, rows - 1) + 18;
  }
}

function parseMarkdownSections(markdown: string): ReportSection[] {
  const sections: ReportSection[] = [];
  let current: ReportSection | undefined;

  markdown.split(/\r?\n/).forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) return;
    const heading = line.match(/^#{1,6}\s+(.+)$/);
    if (heading) {
      current = { title: cleanMarkdownText(heading[1]), lines: [] };
      sections.push(current);
      return;
    }
    if (!current) {
      current = { title: "Resumo executivo", lines: [] };
      sections.push(current);
    }
    current.lines.push(line);
  });

  return sections.filter((section) => section.lines.length > 0 || section.title);
}

function firstMarkdownTitle(markdown?: string) {
  if (!markdown) return undefined;
  const match = markdown.match(/^#{1,6}\s+(.+)$/m);
  return match ? cleanMarkdownText(match[1]) : undefined;
}

function cleanMarkdownText(value: string) {
  return value
    .replace(/\*\*/g, "")
    .replace(/`/g, "")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1 ($2)")
    .replace(/\s+/g, " ")
    .trim();
}

function objectValue(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function textValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function reliabilityValue(value: unknown, key: string) {
  const object = objectValue(value);
  const direct = object ? object[key] : undefined;
  if (typeof direct === "string" && direct.trim()) return direct.trim();
  if (direct && typeof direct === "object") return JSON.stringify(direct);
  return "Nao informado";
}

function analystNameFromContext(context: unknown) {
  const object = objectValue(context);
  const name = object?.analista_nome;
  return typeof name === "string" && name.trim() ? name.trim() : undefined;
}

function sanitizeFileName(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase()
    .slice(0, 80);
}

function wrapText(text: string, maxWidth: number, fontSize: number, bold: boolean) {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let lineText = "";

  words.forEach((word) => {
    const candidate = lineText ? `${lineText} ${word}` : word;
    if (measureText(candidate, fontSize, bold) <= maxWidth) {
      lineText = candidate;
      return;
    }
    if (lineText) lines.push(lineText);
    if (measureText(word, fontSize, bold) <= maxWidth) {
      lineText = word;
      return;
    }
    const chunks = splitLongWord(word, maxWidth, fontSize, bold);
    lines.push(...chunks.slice(0, -1));
    lineText = chunks[chunks.length - 1] || "";
  });

  if (lineText) lines.push(lineText);
  return lines.length ? lines : [""];
}

function splitLongWord(word: string, maxWidth: number, fontSize: number, bold: boolean) {
  const chunks: string[] = [];
  let chunk = "";
  Array.from(word).forEach((char) => {
    const candidate = `${chunk}${char}`;
    if (candidate && measureText(candidate, fontSize, bold) > maxWidth) {
      if (chunk) chunks.push(chunk);
      chunk = char;
      return;
    }
    chunk = candidate;
  });
  if (chunk) chunks.push(chunk);
  return chunks;
}

function measureText(text: string, fontSize: number, bold: boolean) {
  const base = bold ? 0.56 : 0.51;
  return Array.from(text).reduce((sum, char) => {
    if (char === " ") return sum + fontSize * 0.26;
    if (/[A-Z0-9]/.test(char)) return sum + fontSize * (base + 0.05);
    if (/[.,:;|!]/.test(char)) return sum + fontSize * 0.24;
    return sum + fontSize * base;
  }, 0);
}

function buildPdf(pages: PdfPage[]) {
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [0];
  const pageKids = pages.map((_, index) => `${5 + index * 2} 0 R`).join(" ");
  const maxObjectId = 4 + pages.length * 2;

  function addObject(id: number, body: string) {
    offsets[id] = pdf.length;
    pdf += `${id} 0 obj\n${body}\nendobj\n`;
  }

  addObject(1, "<< /Type /Catalog /Pages 2 0 R >>");
  addObject(2, `<< /Type /Pages /Kids [${pageKids}] /Count ${pages.length} >>`);
  addObject(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>");
  addObject(4, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>");

  pages.forEach((page, index) => {
    const pageObjectId = 5 + index * 2;
    const contentObjectId = pageObjectId + 1;
    const stream = page.ops.join("\n");
    addObject(
      pageObjectId,
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE_WIDTH} ${PAGE_HEIGHT}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${contentObjectId} 0 R >>`
    );
    addObject(contentObjectId, `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
  });

  const xrefOffset = pdf.length;
  pdf += `xref\n0 ${maxObjectId + 1}\n`;
  pdf += "0000000000 65535 f \n";
  for (let id = 1; id <= maxObjectId; id += 1) {
    pdf += `${String(offsets[id] || 0).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${maxObjectId + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;
  return pdf;
}

function textOp(font: "F1" | "F2", size: number, x: number, y: number, text: string, color: PdfColor) {
  return `${colorOp(color)}\nBT /${font} ${fixed(size)} Tf 1 0 0 1 ${fixed(x)} ${fixed(y)} Tm ${hexPdfString(
    text
  )} Tj ET`;
}

function line(x1: number, y1: number, x2: number, y2: number, color: PdfColor) {
  return `${strokeColorOp(color)}\n0.6 w ${fixed(x1)} ${fixed(y1)} m ${fixed(x2)} ${fixed(y2)} l S`;
}

function rect(x: number, y: number, width: number, height: number, color: PdfColor, fill: boolean) {
  return `${fill ? colorOp(color) : strokeColorOp(color)}\n${fixed(x)} ${fixed(y)} ${fixed(width)} ${fixed(
    height
  )} re ${fill ? "f" : "S"}`;
}

function colorOp(color: PdfColor) {
  return `${fixed(color[0])} ${fixed(color[1])} ${fixed(color[2])} rg`;
}

function strokeColorOp(color: PdfColor) {
  return `${fixed(color[0])} ${fixed(color[1])} ${fixed(color[2])} RG`;
}

function fixed(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function hexPdfString(value: string) {
  return `<${toWinAnsiBytes(value)
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")}>`;
}

function toWinAnsiBytes(value: string) {
  const bytes: number[] = [];
  Array.from(value.normalize("NFC")).forEach((char) => {
    const codePoint = char.codePointAt(0) || 0x3f;
    if (codePoint <= 0x7f) {
      bytes.push(codePoint);
      return;
    }
    if (codePoint >= 0xa0 && codePoint <= 0xff) {
      bytes.push(codePoint);
      return;
    }
    bytes.push(WIN_ANSI_OVERRIDES[codePoint] || 0x3f);
  });
  return bytes;
}
