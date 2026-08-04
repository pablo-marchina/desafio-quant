from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import httpx

from scraper.api.services.job_manager import ProgressCallback

DEFAULT_REPORT_OPENROUTER_MODEL = "~google/gemini-flash-latest"
DEFAULT_REPORT_OPENROUTER_FALLBACK_MODELS = (
    "google/gemini-2.5-flash",
    "google/gemini-2.5-flash-lite",
)


class ActionReportService:
    def __init__(self, startup_service: Any | None = None) -> None:
        self.startup_service = startup_service
        self.base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.model = os.getenv(
            "REPORT_OPENROUTER_MODEL",
            DEFAULT_REPORT_OPENROUTER_MODEL,
        )
        self.fallback_models = _csv_env(
            "REPORT_OPENROUTER_FALLBACK_MODELS",
            DEFAULT_REPORT_OPENROUTER_FALLBACK_MODELS,
        )
        self.timeout = float(os.getenv("OPENROUTER_TIMEOUT", "45"))

    def generate(
        self,
        startup: dict[str, Any],
        progress: ProgressCallback,
        *,
        objective: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")

        company_name = str(startup.get("company_name") or "").strip()
        if not company_name:
            raise ValueError("Startup has no company_name")
        recommendation = startup.get("nvidia_recommendation") or {}
        if not isinstance(recommendation, dict):
            recommendation = {}
        if not recommendation:
            raise ValueError(
                "Startup has no NVIDIA recommendation. Generate it before the report."
            )

        competitive = startup.get("competitive_analysis") or {}
        if not isinstance(competitive, dict):
            competitive = {}
        benchmark = _benchmark_from_competitive(competitive)

        progress(10)
        payload = self._build_payload(
            startup=startup,
            recommendation=recommendation,
            competitive=competitive,
            objective=objective,
            report_context=context or {},
            benchmark=benchmark,
        )
        progress(25)
        try:
            content = self._call_openrouter(payload, api_key)
            progress(80)
            parsed = self._parse_report(content)
        except Exception as error:
            if not _is_openrouter_rate_limit(error):
                raise
            progress(80)
            parsed = _fallback_report(
                startup=startup,
                recommendation=recommendation,
                benchmark=benchmark,
                report_context=context or {},
                model=self.model,
                reason="OpenRouter retornou 429 Too Many Requests.",
            )
        parsed["benchmark_competitivo"] = _merge_benchmark(
            parsed.get("benchmark_competitivo"), benchmark
        )
        report = {
            "startup_id": str(startup.get("candidate_id") or startup.get("id") or ""),
            "company_name": company_name,
            "model": str(payload.get("model") or self.model),
            "generated_at": datetime.now(UTC).isoformat(),
            "context": context or {},
            **parsed,
        }
        if self.startup_service is not None:
            self.startup_service.update_startup(
                str(startup.get("id") or startup.get("candidate_id")),
                {"action_report": report},
            )
        progress(95)
        return report

    def _build_payload(
        self,
        *,
        startup: dict[str, Any],
        recommendation: dict[str, Any],
        competitive: dict[str, Any],
        objective: str | None,
        report_context: dict[str, Any],
        benchmark: dict[str, Any],
    ) -> dict[str, Any]:
        context = {
            "startup": {
                "id": startup.get("id"),
                "candidate_id": startup.get("candidate_id"),
                "company_name": startup.get("company_name"),
                "cnpj": startup.get("cnpj"),
                "website": startup.get("validated_url") or startup.get("website"),
                "description": startup.get("company_description")
                or startup.get("description"),
                "ai_dependency_level": startup.get("ai_dependency_level"),
                "ai_technology_focus": startup.get("ai_technology_focus"),
                "target_market": startup.get("target_market"),
                "tech_stack": startup.get("tech_stack"),
                "technology_intelligence": startup.get("technology_intelligence"),
            },
            "nvidia_recommendation": recommendation,
            "competitive_analysis": competitive,
            "benchmark_competitivo": benchmark,
            "contexto_negociado_fase_1": report_context,
            "objective": " ".join((objective or "").split()),
            "coletado_em": datetime.now(UTC).date().isoformat(),
        }
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Voce e um analista senior de parcerias/M&A para o time NVIDIA. "
                        "Seja direto, executivo e factual. Nunca invente dados. "
                        "Nao repita dados cadastrais completos: use apenas nome, CNPJ "
                        "e descricao curta para identificacao. Responda somente JSON valido."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Gere o relatorio final em markdown no campo markdown_report, "
                        "seguindo exatamente esta estrutura: "
                        "### {nome_empresa} — CNPJ {cnpj}; descricao em 1-2 linhas; "
                        "### Aderência ao Perfil Buscado; "
                        "### Score AI-Native: {score}/100; "
                        "### Fit com {produto_alvo definido no contexto}; "
                        "### Benchmark Competitivo; "
                        "### Riscos e Gaps; "
                        "### Próxima Ação Sugerida; "
                        "### Dificuldade de Implementação; "
                        "### Confiabilidade da Análise. "
                        "Use o contexto negociado na guia para avaliar aderencia. "
                        "Use benchmark_competitivo para concorrentes; se estiver vazio, "
                        "declare sem concorrentes diretos identificados publicamente. "
                        "Na secao Confiabilidade da Análise use: Dados cadastrais: "
                        "Alta (fonte: Receita Federal via cnpj.biz); Fit NVIDIA: "
                        "Alta|Média|Baixa; Benchmark competitivo: Alta|Média|Baixa "
                        "com fonte das buscas; Coletado em: coletado_em. "
                        "Nao cite razao social, endereco, socios ou CNAE completo. "
                        "Tambem retorne: executive_summary string; next_actions array; "
                        "nvidia_focus array; bigtech_implications array; risks array; "
                        "open_questions array; score_ai_native number; "
                        "benchmark_competitivo objeto; confiabilidade objeto. "
                        f"Dados: {json.dumps(context, ensure_ascii=False, default=str)}"
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 1800,
        }

    def _call_openrouter(self, payload: dict[str, Any], api_key: str) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        referer = os.getenv("OPENROUTER_HTTP_REFERER")
        title = os.getenv("OPENROUTER_X_TITLE")
        if referer:
            headers["HTTP-Referer"] = referer
        if title:
            headers["X-Title"] = title
        response = None
        models = list(dict.fromkeys([str(payload.get("model") or self.model), *self.fallback_models]))
        for index, model in enumerate(models):
            payload["model"] = model
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            if getattr(response, "status_code", None) == 404 and index < len(models) - 1:
                continue
            response.raise_for_status()
            break
        if response is None:
            raise RuntimeError("OpenRouter request was not executed")
        data = response.json()
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices:
            raise RuntimeError("OpenRouter returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("OpenRouter returned empty content")
        return content.strip()

    @staticmethod
    def _parse_report(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "executive_summary": cleaned[:1000],
                "next_actions": [],
                "nvidia_focus": [],
                "bigtech_implications": [],
                "risks": [],
                "open_questions": [],
                "markdown_report": cleaned,
                "benchmark_competitivo": {
                    "concorrentes": [],
                    "posicionamento": "sem concorrentes diretos identificados publicamente",
                },
                "raw_report": content,
                "structured_output": {},
            }
        if not isinstance(parsed, dict):
            parsed = {"executive_summary": str(parsed)}
        return {
            "executive_summary": str(parsed.get("executive_summary") or ""),
            "next_actions": _list_of_dicts(parsed.get("next_actions")),
            "nvidia_focus": _list_of_strings(parsed.get("nvidia_focus")),
            "bigtech_implications": _list_of_strings(
                parsed.get("bigtech_implications")
            ),
            "risks": _list_of_strings(parsed.get("risks")),
            "open_questions": _list_of_strings(parsed.get("open_questions")),
            "markdown_report": str(
                parsed.get("markdown_report")
                or parsed.get("report_markdown")
                or parsed.get("raw_report")
                or ""
            ),
            "score_ai_native": _int_or_none(parsed.get("score_ai_native")),
            "benchmark_competitivo": _dict_or_default(
                parsed.get("benchmark_competitivo"),
                {
                    "concorrentes": [],
                    "posicionamento": "sem concorrentes diretos identificados publicamente",
                },
            ),
            "confiabilidade": _dict_or_default(parsed.get("confiabilidade"), {}),
            "structured_output": parsed,
        }


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item not in (None, "")]


