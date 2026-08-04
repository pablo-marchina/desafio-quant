from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests


AI_TERMS = (
    "inteligencia artificial",
    "machine learning",
    "deep learning",
    "redes neurais",
    "processamento de linguagem natural",
    "nlp",
    "visao computacional",
    "computer vision",
    "chatbot",
    "assistente virtual",
    "modelo preditivo",
    "algoritmo de recomendacao",
    "automacao inteligente",
    "llm",
    "gpt",
    "transformers",
    "pytorch",
    "tensorflow",
    "cuda",
    "gpu",
    "nvidia",
    "triton",
    "tensorrt",
    "rapids",
    "morpheus",
    "nemo",
    "data scientist",
    "ml engineer",
    "fine-tuning",
    "treinamento de modelo",
    "inferencia",
    "mlops",
)

PRESS_DOMAINS = {
    "braziljournal.com",
    "exame.com",
    "forbes.com.br",
    "neofeed.com.br",
    "pipelinevalor.globo.com",
    "revistapegn.globo.com",
    "startups.com.br",
    "valor.globo.com",
}

ECOSYSTEM_DOMAINS = {
    "cubo.itau",
    "distrito.me",
    "endeavor.org.br",
    "openstartups.net",
    "startse.com",
}

SOCIAL_DOMAINS = {
    "github.com",
    "linkedin.com",
    "medium.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
}

GENERIC_PAGE_MARKERS = (
    "page not found",
    "pagina nao encontrada",
    "erro 404",
    "404 not found",
    "access denied",
)

STRONG_CONTEXT_MARKERS = (
    "case",
    "entrevista",
    "produto",
    "plataforma",
    "tecnologia",
    "engenharia",
    "desenvolvemos",
    "utilizamos",
    "usa ",
    "startup",
)


class EvidenceValidatorAgent:
    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: int = 10,
        verificar_urls: bool = True,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.verificar_urls = verificar_urls

    def executar(
        self,
        startup: str,
        site_oficial: str | None,
        dados_brutos: dict[str, Any],
    ) -> dict[str, Any]:
        evidencias = _normalizar_evidencias(dados_brutos)
        oficial_domain = _domain(site_oficial)
        validadas: list[dict[str, Any]] = []
        medias: list[dict[str, Any]] = []
        descartadas: list[dict[str, Any]] = []
        erros: list[str] = []

        for evidencia in evidencias:
            resultado, motivo, erro = self._validar_evidencia(
                evidencia,
                startup=startup,
                official_domain=oficial_domain,
            )
            if erro:
                erros.append(erro)
            if resultado is None:
                descartadas.append({"url": evidencia["url"], "motivo": motivo})
                continue
            if resultado["classificacao"] == "alta":
                validadas.append(resultado)
            elif resultado["classificacao"] == "media":
                medias.append(resultado)
            else:
                descartadas.append({"url": resultado["url"], "motivo": motivo or "baixa confianca"})

        _marcar_corroboracao(validadas, medias)
        resumo = _construir_resumo(validadas, medias)

        return {
            "startup": startup,
            "evidencias_validadas": validadas,
            "evidencias_medias": medias,
            "evidencias_descartadas": descartadas,
            "resumo_consolidado": resumo,
            "erros_validacao": erros,
        }

    def _validar_evidencia(
        self,
        evidencia: dict[str, Any],
        startup: str,
        official_domain: str,
    ) -> tuple[dict[str, Any] | None, str | None, str | None]:
        url = evidencia["url"]
        source_domain = _domain(url)
        is_official = bool(official_domain and _same_organization_domain(source_domain, official_domain))
        content = _clean(
            evidencia.get("conteudo_textual")
            or evidencia.get("conteudo_markdown")
            or evidencia.get("snippet")
        )
        title = _clean(evidencia.get("titulo") or evidencia.get("titulo_pagina"))
        combined = f"{title} {content}".strip()
        normalized = _normalize(combined)

        if not url or not source_domain:
            return None, "url_invalida", None
        if any(marker in normalized for marker in GENERIC_PAGE_MARKERS):
            return None, "url_quebrada", None
        if not evidencia.get("pagina_coletada") and self.verificar_urls:
            accessible, error = self._url_acessivel(url)
            if not accessible:
                message = f"Falha ao acessar URL {url}: {error}" if error else None
                return None, "url_quebrada", message
        if not content:
            return None, "irrelevante: conteudo vazio", None

        mentions = _count_startup_mentions(combined, startup)
        if mentions == 0 and not is_official:
            return None, "homonimo_potencial: startup nao confirmada no conteudo", None

        technologies = _find_ai_terms(content)
        strong_mention = _is_strong_mention(content, mentions, is_official)
        has_ai_evidence = bool(technologies and (strong_mention or mentions > 0 or is_official))
        source_type, credibility = _classify_source(source_domain, is_official)
        relevance_score = 0.4 if strong_mention else 0.1
        confidence = round(relevance_score + (0.3 if has_ai_evidence else 0.0) + credibility * 0.3, 2)
        classification = "alta" if confidence >= 0.7 else "media" if confidence >= 0.4 else "baixa"

        result = {
            "url": url,
            "dominio": source_domain,
            "tipo_fonte": source_type,
            "credibilidade_fonte": credibility,
            "trecho_evidencia": _extract_evidence_excerpt(content, technologies),
            "score_confianca": confidence,
            "classificacao": classification,
            "mencao_forte": strong_mention,
            "contem_evidencia_ia": has_ai_evidence,
            "declaracao_propria": is_official,
            "tecnologias_detectadas": technologies,
            "corroborada": False,
        }
        reason = None
        if classification == "baixa":
            reason = "mencao superficial sem evidencia substantiva de IA"
        return result, reason, None

    def _url_acessivel(self, url: str) -> tuple[bool, str | None]:
        try:
            response = self.session.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 EvidenceValidator/1.0"},
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()
            return True, None
        except requests.RequestException as exc:
            return False, str(exc)


