"""Suite de validação integrada da Fase 2 — NVIDIA Startup AI Radar.

Seção 1: Fallback Tavily → SerpAPI (Tavily mockado para falhar com 429).
Seção 2: Distribuição de níveis de extração (re-extração sobre amostra, sem DB write).
Seção 3: URL Discovery para startups deep_scan_failed (sem atualizar status no banco).

Uso:
    python tests/validate_phase2.py            # todas as seções
    python tests/validate_phase2.py --section 1
    python tests/validate_phase2.py --section 2
    python tests/validate_phase2.py --section 3
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.logging_conf import setup_logging
from src.phase2.tools.extractor import _extract_impl
from src.phase2.tools.url_discovery import _discover_startup_url_impl


# =============================================================================
# Utilitários compartilhados
# =============================================================================

class _LogCapture(logging.Handler):
    """Captura records de loggers específicos via handler injetado."""

    def __init__(self, *logger_names: str) -> None:
        super().__init__(level=logging.DEBUG)
        self._names = logger_names
        self.records: list[logging.LogRecord] = []
        for name in logger_names:
            log = logging.getLogger(name)
            log.addHandler(self)
            log.setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def messages(self, level: int | None = None) -> list[str]:
        return [
            r.getMessage() for r in self.records
            if level is None or r.levelno >= level
        ]

    def warnings(self) -> list[str]:
        return self.messages(logging.WARNING)

    def infos(self) -> list[str]:
        return self.messages(logging.INFO)

    def __enter__(self) -> "_LogCapture":
        return self

    def __exit__(self, *_: Any) -> None:
        for name in self._names:
            logging.getLogger(name).removeHandler(self)


async def _db_fetch(sql: str, *args: Any) -> list[dict]:
    """Query read-only: abre conexão, executa, fecha."""
    import asyncpg
    conn = await asyncpg.connect(dsn=get_settings().database_url)
    try:
        rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


def _is_valid_url(url: str | None) -> bool:
    return bool(url and re.match(r"https?://[^\s/$.?#].[^\s]*", url))


def _trunc(s: str | None, n: int = 80) -> str:
    if not s:
        return ""
    return (s[:n] + "…") if len(s) > n else s


# =============================================================================
# Seção 1 — Fallback Tavily → SerpAPI
# =============================================================================

_S1_STARTUPS = [
    ("Nubank", "Financeiro"),
    ("iFood", "Foodtech"),
    ("Stone", "Financeiro"),
    ("QuintoAndar", "PropTech"),
    ("C6 Bank", "Financeiro"),
]


def _tavily_fail(api_key: str, startup_name: str, sector: str) -> str | None:
    raise Exception("Simulated 429 Too Many Requests")


async def run_section1() -> dict:
    print("\n=== Seção 1: Fallback Tavily → SerpAPI ===")
    rows: list[dict] = []

    with patch("src.phase2.tools.url_discovery._tavily_search", side_effect=_tavily_fail):
        for name, sector in _S1_STARTUPS:
            # Log capture por startup para isolar as mensagens
            with _LogCapture("phase2.url_discovery") as cap:
                print(f"  {name}...", end=" ", flush=True)
                t0 = perf_counter()
                url = await _discover_startup_url_impl(name, sector)
                elapsed = perf_counter() - t0

            provider = "Nenhum"
            for msg in cap.infos():
                m = re.search(r"URL encontrada via (.+?) para", msg)
                if m:
                    provider = m.group(1).strip()
                    break

            rotations = sum(1 for m in cap.warnings() if "Rotacao de chave" in m)
            tavily_fails = sum(1 for m in cap.warnings() if "Falha em Tavily" in m)
            valid = _is_valid_url(url)

            print(f"{'✅' if valid else '❌'} {provider} | {elapsed:.2f}s")
            rows.append({
                "startup": name,
                "provider": provider,
                "elapsed": elapsed,
                "url": url or "",
                "valid_url": valid,
                "rotations": rotations,
                "tavily_fails": tavily_fails,
            })

    success = sum(1 for r in rows if r["valid_url"])
    total = len(rows)
    avg_time = sum(r["elapsed"] for r in rows) / total if total else 0
    total_rotations = sum(r["rotations"] for r in rows)

    print(f"\n  Resultado: {success}/{total} URLs válidas | {total_rotations} rotações | {avg_time:.2f}s médio")
    return {"rows": rows, "success": success, "total": total, "avg_time": avg_time, "rotations": total_rotations}


# =============================================================================
# Seção 2 — Self-healing: níveis de extração
# =============================================================================

_S2_QUERY = """
    SELECT id, name, official_website FROM startups_discovered
    WHERE status = 'deep_scan_completed'
      AND official_website IS NOT NULL
      AND official_website NOT LIKE '%.pdf'
      AND official_website NOT LIKE '%x.com%'
      AND official_website NOT LIKE '%tracxn.com%'
      AND official_website NOT LIKE '%jusbrasil%'
      AND official_website NOT LIKE '%captable%'
      AND official_website NOT LIKE '%linkedin%'
      AND official_website NOT LIKE '%pinterest%'
      AND official_website NOT LIKE '%reuters%'
      AND official_website NOT LIKE '%healthcaretechoutlook%'
    ORDER BY RANDOM()
    LIMIT 20
