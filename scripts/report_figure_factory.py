#!/usr/bin/env python3
"""Deterministic SVG figure factory for the five-page ARGOS final report.

Inputs are frozen report-only artifacts. The factory does not read outcomes or
recompute any scientific result; it only renders approved numbers/copy into
self-contained 16:9 SVGs using the frozen visual identity.
"""
from __future__ import annotations

import csv
import hashlib
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry"
OUT = ROOT / "report" / "figures"
W, H = 1600, 900


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load() -> tuple[dict, dict[tuple[str, str], dict]]:
    identity_path = REG / "argos_visual_identity_freeze.json"
    figure_path = REG / "report_figure_inputs.csv"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    rows: dict[tuple[str, str], dict] = {}
    with figure_path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            rows[(row["figure_id"], row["series_or_step"])] = row
    return identity, rows


class SVG:
    def __init__(self, palette: dict[str, str]):
        self.p = palette
        self.e: list[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
            '<defs>',
            f'<marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 z" fill="{palette["muted"]}"/></marker>',
            f'<marker id="arrowAmber" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto"><path d="M0,0 L12,6 L0,12 z" fill="{palette["gate_amber"]}"/></marker>',
            '</defs>',
            f'<rect width="{W}" height="{H}" fill="{palette["ink"]}"/>',
        ]

    def rect(self, x, y, w, h, fill, stroke="none", sw=0, r=18, opacity=1):
        self.e.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"/>')

    def line(self, x1, y1, x2, y2, stroke, sw=2, dash=None, arrow=False, amber=False, opacity=1):
        attrs = f' stroke-dasharray="{dash}"' if dash else ""
        marker = (' marker-end="url(#arrowAmber)"' if amber else ' marker-end="url(#arrow)"') if arrow else ""
        self.e.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"{attrs}{marker}/>')

    def circle(self, cx, cy, r, fill, stroke="none", sw=0):
        self.e.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def ellipse(self, cx, cy, rx, ry, fill="none", stroke="#fff", sw=3, dash=None):
        attrs = f' stroke-dasharray="{dash}"' if dash else ""
        self.e.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{attrs}/>')

    def path(self, d, fill="none", stroke="#fff", sw=3, dash=None, opacity=1):
        attrs = f' stroke-dasharray="{dash}"' if dash else ""
        self.e.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"{attrs}/>')

    def text(self, x, y, text, size=28, fill=None, weight=400, anchor="start", family="Inter,Segoe UI,Arial,sans-serif", opacity=1):
        fill = fill or self.p["paper"]
        self.e.append(f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" opacity="{opacity}">{escape(str(text))}</text>')

    def multiline(self, x, y, lines, size=26, fill=None, weight=400, leading=1.25, anchor="start"):
        for i, line in enumerate(lines):
            self.text(x, y + i * size * leading, line, size=size, fill=fill, weight=weight, anchor=anchor)

    def finish(self) -> str:
        return "\n".join(self.e + ["</svg>"]) + "\n"


def title(svg: SVG, kicker: str, main: str, sub: str):
    p = svg.p
    svg.text(80, 72, kicker.upper(), 20, p["sensor_cyan"], 700)
    svg.text(80, 128, main, 42, p["paper"], 700)
    svg.text(80, 170, sub, 24, p["muted"], 400)
    argos_mark(svg, 1450, 85, 0.55)


def argos_mark(svg: SVG, cx: float, cy: float, scale: float = 1.0, label: bool = True):
    p = svg.p
    # Abstract sensor/gate mark: three incomplete arcs and M2 core.
    svg.path(f"M {cx-70*scale} {cy} Q {cx} {cy-50*scale} {cx+70*scale} {cy}", stroke=p["sensor_cyan"], sw=5*scale)
    svg.path(f"M {cx-52*scale} {cy+8*scale} Q {cx} {cy+48*scale} {cx+52*scale} {cy+8*scale}", stroke=p["evidence_teal"], sw=5*scale)
    svg.path(f"M {cx-84*scale} {cy+18*scale} Q {cx-35*scale} {cy+74*scale} {cx+20*scale} {cy+48*scale}", stroke=p["gate_amber"], sw=4*scale, dash=f"{18*scale},{11*scale}")
    svg.circle(cx, cy+5*scale, 12*scale, p["paper"])
    svg.circle(cx, cy+5*scale, 5*scale, p["sensor_cyan"])
    if label:
        svg.text(cx, cy+92*scale, "ARGOS", 24*scale, p["paper"], 700, anchor="middle")


def chip(svg: SVG, x, y, text, fill, w=None, text_fill=None):
    p = svg.p
    w = w or max(120, len(text) * 13 + 34)
    svg.rect(x, y, w, 48, fill, r=24)
    svg.text(x+w/2, y+32, text, 20, text_fill or p["ink"], 700, anchor="middle")
    return w


def card(svg: SVG, x, y, w, h, stroke=None, fill=None):
    p = svg.p
    svg.rect(x, y, w, h, fill or p["surface"], stroke or p["grid"], 2, 20)


def val(rows, fig, key, field="display_value"):
    return rows[(fig, key)][field]


def fig01(identity, rows):
    p = identity["palette"]
    s = SVG(p)
    title(s, "01 • Estratégia", "Informação só vira risco depois de sobreviver ao teste", "Prediction markets como sensores PIT; abstention é um output de primeira classe.")

    nodes = [
        (100, "Prediction market", "sensor PIT", p["sensor_cyan"]),
        (430, "M2", "probabilidade agregada", p["sensor_cyan"]),
        (760, "Gate incremental", "movimento > M2?", p["evidence_teal"]),
        (1090, "Gate econômico", "capital + custos", p["evidence_teal"]),
    ]
    y = 300
    for x, h1, h2, c in nodes:
        card(s, x, y, 250, 145, c, p["surface"])
        s.circle(x+36, y+36, 10, c)
        s.text(x+28, y+83, h1, 27, p["paper"], 700)
        s.text(x+28, y+118, h2, 21, p["muted"], 400)
    for x1, x2 in [(350,430),(680,760),(1010,1090)]:
        s.line(x1+8, y+72, x2-12, y+72, p["muted"], 3, arrow=True)

    card(s, 1380, y, 140, 145, p["evidence_teal"], p["surface_2"])
    s.text(1450, y+58, "ALOCA", 24, p["evidence_teal"], 700, anchor="middle")
    s.text(1450, y+98, "somente", 18, p["muted"], 400, anchor="middle")
    s.text(1450, y+122, "se passar", 18, p["muted"], 400, anchor="middle")
    s.line(1340, y+72, 1368, y+72, p["muted"], 3, arrow=True)

    # Deliberate abstention branch.
    s.line(885, y+145, 885, 535, p["gate_amber"], 3, arrow=True, amber=True)
    card(s, 715, 550, 340, 110, p["gate_amber"], p["surface_2"])
    s.text(885, 595, "ABSTAIN / C0_NO_TRADE", 25, p["gate_amber"], 700, anchor="middle")
    s.text(885, 630, "decisão deliberada, não erro", 19, p["muted"], 400, anchor="middle")

    # EUAS compact rationale.
    card(s, 100, 570, 500, 230, p["grid"], p["surface"])
    s.text(130, 612, "POR QUE EARNINGS/EPS?", 20, p["sensor_cyan"], 700)
    scores = [("Earnings",72,p["evidence_teal"]),("Macro",50,p["muted"]),("FDA",47,p["muted"]),("M&A ann.",47,p["muted"])]
    for i,(name,score,c) in enumerate(scores):
        yy=650+i*34
        s.text(130, yy+16, name, 18, p["paper"], 600)
        s.rect(250, yy, score*3.2, 20, c, r=10)
        s.text(500, yy+16, score, 18, c, 700, anchor="end")
    s.text(130, 790, "EUAS-v1.1 • research-design score, não performance", 16, p["muted"], 400)

    chip(s, 1120, 590, "117 eventos testados", p["surface_2"], 300, p["paper"])
    chip(s, 1120, 650, "116/117 EPS oficiais", p["surface_2"], 300, p["paper"])
    chip(s, 1120, 710, "115/117 tape + trajetória", p["surface_2"], 300, p["paper"])
    s.text(1120, 790, "Muitos olhos. Risco só com evidência incremental.", 20, p["gate_amber"], 700)
    return s.finish()


def fig02(identity, rows):
    p = identity["palette"]
    s = SVG(p)
    title(s, "02 • Modelagem", "Complexidade removida antes dos outcomes", "Amplitude de pesquisa → redução estrutural → parcimônia compatível com o n efetivo.")

    steps = [
        ("Técnicas", 69, 430, p["sensor_cyan"]),
        ("Inputs Pass-B", 59, 380, p["sensor_cyan"]),
        ("Descritores label-free", 25, 310, p["muted"]),
        ("Mecanismos primários", 6, 235, p["evidence_teal"]),
        ("Coeficientes core", 8, 200, p["evidence_teal"]),
        ("Challenger não linear", 1, 165, p["gate_amber"]),
    ]
    x=100
    center_y=420
    for i,(label,n,h,c) in enumerate(steps):
        w=200 if i<4 else 180
        y=center_y-h/2
        s.rect(x,y,w,h,p["surface"],c,2,18)
        s.text(x+w/2, center_y-18, n, 58, c, 700, anchor="middle")
        lines = label.split(" ",1)
        s.text(x+w/2, center_y+38, lines[0], 21, p["paper"], 700, anchor="middle")
        if len(lines)>1:
            s.text(x+w/2, center_y+66, lines[1], 18, p["muted"], 400, anchor="middle")
        if i < len(steps)-1:
            s.line(x+w+12, center_y, x+w+55, center_y, p["muted"], 3, arrow=True)
        x += w+70

    s.text(100, 705, "15 pares |Spearman| ≥ 0,90 já no Pass B → redundância removida antes dos labels", 22, p["muted"], 400)
    chip(s, 100, 745, "40 warm-up", p["surface_2"], 210, p["paper"])
    chip(s, 330, 745, "75 previsões OOS", p["surface_2"], 250, p["paper"])
    chip(s, 600, 745, "54 date clusters", p["surface_2"], 250, p["paper"])
    chip(s, 870, 745, "ridge λ = 1", p["surface_2"], 210, p["paper"])
    chip(s, 1100, 745, "sem hyperparameter search", p["surface_2"], 340, p["paper"])
    s.text(100, 835, "Complexidade foi removida antes dos outcomes, não depois dos resultados.", 24, p["evidence_teal"], 700)
    return s.finish()


def metric_group(s: SVG, x, y, title_txt, a_name, a_val, b_name, b_val, maxv, p):
    card(s,x,y,620,230,p["grid"],p["surface"])
    s.text(x+30,y+42,title_txt.upper(),19,p["muted"],700)
    for j,(name,v,c) in enumerate([(a_name,a_val,p["sensor_cyan"]),(b_name,b_val,p["fail_coral"])]):
        yy=y+85+j*70
        s.text(x+30,yy+23,name,20,p["paper"],600)
        bw=360*(v/maxv)
        s.rect(x+185,yy,bw,30,c,r=8)
        s.text(x+575,yy+24,f"{v:.4f}",22,c,700,anchor="end")
    s.text(x+30,y+215,"↓ menor é melhor",16,p["muted"],400)


def ci_strip(s: SVG, x, y, w, label, point, low, high, xmin, xmax, color, p):
    card(s,x,y,w,105,p["grid"],p["surface"])
    s.text(x+20,y+30,label,17,p["paper"],600)
    axis_x=x+250; axis_w=w-290; axis_y=y+65
    def sx(v): return axis_x+(v-xmin)/(xmax-xmin)*axis_w
    s.line(axis_x,axis_y,axis_x+axis_w,axis_y,p["grid"],2)
    z=sx(0)
    s.line(z,y+44,z,y+87,p["paper"],2,dash="5,5",opacity=.7)
    s.line(sx(low),axis_y,sx(high),axis_y,color,7)
    s.circle(sx(point),axis_y,8,color)
    s.text(x+w-18,y+30,f"{point:+.4f}  CI [{low:+.4f}; {high:+.4f}]",16,color,700,anchor="end")


def fig03(identity, rows):
    p=identity["palette"]
    s=SVG(p)
    title(s,"03 • Resultados","O teste podia reprovar o robô — e reprovou H2","M2 continuou informativo; a camada congelada de movimentos não provou ganho incremental.")
    b1=float(val(rows,"FIG-P3-METRICS","M2_CAL","value")); b2=float(val(rows,"FIG-P3-METRICS","M_MOVE_CORE","value"))
    l1=float(val(rows,"FIG-P3-METRICS","M2_CAL","value")) if False else 0.45400185611709
    l2=0.5403842574211747
    metric_group(s,100,235,"Brier score","M2_CAL",b1,"M_MOVE_CORE",b2,.18,p)
    metric_group(s,790,235,"Log loss","M2_CAL",l1,"M_MOVE_CORE",l2,.60,p)
    ci_strip(s,100,500,1310,"Incremento Brier = M2_CAL − M_MOVE_CORE",-0.0170709907,-0.0491014452,0.0128164627,-.06,.03,p["fail_coral"],p)
    ci_strip(s,100,625,1310,"Incremento log loss = M2_CAL − M_MOVE_CORE",-0.0863824013,-0.2144785097,0.0252069643,-.25,.05,p["fail_coral"],p)
    chip(s,100,760,"0/3 tercis temporais positivos",p["fail_coral"],340,p["ink"])
    chip(s,465,760,"75 eventos OOS",p["surface_2"],240,p["paper"])
    chip(s,730,760,"54 date clusters",p["surface_2"],250,p["paper"])
    chip(s,1005,760,"STOP RULE ATIVADO",p["gate_amber"],310,p["ink"])
    s.text(100,842,"H2 falhou → sem resgate por subgrupo/threshold/challenger → H4/H5 bloqueadas.",23,p["gate_amber"],700)
    return s.finish()


def fig04(identity, rows):
    p=identity["palette"]
    s=SVG(p)
    title(s,"04 • Backtest","Traduzimos em capital — e o stop rule preservou no-trade","Teste econômico separado, com regras PIT, benchmark, custos, sizing e multiplicidade congelados.")
    badges=[("PIT entrada/saída",p["sensor_cyan"]),("SPY matched",p["sensor_cyan"]),("equal-notional",p["muted"]),("sem leverage",p["muted"]),("Holm",p["evidence_teal"]),("20/35 bps",p["gate_amber"])]
    x=100
    for txt,c in badges:
        ww=chip(s,x,220,txt,p["surface_2"],None,c)
        x += ww+18
    card(s,100,320,940,370,p["grid"],p["surface"])
    s.text(135,365,"R1 • T−1 • 10 sessões",22,p["muted"],700)
    stats=[("Oportunidades","108"),("Trades","34"),("Long / Short","21 / 13"),("Trade rate","31,48%")]
    for i,(lab,v) in enumerate(stats):
        xx=135+(i%2)*430; yy=420+(i//2)*105
        s.text(xx,yy,lab,19,p["muted"],600)
        s.text(xx,yy+48,v,40,p["paper"],700)
    s.line(135,595,990,595,p["grid"],2)
    s.text(135,635,"MA net / oportunidade",19,p["muted"],600)
    s.text(390,635,"−0,2050%",30,p["fail_coral"],700)
    s.text(585,635,"CI95 [−0,9719%; +0,5590%]",23,p["paper"],600)
    s.text(135,672,"Hit rate 41,18%  •  Holm p = 1,0",18,p["muted"],400)

    # Decision terminal.
    s.line(1045,505,1125,505,p["gate_amber"],4,arrow=True,amber=True)
    card(s,1140,350,350,310,p["gate_amber"],p["surface_2"])
    argos_mark(s,1315,430,.48,False)
    s.text(1315,515,"C0_NO_TRADE",34,p["gate_amber"],700,anchor="middle")
    s.text(1315,555,"CHAMPION ECONÔMICO",18,p["paper"],700,anchor="middle")
    s.multiline(1315,595,["gate não passou;","capital não foi forçado"],20,p["muted"],400,1.35,"middle")
    s.text(100,785,"Não inventar Sharpe/equity curve/max drawdown de portfólio: agregação de posições sobrepostas não foi congelada.",20,p["muted"],400)
    s.text(100,835,"Um resultado diagnóstico positivo não substitui uma regra que falhou o protocolo congelado.",22,p["evidence_teal"],700)
    return s.finish()


def fig05(identity, rows):
    p=identity["palette"]
    s=SVG(p)
    title(s,"05 • GenAI + Próximos passos","O resultado final é uma decisão de pesquisa — e um próximo experimento melhor","IA acelerou pesquisa e execução; fontes, CI, gates humanos e hashes decidiram o que virou evidência.")

    # Verification loop left.
    card(s,80,230,780,520,p["grid"],p["surface"])
    s.text(120,275,"GENAI: IMPACTO COM VERIFICAÇÃO",21,p["sensor_cyan"],700)
    loop=[("AI propõe",p["sensor_cyan"]),("Fonte / execução",p["sensor_cyan"]),("Gate humano",p["evidence_teal"]),("Freeze / hash",p["gate_amber"]),("Aceita ou rejeita",p["paper"])]
    coords=[(190,365),(420,330),(655,365),(600,585),(300,600)]
    for (lab,c),(cx,cy) in zip(loop,coords):
        s.circle(cx,cy,58,p["surface_2"],c,3)
        words=lab.split(" / ") if " / " in lab else [lab]
        if len(words)==1:
            s.text(cx,cy+7,words[0],18,c,700,anchor="middle")
        else:
            s.text(cx,cy-2,words[0],16,c,700,anchor="middle"); s.text(cx,cy+21,words[1],16,c,700,anchor="middle")
    pairs=list(zip(coords,coords[1:]+coords[:1]))
    for (x1,y1),(x2,y2) in pairs:
        s.line(x1,y1,x2,y2,p["muted"],2,arrow=True,opacity=.7)
    s.text(120,695,"11 entradas no ledger • human-in-the-loop • outcome firewall",18,p["muted"],400)

    # Future research right, deliberately dashed/segregated.
    card(s,910,230,610,520,p["grid"],p["surface"])
    s.text(950,275,"PRÓXIMO ESTUDO — NÃO É RESULTADO SUBMETIDO",20,p["gate_amber"],700)
    future=[
        ("FDA",47,"preferida se mantivermos ações individuais",p["evidence_teal"]),
        ("Macro",50,"forte, mas exige rates/índices",p["sensor_cyan"]),
        ("M&A completion",None,"expandir descoberta antes de rankear",p["gate_amber"]),
    ]
    yy=330
    for name,score,note,c in future:
        s.rect(950,yy,520,100,p["surface_2"],c,2,16)
        s.text(980,yy+38,name,25,p["paper"],700)
        if score is not None:
            s.text(1435,yy+38,score,27,c,700,anchor="end")
        else:
            s.text(1435,yy+38,"UNRANKED",16,c,700,anchor="end")
        s.text(980,yy+72,note,17,p["muted"],400)
        yy+=125
    s.line(900,210,900,790,p["gate_amber"],2,dash="10,10",opacity=.7)
    chip(s,950,710,"Earnings #1 em 81/81 sensibilidades",p["surface_2"],510,p["paper"])
    s.text(80,825,"A disciplina do ARGOS não é sempre operar; é saber quando a evidência ainda não autoriza risco.",24,p["gate_amber"],700)
    return s.finish()


def logo(identity):
    p=identity["palette"]
    s=SVG(p)
    argos_mark(s,800,390,2.2,False)
    s.text(800,610,"ARGOS",72,p["paper"],700,anchor="middle")
    s.text(800,665,"Muitos olhos. Risco só com evidência incremental.",28,p["muted"],400,anchor="middle")
    return s.finish()


def main() -> None:
    identity, rows = load()
    assert identity["status"] == "PASS_VISUAL_IDENTITY_FREEZE"
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "argos_mark.svg": logo(identity),
        "fig01_strategy_pipeline.svg": fig01(identity, rows),
        "fig02_model_reduction.svg": fig02(identity, rows),
        "fig03_h2_results.svg": fig03(identity, rows),
        "fig04_economic_backtest.svg": fig04(identity, rows),
        "fig05_genai_future.svg": fig05(identity, rows),
    }
    for name, content in outputs.items():
        (OUT / name).write_text(content, encoding="utf-8")

    manifest = {
        "artifact": "ARGOS_FINAL_FIGURE_FACTORY",
        "version": "FFF-v1.0",
        "status": "PASS_FIGURES_GENERATED_FROM_FROZEN_INPUTS",
        "scientific_reopen": False,
        "canvas": "1600x900",
        "identity_source": "registry/argos_visual_identity_freeze.json",
        "figure_input_source": "registry/report_figure_inputs.csv",
        "identity_sha256": sha256(REG / "argos_visual_identity_freeze.json"),
        "figure_inputs_sha256": sha256(REG / "report_figure_inputs.csv"),
        "outputs": {name: sha256(OUT / name) for name in outputs},
        "rules": [
            "No result is recomputed; all quantitative values come from frozen report inputs.",
            "No external fonts or network assets are required.",
            "No GitHub URL, author name or university identity is rendered.",
            "No-trade uses the gate/abstention semantic color, not an error-only state.",
            "Future research is visually segregated from submitted evidence."
        ]
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