def validar_evidencias_scraper(
    dados_brutos: dict[str, Any],
    site_oficial: str | None = None,
    session: requests.Session | None = None,
    verificar_urls: bool = True,
) -> dict[str, Any]:
    startup = _clean(dados_brutos.get("startup"))
    return EvidenceValidatorAgent(
        session=session,
        verificar_urls=verificar_urls,
    ).executar(startup, site_oficial, dados_brutos)


def salvar_validacao_evidencias(
    resultado: dict[str, Any],
    output_dir: Path | None = None,
) -> Path:
    output_dir = output_dir or Path("data/processed/_evidencias")
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", _normalize(resultado.get("startup"))).strip("-") or "startup"
    path = output_dir / f"evidencias_validadas_{slug}.json"
    path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _normalizar_evidencias(dados: dict[str, Any]) -> list[dict[str, Any]]:
    raw_candidate = dados.get("dados_brutos")
    raw: dict[str, Any] = raw_candidate if isinstance(raw_candidate, dict) else dados
    by_url: dict[str, dict[str, Any]] = {}

    search_groups = raw.get("resultados_buscas") or raw.get("resultados_busca") or []
    for group in search_groups:
        items = group.get("resultados", []) if isinstance(group, dict) and "resultados" in group else [group]
        for item in items:
            _merge_evidence(by_url, item, pagina_coletada=False)

    pages = raw.get("paginas_completas") or raw.get("paginas_coletadas") or []
    for item in pages:
        _merge_evidence(by_url, item, pagina_coletada=True)

    for group in raw.get("varredura_complementar", []):
        for item in group.get("resultados", []):
            _merge_evidence(by_url, item, pagina_coletada=False)

    for task in raw.get("resultados", []):
        for item in task.get("itens_filtrados", []):
            normalized = {
                "url": item.get("link"),
                "titulo": item.get("titulo"),
                "snippet": item.get("descricao"),
            }
            _merge_evidence(by_url, normalized, pagina_coletada=False)

    return list(by_url.values())


def _merge_evidence(
    by_url: dict[str, dict[str, Any]],
    item: dict[str, Any],
    pagina_coletada: bool,
) -> None:
    url = _canonical_url(item.get("url") or item.get("link"))
    if not url:
        return
    existing = by_url.setdefault(url, {"url": url, "pagina_coletada": False})
    for key, value in item.items():
        if value not in (None, "", [], {}):
            existing[key] = value
    existing["url"] = url
    existing["pagina_coletada"] = existing["pagina_coletada"] or pagina_coletada


