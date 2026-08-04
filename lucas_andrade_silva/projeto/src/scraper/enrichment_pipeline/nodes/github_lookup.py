from __future__ import annotations

import base64
import json
import re
import unicodedata
from urllib.parse import urlsplit

import httpx

from .. import config
from ..identity import company_tokens
from ..state import EnrichmentState
from .llm_summarize import append_error

MANIFEST_FILES = ("package.json", "requirements.txt", "pyproject.toml", "pom.xml", "go.mod")
STOPWORDS = {
    "para", "com", "uma", "das", "dos", "por", "the", "and", "for", "with",
    "startup", "empresa", "plataforma", "solucao", "solucoes", "tecnologia",
    "brasil", "brasileira", "brasileiro",
}


def _github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "startup-ai-radar/1.0"}
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return headers


def _search_org_candidates(candidate: dict[str, object]) -> list[dict[str, object]]:
    company_name = str(candidate.get("company_name") or candidate.get("nome") or "").strip()
    if not company_name:
        return []
    query = f"{company_name} in:login type:org"
    with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS, headers=_github_headers(), follow_redirects=True) as client:
        response = client.get(f"{config.GITHUB_API_URL.rstrip('/')}/search/users", params={"q": query, "per_page": "5"})
        response.raise_for_status()
        items = response.json().get("items", [])
    rows: list[dict[str, object]] = []
    for item in items:
        login = str(item.get("login") or "").strip()
        url = str(item.get("html_url") or "").strip()
        if not login or not url:
            continue
        rows.append(
            {
                "url": url,
                "source_type": "github",
                "origin": "github_api",
                "title": login,
                "snippet": str(item.get("type") or ""),
                "raw_text": None,
                "metadata": {"login": login, "api_url": item.get("url")},
            }
        )
    return rows


def _domain_from_state(state: EnrichmentState) -> str:
    candidate = state.get("candidate", {})
    for value in (
        state.get("validated_url"),
        candidate.get("website_url"),
        candidate.get("website"),
        candidate.get("validated_url"),
        candidate.get("source_url"),
    ):
        host = urlsplit(str(value or "")).netloc.lower()
        if host:
            return host.removeprefix("www.")
    return ""


def _search_repo_candidates(domain: str, tested_urls: set[str]) -> list[dict[str, object]]:
    if not domain:
        return []
    query = f'"{domain}" in:readme,description'
    with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS, headers=_github_headers(), follow_redirects=True) as client:
        response = client.get(f"{config.GITHUB_API_URL.rstrip('/')}/search/repositories", params={"q": query, "per_page": "5"})
        response.raise_for_status()
        items = response.json().get("items", [])
    rows: list[dict[str, object]] = []
    for item in items:
        url = str(item.get("html_url") or "").strip()
        if not url or url in tested_urls:
            continue
        owner = item.get("owner") or {}
        rows.append(
            {
                "url": url,
                "source_type": "github",
                "origin": "github_api",
                "title": str(item.get("full_name") or ""),
                "snippet": str(item.get("description") or ""),
                "raw_text": None,
                "metadata": {
                    "repo": item,
                    "owner": owner.get("login"),
                    "api_url": item.get("url"),
                    "repo_name": item.get("name"),
                },
            }
        )
    return rows


def _load_org_profile(api_url: str) -> dict[str, object]:
    with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS, headers=_github_headers(), follow_redirects=True) as client:
        response = client.get(api_url)
        response.raise_for_status()
        profile = response.json()
        repos_response = client.get(f"{api_url}/repos", params={"per_page": str(config.MAX_GITHUB_REPOS), "sort": "updated"})
        repos_response.raise_for_status()
        repos = repos_response.json()
    return {"profile": profile, "repos": repos}


def _load_repo_readme(owner: str, repo: str) -> str:
    if not owner or not repo:
        return ""
    url = f"{config.GITHUB_API_URL.rstrip('/')}/repos/{owner}/{repo}/readme"
    with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS, headers=_github_headers(), follow_redirects=True) as client:
        response = client.get(url)
        if response.status_code == 404:
            return ""
        response.raise_for_status()
        payload = response.json()
    encoded = str(payload.get("content") or "")
    try:
        return base64.b64decode(encoded, validate=False).decode("utf-8", errors="replace")[:4000]
    except Exception:
        return ""