def _csv_env(name: str, default: tuple[str, ...]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return list(default)
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or list(default)


def _list_of_dicts(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            items.append(
                {
                    str(key): str(value)
                    for key, value in item.items()
                    if value not in (None, "")
                }
            )
        elif item not in (None, ""):
            items.append({"action": str(item)})
    return items


def _dict_or_default(value: Any, default: dict[str, Any]) -> dict[str, Any]:
    return value if isinstance(value, dict) else default


def _is_openrouter_rate_limit(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code == 429
    message = str(error).casefold()
    return (
        "429" in message
        and (
            "too many requests" in message
            or "openrouter" in message
            or "chat/completions" in message
        )
    )


def _merge_benchmark(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    current = value if isinstance(value, dict) else {}
    competitors = current.get("concorrentes")
    if not isinstance(competitors, list) or not competitors:
        current["concorrentes"] = fallback.get("concorrentes", [])
    if not current.get("posicionamento"):
        current["posicionamento"] = fallback.get(
            "posicionamento",
            "sem concorrentes diretos identificados publicamente",
        )
    return current


def _int_or_none(value: Any) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return max(0, min(100, number))


def _fallback_report(
    *,
    startup: dict[str, Any],
    recommendation: dict[str, Any],
    benchmark: dict[str, Any],
    report_context: dict[str, Any],
    model: str,
    reason: str,
) -> dict[str, Any]:
    company = str(startup.get("company_name") or "Startup não informada")
    cnpj = str(startup.get("cnpj") or "não informado")
    description = _short_text(
        startup.get("company_description") or startup.get("description") or "Descrição não informada.",
        260,
    )
    profile = report_context.get("perfil_ideal") if isinstance(report_context, dict) else {}
    if not isinstance(profile, dict):
        profile = {}
    gaps = recommendation.get("gaps") if isinstance(recommendation.get("gaps"), list) else []
    recommendations = (
        recommendation.get("recommendations")
        if isinstance(recommendation.get("recommendations"), list)
        else []
    )
    recommended_product = ""
    if recommendations and isinstance(recommendations[0], dict):
        recommended_product = str(recommendations[0].get("produto") or "")
    product = str(report_context.get("produto_alvo") or recommended_product or "recomende você mesmo")
    competitors = benchmark.get("concorrentes") if isinstance(benchmark.get("concorrentes"), list) else []
    competitor_lines = (
        "\n".join(
            f"- {item.get('nome', 'Concorrente não informado')}: usa NVIDIA = "
            f"{item.get('usa_nvidia', 'desconhecido')} (fonte: {item.get('fonte', 'sem fonte')})"
            for item in competitors
            if isinstance(item, dict)
        )
        or "- sem concorrentes diretos identificados publicamente"
    )
    risk_lines = (
        "\n".join(
            f"- {str(item.get('gap') or item)[:180]}"
            for item in gaps[:4]
        )
        if gaps
        else "- Dados insuficientes para listar gaps específicos além da limitação de cota do provedor LLM."
    )
    score = _fallback_score(startup, recommendations)
    collected_at = datetime.now(UTC).date().isoformat()
    markdown = f"""### {company} — CNPJ {cnpj}
{description}

### Aderência ao Perfil Buscado
Atende parcialmente. Perfil buscado: setor {profile.get('setor') or 'não definido'}, estágio {profile.get('estagio') or 'não definido'}, porte {profile.get('porte') or 'não definido'}, urgência {profile.get('urgencia') or 'não definida'}. A aderência não pôde ser validada por LLM devido a limite de requisições.

### Score AI-Native: {score}/100
Score determinístico baseado em classificação de IA, stack tecnológica e existência de recomendações NVIDIA salvas.

### Fit com {product}
Há fit potencial quando as recomendações NVIDIA salvas apontam produto/gap compatível. Nível de confiança: Baixo - relatório gerado sem chamada LLM por limitação temporária do OpenRouter.

### Benchmark Competitivo
{competitor_lines}
Posicionamento: {benchmark.get('posicionamento') or 'sem concorrentes diretos identificados publicamente'}.

### Riscos e Gaps
{risk_lines}

### Próxima Ação Sugerida
[Aguardar mais dados] Limite de requisições no provedor LLM impediu a análise completa; revisar quando a cota normalizar.

### Dificuldade de Implementação
Nível: Médio - depende de validação técnica do fit e confirmação de recursos da startup.

### Confiabilidade da Análise
- Dados cadastrais: Alta (fonte: Receita Federal via cnpj.biz)
- Fit NVIDIA: Baixa
- Benchmark competitivo: Baixa (fonte das buscas salvas na guia VS Big Techs/Supabase)
- Coletado em: {collected_at}
"""
    return {
        "executive_summary": (
            f"Relatório fallback gerado porque {reason} A análise usa somente dados salvos."
        ),
        "next_actions": [
            {
                "action": "Aguardar mais dados",
                "rationale": "Cota do provedor LLM excedida; relatório completo deve ser reprocessado depois.",
                "priority": "Média",
            }
        ],
        "nvidia_focus": [product],
        "bigtech_implications": [str(benchmark.get("posicionamento") or "")],
        "risks": [str(item.get("gap") or item) for item in gaps[:4]]
        or ["Limite do provedor LLM reduziu a profundidade da análise."],
        "open_questions": ["Reprocessar o relatório quando o limite do OpenRouter normalizar."],
        "markdown_report": markdown,
        "score_ai_native": score,
        "benchmark_competitivo": benchmark,
        "confiabilidade": {
            "dados_cadastrais": "Alta",
            "fit_nvidia": "Baixa",
            "benchmark_competitivo": "Baixa",
            "coletado_em": collected_at,
            "fallback_reason": reason,
        },
        "raw_report": markdown,
        "structured_output": {"fallback": True, "reason": reason, "model": model},
    }


def _short_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _fallback_score(startup: dict[str, Any], recommendations: list[Any]) -> int:
    score = 30
    if str(startup.get("ai_dependency_level") or "").upper() in {"AI_NATIVE", "AI_ENABLED"}:
        score += 30
    if startup.get("technology_intelligence") or startup.get("tech_stack"):
        score += 20
    if recommendations:
        score += 20
    return max(0, min(100, score))


def _benchmark_from_competitive(competitive: dict[str, Any]) -> dict[str, Any]:
    structured = competitive.get("structured_output")
    if not isinstance(structured, dict):
        structured = {}
    comparison = structured.get("comparacao_competitiva")
    if not isinstance(comparison, dict):
        comparison = {}
    summary = comparison.get("comparacao_bigtechs_resumida")
    if not isinstance(summary, dict):
        summary = {}
    validated = comparison.get("servico_bigtech_validado")
    if not isinstance(validated, dict):
        validated = {}

    competitors: list[dict[str, Any]] = []
    for item in summary.get("equivalentes_big_tech") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("empresa") or "").strip()
        if not name:
            continue
        source = str(validated.get("candidato_url") or "").strip()
        uses_nvidia: bool | str = True if name.casefold() == "nvidia" else "desconhecido"
        competitors.append(
            {
                "nome": name,
                "usa_nvidia": uses_nvidia,
                "fonte": source or "sem fonte oficial salva",
            }
        )
    if not competitors and validated.get("candidato_empresa"):
        competitors.append(
            {
                "nome": str(validated.get("candidato_empresa")),
                "usa_nvidia": (
                    True
                    if str(validated.get("candidato_empresa")).casefold() == "nvidia"
                    else "desconhecido"
                ),
                "fonte": str(validated.get("candidato_url") or "sem fonte oficial salva"),
            }
        )
    if not competitors:
        return {
            "concorrentes": [],
            "posicionamento": "sem concorrentes diretos identificados publicamente",
        }
    return {
        "concorrentes": competitors,
        "posicionamento": str(
            summary.get("risco_substituicao")
            or competitive.get("final_answer")
            or "Comparacao baseada na guia VS Big Techs salva no Supabase."
        ),
    }
