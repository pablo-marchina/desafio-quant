"""Gera `data/eval/REVISAO-ROTULOS.md` — folha de revisão humana do eval set (F1.12/F7.1/F7.7).

Motivo (2026-06-22): `label_source: human` afirma revisão humana, mas as entradas reais foram
auto-rotuladas pelo pipeline e **promovidas** sem o humano (você) ter conferido linha a linha. Até
essa conferência, o `human` é aspiracional. Este script emite um documento escaneável (rótulo +
prioridade F7.7 + evidência) para você marcar concordo/ajustar por entrada — completá-lo torna a
proveniência honesta. Puro/offline (só lê os YAML versionados). Re-rode quando um rótulo mudar.

    python scripts/gen_label_review.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.eval.dataset import LabeledStartup, load_eval_set  # noqa: E402

_OUT = Path(__file__).resolve().parents[1] / "data" / "eval" / "REVISAO-ROTULOS.md"
_EMO = {"alta": "🔴", "media": "🟡", "baixa": "⚪"}


def _techs(e: LabeledStartup) -> str:
    if not e.expected_techs:
        return "_(nenhuma — fora do escopo de prescrição: periférico/non-AI ou wrapper frágil)_"
    return " · ".join(
        f"{_EMO[t.prioridade.value] if t.prioridade else '·'} {t.tech}" for t in e.expected_techs
    )


def _aimi(e: LabeledStartup) -> str:
    a = e.aimi
    return (
        f"P1 data_moat **{a.data_moat}** · P2 workflow **{a.workflow_depth}** · "
        f"P3 tech_opt **{a.technical_optimization}** · P4 distrib **{a.distribution_moat}** "
        f"(total {a.total})"
    )


def _real_block(e: LabeledStartup) -> str:
    src = "✅ human" if e.label_source == "human" else "⚠️ model (pendente, fora do headline)"
    lines = [
        f"### {e.nome} · `{e.region.value}` · {e.classificacao.value}",
        "",
        f"- **Setor / país:** {e.setor} ({e.pais}) — origem do rótulo: {src}",
        f"- **AIMI:** {_aimi(e)}",
        f"- **Techs (prioridade):** {_techs(e)}",
        f"- **Por quê (rationale):** {e.rationale.strip()}",
    ]
    if e.evidence_urls:
        lines.append("- **Evidência:** " + " · ".join(e.evidence_urls))
    if e.notes:
        lines.append(f"- **Notas:** {e.notes.strip()}")
    lines += ["- **Sua revisão:** ☐ concordo  ☐ ajustar → _______________________", ""]
    return "\n".join(lines)


def main() -> int:
    entries = load_eval_set(include_model=True)
    reais = sorted((e for e in entries if not e.synthetic), key=lambda e: (e.region.value, e.nome))
    synth = sorted((e for e in entries if e.synthetic), key=lambda e: (e.region.value, e.id))

    out: list[str] = []
    out.append("# Revisão de rótulos do eval set (F1.12 / F7.1 / F7.7)")
    out.append("")
    out.append(
        f"> Gerado por `scripts/gen_label_review.py` em {date.today().isoformat()}. **Objetivo:** "
        "você (revisor humano) confere CADA rótulo e marca concordo/ajustar. Até esta revisão, "
        "`label_source: human` é **aspiracional** para as reais — completá-la torna a proveniência "
        "honesta."
    )
    out.append(">")
    out.append(
        "> **Prioridade das techs (F7.7):** 🔴 ALTA = a alavanca NVIDIA da empresa (entra no "
        "`recall@ALTA`) · 🟡 MÉDIA = complemento · ⚪ BAIXA = leque que o §5.5 emite por completude. "
        "Ancorada no **gap do perfil**, não na saída da regra (anti-circularidade)."
    )
    out.append(">")
    out.append(
        "> **Definições que resolvem tensões aparentes** (aplique-as ao revisar — evitam falso-positivo "
        "de inconsistência): **AI-native** (`classifier.md`) = IA é o *núcleo do valor/produto*, **não** "
        "'IA própria' → uma plataforma que orquestra NLP de terceiros mas cuja conversa **é** o produto "
        "é AI-native **e** wrapper (a região captura a falta de moat). **P3 / Technical Optimization** "
        "(rubrica AIMI, `docs/ARQUITETURA.md §3.6`) = *serving/otimização de inferência próprios* (self-host/Triton/"
        "TensorRT/quantização), **não** posse de modelos → quem tem modelo próprio mas serve em cloud "
        "fica **P3 baixo** (o moat de modelo é P1, não P3). **NeMo Guardrails** entra quando há "
        "*superfície generativa/conversacional* ao usuário (copiloto/chat/gerador = risco de "
        "comportamento); features **discriminativas** (classificação/recomendação/predição) **não** "
        "recebem; *wrapper frágil* (P1 **e** P2 ≤ 6) recebe só setor (gate de prioridade)."
    )
    out.append("")
    out.append(f"## A. Empresas REAIS (headline) — {len(reais)} entradas")
    out.append("")
    out.append("Estas afirmam empresas reais; é aqui que a revisão importa.")
    out.append("")
    for e in reais:
        out.append(_real_block(e))

    out.append(f"## B. Fixtures sintéticas (andaime de medição, NÃO empresas reais) — {len(synth)}")
    out.append("")
    out.append(
        "Ancoradas na rubrica AIMI (`docs/ARQUITETURA.md §3.6`) para dar *span* à métrica (cobrir todas as regiões × "
        "classes). Não há empresa real por trás — revise se a prioridade bate com a região/AIMI."
    )
    out.append("")
    out.append("| id | região | classe | AIMI (P1/P2/P3/P4) | techs (prioridade) |")
    out.append("|---|---|---|---|---|")
    for e in synth:
        a = e.aimi
        out.append(
            f"| `{e.id}` | {e.region.value} | {e.classificacao.value} | "
            f"{a.data_moat}/{a.workflow_depth}/{a.technical_optimization}/{a.distribution_moat} | "
            f"{_techs(e)} |"
        )
    out.append("")

    _OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"[review] {_OUT.relative_to(Path.cwd())} — {len(reais)} reais + {len(synth)} sintéticas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