def _load_manifest(owner: str, repo: str, path: str) -> str:
    url = f"{config.GITHUB_API_URL.rstrip('/')}/repos/{owner}/{repo}/contents/{path}"
    with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS, headers=_github_headers(), follow_redirects=True) as client:
        response = client.get(url)
        if response.status_code == 404:
            return ""
        response.raise_for_status()
        payload = response.json()
    encoded = str(payload.get("content") or "")
    try:
        return base64.b64decode(encoded, validate=False).decode("utf-8", errors="replace")[:20000]
    except Exception:
        return ""


def _repo_signal_text(repos: list[dict[str, object]]) -> list[str]:
    snippets: list[str] = []
    for repo in repos:
        pieces = [
            str(repo.get("name") or ""),
            str(repo.get("description") or ""),
            " ".join(str(topic) for topic in repo.get("topics") or []),
            str(repo.get("language") or ""),
        ]
        text = " ".join(piece for piece in pieces if piece).strip()
        if text:
            snippets.append(text)
    return snippets


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _word_set(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{4,}", _fold(value))
        if token not in STOPWORDS
    }


def _metadata_text(metadata: dict[str, object]) -> str:
    pieces = [
        str(metadata.get("descricao_repo") or ""),
        str(metadata.get("readme_trecho") or ""),
        " ".join(str(item) for item in metadata.get("linguagens") or []),
        " ".join(str(item) for item in metadata.get("topicos") or []),
        str(metadata.get("organizacao_ou_owner") or ""),
        str(metadata.get("blog") or ""),
    ]
    return " ".join(piece for piece in pieces if piece)


def _site_text(state: EnrichmentState) -> str:
    candidate = state.get("candidate", {})
    source = state.get("validated_source") or {}
    return " ".join(
        str(piece or "")
        for piece in (
            candidate.get("description"),
            candidate.get("segment"),
            candidate.get("sector"),
            candidate.get("market"),
            state.get("company_description"),
            source.get("raw_text"),
            " ".join((state.get("web_context") or {}).values()),
        )
        if piece
    )


def cross_validate_github_candidate(state: EnrichmentState, source: dict[str, object]) -> dict[str, object]:
    metadata = dict(source.get("metadata") or {})
    domain = _domain_from_state(state)
    company_name = str((state.get("candidate") or {}).get("company_name") or (state.get("candidate") or {}).get("nome") or "")
    metadata_text = _fold(_metadata_text(metadata))
    criteria: list[str] = []
    evidence: list[str] = []

    if domain and _fold(domain) in metadata_text:
        criteria.append("dominio_presente")
        evidence.append(f"dominio {domain} encontrado nos metadados/README do GitHub")

    site_terms = _word_set(_site_text(state))
    repo_terms = _word_set(metadata_text)
    semantic_overlap = sorted(site_terms & repo_terms)
    if len(semantic_overlap) >= 2:
        criteria.append("match_semantico_descricao")
        evidence.append("termos compartilhados: " + ", ".join(semantic_overlap[:6]))

    owner = str(metadata.get("organizacao_ou_owner") or metadata.get("owner") or metadata.get("login") or "")
    owner_folded = re.sub(r"[^a-z0-9]", "", _fold(owner))
    company_tokens_folded = [re.sub(r"[^a-z0-9]", "", _fold(token)) for token in company_tokens(company_name)]
    brand_folded = "".join(company_tokens_folded[:2])
    if owner_folded and (owner_folded in company_tokens_folded or owner_folded == brand_folded):
        criteria.append("owner_corresponde_marca")
        evidence.append(f"owner GitHub '{owner}' corresponde a marca '{company_name}'")

    if len(criteria) >= 2:
        return {"validado": True, "criterios_atendidos": criteria, "evidencia": "; ".join(evidence)}
    missing = {"dominio_presente", "match_semantico_descricao", "owner_corresponde_marca"} - set(criteria)
    return {"validado": False, "motivo": "criterios ausentes: " + ", ".join(sorted(missing)), "criterios_atendidos": criteria}


def _repo_identity(repo: dict[str, object]) -> tuple[str, str]:
    owner = repo.get("owner") or {}
    return str(owner.get("login") or ""), str(repo.get("name") or "")