"""

_SPA_SITES = [
    ("Nubank",       "https://nubank.com.br"),
    ("iFood",        "https://www.ifood.com.br"),
    ("Stone",        "https://www.stone.com.br"),
    ("Pagar.me",     "https://pagar.me"),
    ("Contabilizei", "https://www.contabilizei.com.br"),
]


async def _extract_one(name: str, url: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        t0 = perf_counter()
        try:
            data = await asyncio.wait_for(_extract_impl(url), timeout=30)
            elapsed = perf_counter() - t0
            content = data.raw_text or data.core_business or ""
            return {
                "name": name, "url": url,
                "level": data.extraction_level,
                "has_content": bool(content),
                "content_len": len(content),
                "elapsed": elapsed,
                "preview": _trunc(content, 120),
            }
        except asyncio.TimeoutError:
            return {"name": name, "url": url, "level": "timeout", "has_content": False,
                    "content_len": 0, "elapsed": perf_counter() - t0, "preview": "TIMEOUT"}
        except Exception as exc:
            return {"name": name, "url": url, "level": "error", "has_content": False,
                    "content_len": 0, "elapsed": perf_counter() - t0, "preview": f"ERRO: {exc}"}


async def run_section2() -> dict:
    print("\n=== Seção 2: Self-healing (níveis de extração) ===")

    sample = await _db_fetch(_S2_QUERY)
    print(f"  Amostra: {len(sample)} startups | semáforo=3")

    sem = asyncio.Semaphore(3)
    results = await asyncio.gather(*[_extract_one(r["name"], r["official_website"], sem) for r in sample])

    by_level: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_level[r["level"]].append(r)

    total = len(results)
    level_stats = []
    for level in ("json_ld", "main_text", "spa", "none", "timeout", "error"):
        items = by_level.get(level, [])
        if not items:
            continue
        count = len(items)
        avg = sum(i["elapsed"] for i in items) / count
        with_content = sum(1 for i in items if i["has_content"])
        level_stats.append({
            "level": level, "count": count,
            "pct": count / total * 100,
            "avg_time": avg,
            "with_content": with_content,
        })
        print(f"  {level:10s} {count:3d} ({count/total*100:5.1f}%) | {avg:.2f}s | conteúdo: {with_content}/{count}")

    near_failures = [r for r in results if r["level"] not in ("json_ld",)]

    # SPA stress test — força Nível 3 zerando _fetch_html
    print(f"\n  Teste de estresse Crawl4AI (Nível 3 forçado):")

    async def _null_fetch(url: str) -> str | None:
        return None

    spa_results = []
    for spa_name, spa_url in _SPA_SITES:
        print(f"    {spa_name}...", end=" ", flush=True)
        with patch("src.phase2.tools.extractor._fetch_html", new=_null_fetch):
            t0 = perf_counter()
            try:
                data = await asyncio.wait_for(_extract_impl(spa_url), timeout=45)
                elapsed = perf_counter() - t0
                content = data.raw_text or data.core_business or ""
                result = {
                    "name": spa_name, "url": spa_url,
                    "level": data.extraction_level,
                    "has_content": bool(content),
                    "content_len": len(content),
                    "elapsed": elapsed,
                }
                icon = "✅" if result["has_content"] else "⚠️ sem conteúdo"
                print(f"{icon} | {data.extraction_level} | {elapsed:.1f}s | {result['content_len']} chars")
            except asyncio.TimeoutError:
                elapsed = perf_counter() - t0
                result = {"name": spa_name, "url": spa_url, "level": "timeout",
                          "has_content": False, "content_len": 0, "elapsed": elapsed}
                print(f"⏱️ timeout ({elapsed:.1f}s)")
            except Exception as exc:
                elapsed = perf_counter() - t0
                result = {"name": spa_name, "url": spa_url, "level": "error",
                          "has_content": False, "content_len": 0, "elapsed": elapsed}
                print(f"❌ {exc}")
        spa_results.append(result)

    return {
        "level_stats": level_stats,
        "near_failures": near_failures,
        "spa_results": spa_results,
        "total": total,
    }


# =============================================================================
# Seção 3 — URL Discovery para deep_scan_failed
# =============================================================================

_S3_QUERY = """
    SELECT id, name, sector, official_website FROM startups_discovered
    WHERE status = 'deep_scan_failed'
      AND name NOT LIKE 'Loading%'
      AND name NOT LIKE 'Registre%'
      AND name NOT LIKE '¿%'
    LIMIT 15