def _classify_source(domain: str, is_official: bool) -> tuple[str, float]:
    if is_official:
        return "oficial", 0.7
    if _matches_domain_set(domain, PRESS_DOMAINS):
        return "imprensa", 0.9
    if _matches_domain_set(domain, ECOSYSTEM_DOMAINS):
        return "ecossistema", 0.8
    if _matches_domain_set(domain, SOCIAL_DOMAINS):
        return "social", 0.6
    return "outro", 0.3


def _is_strong_mention(content: str, mentions: int, is_official: bool) -> bool:
    normalized = _normalize(content)
    has_context = any(marker in normalized for marker in STRONG_CONTEXT_MARKERS)
    return (mentions >= 2 and len(content) >= 180) or (mentions >= 1 and has_context) or (
        is_official and len(content) >= 120 and has_context
    )


def _count_startup_mentions(text: str, startup: str) -> int:
    normalized_text = _normalize(text)
    normalized_name = _normalize(startup)
    if not normalized_name:
        return 0
    exact = len(re.findall(rf"\b{re.escape(normalized_name)}\b", normalized_text))
    if exact:
        return exact
    legal_suffixes = {"ltda", "limitada", "inc", "sa"}
    significant_tokens = [
        token
        for token in normalized_name.split()
        if len(token) >= 3 and token not in legal_suffixes
    ]
    return 1 if significant_tokens and all(re.search(rf"\b{re.escape(token)}\b", normalized_text) for token in significant_tokens) else 0


def _find_ai_terms(text: str) -> list[str]:
    normalized = _normalize(text)
    found = []
    for term in AI_TERMS:
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized):
            found.append(term)
    return found


def _extract_evidence_excerpt(text: str, technologies: list[str]) -> str:
    clean = _clean(text)
    if not clean:
        return ""
    normalized = _normalize(clean)
    positions = [normalized.find(term) for term in technologies if normalized.find(term) >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - 100)
    end = min(len(clean), start + 300)
    return clean[start:end].strip()


def _marcar_corroboracao(*groups: list[dict[str, Any]]) -> None:
    domains_by_technology: dict[str, set[str]] = defaultdict(set)
    evidences = [item for group in groups for item in group]
    for item in evidences:
        for technology in item["tecnologias_detectadas"]:
            domains_by_technology[technology].add(item["dominio"])
    corroborated = {technology for technology, domains in domains_by_technology.items() if len(domains) >= 2}
    for item in evidences:
        item["corroborada"] = any(technology in corroborated for technology in item["tecnologias_detectadas"])


def _construir_resumo(
    validadas: list[dict[str, Any]],
    medias: list[dict[str, Any]],
) -> dict[str, Any]:
    evidences = validadas + medias
    domains_by_technology: dict[str, set[str]] = defaultdict(set)
    for item in evidences:
        if not item["contem_evidencia_ia"]:
            continue
        for technology in item["tecnologias_detectadas"]:
            domains_by_technology[technology].add(item["dominio"])

    technologies = sorted(domains_by_technology)
    corroborated = {tech: domains for tech, domains in domains_by_technology.items() if len(domains) >= 2}
    supporting_domains = set().union(*corroborated.values()) if corroborated else set()
    scores = [item["score_confianca"] for item in evidences]
    key_claims = [
        f"Uso de {technology} identificado em {len(domains)} fontes independentes."
        for technology, domains in sorted(corroborated.items())
    ]
    return {
        "tecnologias_detectadas": technologies,
        "fontes_corroboradas": len(supporting_domains),
        "afirmacoes_chave": key_claims,
        "nota_geral_qualidade_evidencias": round(sum(scores) / len(scores), 2) if scores else 0.0,
    }


def _canonical_url(value: Any) -> str:
    url = _clean(value)
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if not parsed.netloc:
        return ""
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/") or "/", "", parsed.query, ""))


def _domain(value: Any) -> str:
    url = _clean(value)
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().removeprefix("www.").split(":")[0]


def _same_organization_domain(left: str, right: str) -> bool:
    return left == right or left.endswith(f".{right}") or right.endswith(f".{left}")


def _matches_domain_set(domain: str, candidates: set[str]) -> bool:
    return any(domain == candidate or domain.endswith(f".{candidate}") for candidate in candidates)


def _normalize(value: Any) -> str:
    clean = _clean(value).lower()
    return "".join(char for char in unicodedata.normalize("NFKD", clean) if not unicodedata.combining(char))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()