def _manifest_dependencies(path: str, content: str) -> list[str]:
    if not content.strip():
        return []
    if path == "package.json":
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return []
        deps: list[str] = []
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            values = payload.get(key) or {}
            if isinstance(values, dict):
                deps.extend(str(name) for name in values)
        return deps
    if path == "requirements.txt":
        return [
            re.split(r"[<>=!~\[]", line.strip(), maxsplit=1)[0]
            for line in content.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    if path == "go.mod":
        return [line.split()[1] for line in content.splitlines() if line.strip().startswith("require ") and len(line.split()) >= 2]
    return sorted(_word_set(content))[:20]


def extract_validated_github_stack(repos: list[dict[str, object]]) -> tuple[list[str], list[dict[str, object]]]:
    stack: list[str] = []
    evidence: list[dict[str, object]] = []
    for repo in repos[: config.MAX_GITHUB_REPOS]:
        owner, repo_name = _repo_identity(repo)
        repo_url = str(repo.get("html_url") or "")
        for value, source_path in (
            (repo.get("language"), "github_language"),
            *[(topic, "github_topic") for topic in repo.get("topics") or []],
        ):
            item = str(value or "").strip()
            if not item:
                continue
            stack.append(item)
            evidence.append({"tecnologia": item, "fonte": source_path, "repo_url": repo_url})
        for path in MANIFEST_FILES:
            try:
                content = _load_manifest(owner, repo_name, path)
            except Exception:
                continue
            for dependency in _manifest_dependencies(path, content):
                item = dependency.strip()
                if not item:
                    continue
                stack.append(item)
                evidence.append({"tecnologia": item, "fonte": path, "repo_url": repo_url})
    return sorted(dict.fromkeys(stack)), evidence


def _candidate_metadata(source: dict[str, object], payload: dict[str, object]) -> dict[str, object]:
    metadata = dict(source.get("metadata") or {})
    if "profile" in payload:
        profile = dict(payload.get("profile") or {})
        repos = list(payload.get("repos") or [])
        readme = ""
        for repo in repos[: config.MAX_GITHUB_REPOS]:
            owner, repo_name = _repo_identity(repo)
            try:
                readme = _load_repo_readme(owner, repo_name)
            except Exception:
                readme = ""
            if readme:
                break
        metadata.update(
            {
                "descricao_repo": " ".join(str(repo.get("description") or "") for repo in repos),
                "readme_trecho": readme[:1200],
                "linguagens": [str(repo.get("language")) for repo in repos if repo.get("language")],
                "topicos": sorted({str(topic) for repo in repos for topic in (repo.get("topics") or [])}),
                "organizacao_ou_owner": profile.get("login"),
                "blog": profile.get("blog"),
            }
        )
        return metadata
    repo = dict(metadata.get("repo") or {})
    owner, repo_name = _repo_identity(repo)
    readme = ""
    try:
        readme = _load_repo_readme(owner, repo_name)
    except Exception:
        readme = ""
    metadata.update(
        {
            "descricao_repo": repo.get("description"),
            "readme_trecho": readme[:1200],
            "linguagens": [repo.get("language")] if repo.get("language") else [],
            "topicos": list(repo.get("topics") or []),
            "organizacao_ou_owner": owner,
            "blog": repo.get("homepage"),
        }
    )
    return metadata


def github_lookup_node(state: EnrichmentState) -> dict[str, object]:
    if state.get("skip_github") or state.get("run_deep_enrichment") is False or ("validated_url" in state and not state.get("validated_url")):
        reason = (
            "desabilitado"
            if state.get("skip_github")
            else "nao_executado_sem_url_validada"
            if "validated_url" in state and not state.get("validated_url")
            else "nao_executado_fora_do_deep_enrichment"
        )
        insufficient = list(state.get("dados_insuficientes") or [])
        insufficient.append(f"github_discovery:{reason}")
        return {
            "github_profile": state.get("github_profile") or {},
            "github_candidatos_testados": list(
                state.get("github_candidatos_testados") or []
            ),
            "github_tentativas": int(state.get("github_tentativas") or 0),
            "github_repo_validado": None,
            "github_validacao_status": reason,
            "github_validacao_evidencia": None,
            "github_validacao_criterios": [],
            "dados_insuficientes": list(dict.fromkeys(insufficient)),
            "errors": state.get("errors", {}),
        }
    candidate = state.get("candidate", {})
    errors = state.get("errors", {})
    identity_evidence = dict(state.get("identity_evidence") or {})
    sources = list(identity_evidence.get("sources", []))
    tested_urls = set(state.get("github_candidatos_testados") or [])
    attempts = int(state.get("github_tentativas") or 0)
    try:
        candidates = [
            source
            for source in _search_org_candidates(candidate)
            if str(source.get("url") or "") not in tested_urls
        ]
        candidates.extend(_search_repo_candidates(_domain_from_state(state), tested_urls))
    except Exception as error:
        insufficient = list(state.get("dados_insuficientes") or [])
        insufficient.append(f"github_discovery:erro:{error}")
        return {
            "github_profile": {},
            "github_candidatos_testados": sorted(tested_urls),
            "github_tentativas": attempts,
            "github_repo_validado": None,
            "github_validacao_status": "erro",
            "github_validacao_evidencia": None,
            "github_validacao_criterios": [],
            "dados_insuficientes": list(dict.fromkeys(insufficient)),
            "errors": append_error(errors, "github_lookup", str(error)),
        }

    best_profile: dict[str, object] = {}
    validated_sources = list(state.get("validated_sources", []))
    for source in candidates:
        if attempts >= config.MAX_GITHUB_VALIDATION_ATTEMPTS:
            break
        url = str(source.get("url") or "")
        if not url or url in tested_urls:
            continue
        tested_urls.add(url)
        attempts += 1
        metadata = dict(source.get("metadata") or {})
        api_url = str(metadata.get("api_url") or "")
        payload: dict[str, object] = {}
        if api_url:
            try:
                if metadata.get("repo"):
                    payload = {"repos": [metadata["repo"]]}
                else:
                    payload = _load_org_profile(api_url)
            except Exception as error:
                errors = append_error(errors, "github_lookup", f"{source.get('url')}: {error}")
                continue
        repos = list(payload.get("repos") or [])
        metadata = _candidate_metadata(source, payload)
        source["metadata"] = metadata
        source["raw_text"] = _metadata_text(metadata)[:6000]
        validation = cross_validate_github_candidate(state, source)
        sources.append({"url": url, "source_type": "github", "origin": "github_api", "validation": validation})
        if not validation.get("validado"):
            continue

        tech_stack, stack_evidence = extract_validated_github_stack(repos)
        profile = dict(payload.get("profile") or {})
        best_profile = {
            "login": metadata.get("organizacao_ou_owner"),
            "url": url,
            "name": profile.get("name") or metadata.get("organizacao_ou_owner"),
            "description": metadata.get("descricao_repo"),
            "location": profile.get("location"),
            "blog": metadata.get("blog"),
            "repos": repos,
            "tech_stack": tech_stack,
            "ai_integrations": [],
            "tech_stack_sources": stack_evidence,
            "validation": validation,
        }
        validated_sources.append({**source, "validation": {"classification": "MATCH", "confidence": 100, **validation}})
        identity_evidence["sources"] = sources
        return {
            "github_profile": best_profile,
            "validated_sources": validated_sources,
            "identity_evidence": identity_evidence,
            "github_candidatos_testados": sorted(tested_urls),
            "github_tentativas": attempts,
            "github_repo_validado": url,
            "github_validacao_status": "confirmado",
            "github_validacao_evidencia": validation.get("evidencia"),
            "github_validacao_criterios": list(validation.get("criterios_atendidos") or []),
            "github_stack_evidence": stack_evidence,
            "errors": errors,
        }

    identity_evidence["sources"] = sources
    status = (
        "esgotado"
        if attempts >= config.MAX_GITHUB_VALIDATION_ATTEMPTS
        else "sem_candidatos"
        if attempts == 0
        else "rejeitado"
    )
    dados_insuficientes = list(state.get("dados_insuficientes") or [])
    dados_insuficientes.append("github_repo_validado")
    dados_insuficientes.append(
        f"github_discovery:{status}:tentativas={attempts}"
    )
    return {
        "github_profile": best_profile,
        "validated_sources": validated_sources,
        "identity_evidence": identity_evidence,
        "github_candidatos_testados": sorted(tested_urls),
        "github_tentativas": attempts,
        "github_repo_validado": None,
        "github_validacao_status": status,
        "github_validacao_evidencia": None,
        "github_validacao_criterios": [],
        "dados_insuficientes": list(dict.fromkeys(dados_insuficientes)),
        "errors": errors,
    }