"""


async def run_section3() -> dict:
    print("\n=== Seção 3: URL Discovery para deep_scan_failed ===")

    candidates = await _db_fetch(_S3_QUERY)
    print(f"  {len(candidates)} startups com URLs inválidas")

    rows: list[dict] = []
    for r in candidates:
        name = r["name"]
        sector = r.get("sector") or ""
        original = r.get("official_website") or ""

        print(f"  {_trunc(name, 32)}...", end=" ", flush=True)

        with _LogCapture("phase2.url_discovery") as cap:
            t0 = perf_counter()
            try:
                url = await _discover_startup_url_impl(name, sector)
            except Exception as exc:
                url = None
                print(f"EXCEÇÃO: {exc}", end=" ")
            elapsed = perf_counter() - t0

        provider = "Nenhum"
        for msg in cap.infos():
            m = re.search(r"URL encontrada via (.+?) para", msg)
            if m:
                provider = m.group(1).strip()
                break

        valid = _is_valid_url(url)
        print(f"{'✅' if valid else '❌'} {provider} | {elapsed:.2f}s | {_trunc(url, 45)}")

        rows.append({
            "name": name,
            "sector": sector,
            "original_url": original,
            "found_url": url or "",
            "provider": provider,
            "elapsed": elapsed,
            "valid": valid,
        })

    success = sum(1 for r in rows if r["valid"])
    total = len(rows)
    avg_time = sum(r["elapsed"] for r in rows) / total if total else 0
    provider_counts = dict(Counter(r["provider"] for r in rows if r["valid"]))

    print(f"\n  Resultado: {success}/{total} encontradas ({success/total*100:.0f}%) | {avg_time:.2f}s médio")

    return {
        "rows": rows,
        "success": success,
        "total": total,
        "avg_time": avg_time,
        "provider_counts": provider_counts,
        "manual_validation": [r for r in rows if r["valid"]][:5],
    }


# =============================================================================
# Geração do relatório Markdown
# =============================================================================

def _write_report(s1: dict | None, s2: dict | None, s3: dict | None) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [
        "# Relatório de Validação — Fase 2 NVIDIA Startup AI Radar",
        "",
        f"**Gerado em:** {now}  ",
        "**Banco:** `nvidia_radar` (somente leitura — banco de produção não modificado)",
        "",
        "---",
        "",
        "## Resumo Executivo",
        "",
    ]

    bullets: list[str] = []
    if s1:
        rate = s1["success"] / s1["total"] * 100 if s1["total"] else 0
        bullets.append(
            f"**Fallback Tavily → SerpAPI**: {s1['success']}/{s1['total']} URLs "
            f"encontradas via SerpAPI ({rate:.0f}% de sucesso). "
            f"{s1['rotations']} rotações detectadas nos logs. "
            f"Tempo médio {s1['avg_time']:.2f}s/startup."
        )
    if s2:
        dominant = max(s2["level_stats"], key=lambda x: x["count"]) if s2["level_stats"] else None
        spa_ok = sum(1 for r in s2["spa_results"] if r["has_content"])
        none_count = next((x["count"] for x in s2["level_stats"] if x["level"] == "none"), 0)
        bullets.append(
            f"**Self-healing (extração)**: {s2['total']} startups re-testadas; "
            f"nível dominante `{dominant['level'] if dominant else 'N/A'}` "
            f"({dominant['count'] if dominant else 0} startups, {dominant['pct']:.0f}%). "
            f"Crawl4AI (Nível 3): {spa_ok}/{len(s2['spa_results'])} SPAs com conteúdo. "
            f"Falhas totais (`none`): {none_count}."
        )
    if s3:
        rate3 = s3["success"] / s3["total"] * 100 if s3["total"] else 0
        providers_str = ", ".join(f"{k} ×{v}" for k, v in s3["provider_counts"].items()) or "nenhum"
        bullets.append(
            f"**URL Discovery (falhos)**: {s3['success']}/{s3['total']} URLs novas "
            f"encontradas ({rate3:.0f}%). Providers: {providers_str}. "
            f"Tempo médio {s3['avg_time']:.2f}s."
        )

    for b in bullets:
        lines.append(f"- {b}")
    lines += ["", "---", ""]

    # ── Seção 1 ──────────────────────────────────────────────────────────────
    if s1:
        lines += [
            "## 1. Fallback Tavily → SerpAPI",
            "",
            "> **Cenário**: ambas as chaves Tavily foram mockadas para lançar "
            "`Exception(\"429\")`. O pipeline deve rotacionar automaticamente para SerpAPI KEY_1.",
            "",
            "| Startup | Provider usado | Tempo (s) | URL encontrada | Válida? |",
            "|---------|---------------|-----------|----------------|---------|",
        ]
        for r in s1["rows"]:
            url_d = _trunc(r["url"], 50) or "—"
            icon = "✅" if r["valid_url"] else "❌"
            lines.append(
                f"| {r['startup']} | {r['provider']} | {r['elapsed']:.2f} | `{url_d}` | {icon} |"
            )
        lines += [
            "",
            f"- **Taxa de sucesso**: {s1['success']}/{s1['total']} ({s1['success']/s1['total']*100:.0f}%)",
            f"- **Rotações de chave nos logs**: {s1['rotations']}",
            f"- **Tempo médio por startup**: {s1['avg_time']:.2f}s",
            "",
            "---",
            "",
        ]

    # ── Seção 2 ──────────────────────────────────────────────────────────────
    if s2:
        lines += [
            "## 2. Self-healing — Níveis de Extração",
            "",
            "### 2.1 Distribuição (amostra de 20 startups `deep_scan_completed`)",
            "",
            "| Nível | Qtd | % | Tempo Médio (s) | Com Conteúdo |",
            "|-------|-----|---|-----------------|--------------|",
        ]
        for stat in s2["level_stats"]:
            lines.append(
                f"| `{stat['level']}` | {stat['count']} | {stat['pct']:.1f}% "
                f"| {stat['avg_time']:.2f} | {stat['with_content']}/{stat['count']} |"
            )

        if s2["near_failures"]:
            lines += [
                "",
                "### 2.2 Quase-falhas — Nível 2+ acionado",
                "",
                "| Startup | Nível | Tempo (s) | Preview do conteúdo extraído |",
                "|---------|-------|-----------|------------------------------|",
            ]
            for r in s2["near_failures"][:10]:
                preview = _trunc(r.get("preview", ""), 70).replace("|", "│")
                lines.append(
                    f"| {_trunc(r['name'], 30)} | `{r['level']}` "
                    f"| {r['elapsed']:.2f} | {preview} |"
                )

        lines += [
            "",
            "### 2.3 Teste de Estresse — Crawl4AI forçado (Nível 3)",
            "",
            "> `_fetch_html` patchado para retornar `None` → Níveis 1 e 2 sempre falham "
            "→ Crawl4AI obrigatoriamente ativado.",
            "",
            "| Site | Nível alcançado | Tempo (s) | Chars extraídos | OK? |",
            "|------|----------------|-----------|-----------------|-----|",
        ]
        for r in s2["spa_results"]:
            icon = "✅" if r["has_content"] else ("⏱️ timeout" if r["level"] == "timeout" else "❌")
            lines.append(
                f"| {r['name']} | `{r['level']}` | {r['elapsed']:.1f} | {r['content_len']} | {icon} |"
            )
        lines += ["", "---", ""]

    # ── Seção 3 ──────────────────────────────────────────────────────────────
    if s3:
        lines += [
            "## 3. URL Discovery para deep_scan_failed",
            "",
            "| Startup | URL original (inválida) | URL encontrada | Provider | Tempo (s) | OK? |",
            "|---------|------------------------|----------------|----------|-----------|-----|",
        ]
        for r in s3["rows"]:
            orig = _trunc(r["original_url"], 30) or "—"
            found = _trunc(r["found_url"], 45) or "—"
            icon = "✅" if r["valid"] else "❌"
            lines.append(
                f"| {_trunc(r['name'], 28)} | `{orig}` | `{found}` "
                f"| {r['provider']} | {r['elapsed']:.2f} | {icon} |"
            )
        lines += [
            "",
            f"- **Taxa de sucesso**: {s3['success']}/{s3['total']} ({s3['success']/s3['total']*100:.0f}%)",
            f"- **Tempo médio**: {s3['avg_time']:.2f}s",
            "",
            "### URLs para validação manual no browser",
            "",
        ]
        for i, r in enumerate(s3["manual_validation"], 1):
            lines.append(f"{i}. **{r['name']}** → <{r['found_url']}>")

        if s3["total"] > 0 and s3["success"] / s3["total"] < 0.70:
            lines += [
                "",
                "> ⚠️ **Taxa abaixo de 70%** — ver Recomendações.",
            ]
        lines += ["", "---", ""]

    # ── Recomendações ────────────────────────────────────────────────────────
    lines += ["## Recomendações Práticas", ""]
    recs: list[str] = []

    if s1 and s1["avg_time"] > 3.0:
        recs.append(
            f"**Timeout URL Discovery** (média {s1['avg_time']:.1f}s): "
            "considerar `REQUEST_TIMEOUT=10` no `.env` para limitar chamadas lentas ao SerpAPI."
        )
    if s1 and s1["success"] < s1["total"]:
        recs.append(
            "**Falhas no SerpAPI**: verificar saldo da conta em `serpapi.com`. "
            "Adicionar `site:` operator na query como último recurso: "
            "`f\"{name} site:crunchbase.com OR site:linkedin.com/company\"`."
        )
    if s2:
        none_count = next((x["count"] for x in s2["level_stats"] if x["level"] == "none"), 0)
        if none_count > 2:
            recs.append(
                f"**{none_count} startups sem conteúdo** (`none`): "
                "verificar se são SPAs não identificados. Aumentar `DEEP_SCAN_CONCURRENCY` e "
                "reduzir `CHUNK_SIZE` para capturar fragmentos menores."
            )
        spa_fails = sum(1 for r in s2["spa_results"] if not r["has_content"])
        if spa_fails:
            recs.append(
                f"**{spa_fails} SPAs sem conteúdo no Nível 3**: "
                "`_CRAWL4AI_TIMEOUT = 30s` (em `spa_fallback.py`) pode ser insuficiente. "
                "Aumentar para 60s para sites com JS pesado."
            )
    if s3:
        if s3["total"] > 0 and s3["success"] / s3["total"] < 0.70:
            recs.append(
                f"**URL Discovery com taxa baixa** ({s3['success']/s3['total']*100:.0f}%): "
                "enriquecer a query com setor: "
                "`f\"{name} {sector} startup Brasil site oficial\"`. "
                "Se ainda falhar, adicionar Nível 5 via LinkedIn: "
                "`site:linkedin.com/company/{slug}`."
            )

    if not recs:
        recs.append(
            "Sistema operando dentro dos parâmetros esperados. "
            "Nenhum ajuste crítico identificado com base nos resultados observados."
        )

    for rec in recs:
        lines.append(f"- {rec}")
    lines.append("")

    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

async def main() -> None:
    parser = argparse.ArgumentParser(description="Validação integrada da Fase 2")
    parser.add_argument(
        "--section", type=int, choices=[1, 2, 3],
        help="Executar apenas uma seção (1, 2 ou 3). Sem flag executa todas.",
    )
    args = parser.parse_args()

    # Suprime logs do pipeline no stdout; _LogCapture captura o que precisa por dentro
    setup_logging("ERROR")

    run_all = args.section is None
    s1 = s2 = s3 = None

    if run_all or args.section == 1:
        s1 = await run_section1()
    if run_all or args.section == 2:
        s2 = await run_section2()
    if run_all or args.section == 3:
        s3 = await run_section3()

    report = _write_report(s1, s2, s3)

    report_path = Path(__file__).parent.parent / "reports" / "phase2_validation_report.md"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(f"\n✅ Relatório salvo em: {report_path}")
    print("\n" + "=" * 60)
    # Mostra o resumo executivo no terminal
    in_summary = False
    for line in report.split("\n"):
        if line.startswith("## Resumo"):
            in_summary = True
        elif line.startswith("---") and in_summary:
            break
        if in_summary:
            print(line)


if __name__ == "__main__":
    asyncio.run(main())
