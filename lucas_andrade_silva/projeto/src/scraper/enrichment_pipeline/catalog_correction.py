"""Maintenance job for correcting startup_ai_radar_catalog rows."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from datetime import UTC, datetime
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import httpx

from . import config
from .identity import validate_source_identity

try:
    from ddgs import DDGS
except ModuleNotFoundError:  # pragma: no cover
    DDGS = None


PROTECTED_COLUMNS = {"id", "source_url", "created_at"}
EDITABLE_COLUMNS = {
    "company_name",
    "website",
    "description",
    "cnpj",
    "founding_year",
    "location",
    "socios",
    "cnae",
    "updated_at",
}
LEADING_NOISE_RE = re.compile(r"^\s*(?:a|o|uma|the|essa)\s+", flags=re.I)
INVALID_NAME_TOKENS = {
    "menu",
    "principal",
    "home",
    "inicio",
    "início",
    "refinaria",
    "solucao",
    "solução",
    "empresa",
    "startup",
    "plataforma",
    "produto",
    "servico",
    "serviço",
}
NEWS_HOST_PARTS = (
    "startups.com.br",
    "braziljournal",
    "exame.com",
    "valor.globo.com",
    "istoedinheiro.com.br",
    "estadao.com.br",
    "folha.uol.com.br",
    "oglobo.globo.com",
    "revistapegn.globo.com",
)
SOCIAL_HOST_PARTS = (
    "linkedin.com",
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "tiktok.com",
)
NON_OFFICIAL_HOST_PARTS = (
    "wikipedia.org",
    "wikidata.org",
    "crunchbase.com",
    "pitchbook.com",
    "glassdoor.com",
    "reclameaqui.com.br",
    "agoracupom.com.br",
    "cuponomia.com.br",
    "meliuz.com.br",
    "cupom",
    "desconto",
)
BAD_OFFICIAL_PATH_PARTS = (
    "/privacy",
    "/politica",
    "/policy",
    "/terms",
    "/termos",
    "/login",
    "/signin",
    "/security",
)
_last_request_at = 0.0
_last_cnpja_request_at = 0.0
_cnpja_rate_limit_failures = 0
_cnpja_disabled = False


def _print(message: str) -> None:
    print(f"[catalog-correction] {message}", file=sys.stderr, flush=True)


def _rate_limit() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_request_at = time.monotonic()


def _cnpja_rate_limit() -> None:
    global _last_cnpja_request_at
    elapsed = time.monotonic() - _last_cnpja_request_at
    minimum_interval = 20.0
    if elapsed < minimum_interval:
        time.sleep(minimum_interval - elapsed)
    _last_cnpja_request_at = time.monotonic()


def _request_json(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            _rate_limit()
            with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
                response = client.get(url, params=params, headers=headers or {})
                if response.status_code in {404, 429, 500, 502, 503, 504} and attempt < 2:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else config.BACKOFF_SECONDS[min(attempt, len(config.BACKOFF_SECONDS) - 1)]
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                return response.json()
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(config.BACKOFF_SECONDS[min(attempt, len(config.BACKOFF_SECONDS) - 1)])
    raise RuntimeError(last_error or f"falha ao buscar {url}")


def clean_company_name(name: str | None) -> str:
    cleaned = re.sub(r"\s+", " ", str(name or "")).strip(" -–—\t\r\n")
    return LEADING_NOISE_RE.sub("", cleaned).strip()


def is_valid_company_name(name: str | None) -> bool:
    value = clean_company_name(name)
    if not value or "@" in value or len(value) < 2:
        return False
    if len(value) > 80 or len(value.split()) > 8:
        return False
    compact = _compact(value)
    first = _compact(value.split()[0])
    if compact in INVALID_NAME_TOKENS or first in INVALID_NAME_TOKENS:
        return False
    if re.search(r"\b(?:clique|saiba|acesse|login|cadastro|voltar|continuar)\b", value, flags=re.I):
        return False
    return bool(re.search(r"[A-Za-zÀ-ÿ0-9]", value))


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text or "") if part.strip()]


def _description_payload(description: str | None, *, allow_web: bool = True) -> str:
    text = re.sub(r"\s+", " ", str(description or "")).strip()
    if not text:
        return ""
    original = re.search(r"descricao_original:\s*(.+?)(?:\s+-\s+fonte_original:|\s+CNPJ:|\s+Web:|$)", text, flags=re.I)
    if original:
        value = original.group(1).strip()
        if value and value.casefold() != "nao informada":
            return value
    web = re.search(r"\bWeb:\s*(.+?)(?:\s+Sinais IA:|\s+Mencoes BR:|\s+Fontes fortes:|\s+Inconsistencias:|$)", text, flags=re.I)
    if allow_web and web:
        value = re.sub(r"https?://\S+:\s*", "", web.group(1)).strip()
        if value:
            return value
    if web and not allow_web:
        return ""
    return text


def extract_name_from_description(description: str | None, fallback: str | None = None, *, allow_web: bool = True) -> str:
    text = _description_payload(description, allow_web=allow_web)
    fallback_clean = clean_company_name(fallback)
    if not text:
        return fallback_clean
    first = _sentences(text)[0] if _sentences(text) else text[:240]
    if fallback_clean and re.match(rf"^(?:A|O|Uma|The|Essa)?\s*{re.escape(fallback_clean)}\b", first, flags=re.I):
        return fallback_clean

    patterns = (
        r"^([A-ZÀ-Ý0-9][\wÀ-ÿ0-9&.\-]{1,40}),",
        r"\bPara\s+(?:a|o|uma|the|essa)?\s*([A-ZÀ-Ý0-9][\wÀ-ÿ0-9&.\- ]{1,50}?)(?:,|\s+(?:ser|é|e|atua|oferece|desenvolve|cria|fornece|usa|utiliza)\b)",
        r"^(?:A|O|Uma|The|Essa)\s+([A-ZÀ-Ý0-9][\wÀ-ÿ0-9&.\- ]{1,60}?)(?:\s+(?:é|e|atua|oferece|desenvolve|cria|fornece|usa|utiliza|helps|offers|provides|develops)\b|[,.;:])",
        r"\b(?:startup|empresa|plataforma)\s+([A-ZÀ-Ý0-9][\wÀ-ÿ0-9&.\- ]{1,50}?)(?:\s+(?:é|e|atua|oferece|desenvolve|cria|fornece|usa|utiliza)\b|[,.;:])",
        r"^([A-ZÀ-Ý0-9][\wÀ-ÿ0-9&.\-]{1,40})(?:\s+(?:é|e|atua|oferece|desenvolve|cria|fornece|usa|utiliza)\b|[,.;:])",
    )
    for pattern in patterns:
        match = re.search(pattern, first)
        if match:
            value = clean_company_name(match.group(1))
            if is_valid_company_name(value) and len(value.split()) <= 6:
                return value
    return fallback_clean


def _first_result(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list):
        return next((item for item in payload if isinstance(item, dict)), None)
    if not isinstance(payload, dict):
        return None
    for key in ("data", "results", "items", "companies", "estabelecimentos"):
        value = payload.get(key)
        if isinstance(value, list):
            found = next((item for item in value if isinstance(item, dict)), None)
            if found:
                return found
    return payload if payload else None


def _digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _pick_nested(payload: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current: Any = payload
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current not in (None, "", []):
            return current
    return None


def _year_from_date(value: Any) -> str:
    text = str(value or "")
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return match.group(0) if match else "Not specified"


def _format_location(payload: dict[str, Any]) -> str:
    city = _pick_nested(payload, ("address", "city"), ("estabelecimento", "cidade", "nome"), ("cidade", "nome"), ("city",))
    state = _pick_nested(payload, ("address", "state"), ("estabelecimento", "estado", "sigla"), ("estado", "sigla"), ("state",), ("uf",))
    parts = [str(part).strip() for part in (city, state) if str(part or "").strip()]
    return ", ".join(parts) if parts else "Brazil"


def _normalize_activity(value: Any) -> str | None:
    if isinstance(value, dict):
        code = value.get("code") or value.get("id")
        text = value.get("text") or value.get("descricao") or value.get("description")
        return " - ".join(str(part).strip() for part in (code, text) if str(part or "").strip()) or None
    if value:
        return str(value)
    return None


def _normalize_members(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    members: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        person = item.get("person") if isinstance(item.get("person"), dict) else {}
        name = item.get("name") or item.get("nome") or person.get("name")
        role = item.get("role") or item.get("qualificacao") or item.get("qualification")
        member = {key: str(val).strip() for key, val in {"name": name, "role": role}.items() if str(val or "").strip()}
        if member:
            members.append(member)
    return members


def normalize_cnpja_payload(payload: Any) -> dict[str, Any]:
    row = _first_result(payload) or {}
    registration = _pick_nested(row, ("taxId",), ("cnpj",), ("registration",), ("estabelecimento", "cnpj"))
    activity = _pick_nested(row, ("mainActivity",), ("primary_activity",), ("atividade_principal",), ("estabelecimento", "atividade_principal"))
    opened = _pick_nested(row, ("founded",), ("foundedAt",), ("created",), ("openDate",), ("estabelecimento", "data_inicio_atividade"), ("abertura",))
    legal_name = _pick_nested(row, ("name",), ("legalName",), ("razao_social",), ("company", "name"))
    return {
        "cnpj": _digits(registration),
        "founding_year": _year_from_date(opened),
        "location": _format_location(row),
        "socios": _normalize_members(_pick_nested(row, ("members",), ("socios",), ("qsa",)) or []),
        "cnae": _normalize_activity(activity) or "não encontrado",
        "legal_name": str(legal_name).strip() if legal_name else None,
    }


def search_cnpj(name: str) -> dict[str, Any]:
    global _cnpja_disabled, _cnpja_rate_limit_failures
    if _cnpja_disabled:
        return {}
    _cnpja_rate_limit()
    payload = _request_json("https://cnpja.com/api/company/search", params={"query": name})
    normalized = normalize_cnpja_payload(payload)
    _cnpja_rate_limit_failures = 0
    return normalized if normalized.get("cnpj") else {}


def _record_cnpja_error(error: Exception) -> None:
    global _cnpja_disabled, _cnpja_rate_limit_failures
    if "429" not in str(error):
        return
    _cnpja_rate_limit_failures += 1
    if _cnpja_rate_limit_failures >= 3:
        _cnpja_disabled = True
        _print("CNPJa suspensa nesta execucao apos 3 bloqueios 429 consecutivos")


def _is_news_or_social(url: str) -> bool:
    lowered = url.lower()
    return any(part in lowered for part in (*NEWS_HOST_PARTS, *SOCIAL_HOST_PARTS, *NON_OFFICIAL_HOST_PARTS))


def _looks_bad_official_path(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return any(part in path for part in BAD_OFFICIAL_PATH_PARTS)


def _homepage(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))


def _compact(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", ascii_value)


def _host_matches_name(url: str, name: str) -> bool:
    host = _compact(urlsplit(url).netloc.replace("www.", ""))
    name_token = _compact(clean_company_name(name).split()[0] if clean_company_name(name) else "")
    return bool(name_token and name_token in host)


def find_official_website(name: str) -> str:
    if DDGS is None:
        return "não encontrado"
    query = f"{name} empresa brasileira site oficial"
    try:
        _rate_limit()
        candidates: list[tuple[int, str]] = []
        with DDGS(timeout=config.HTTP_TIMEOUT_SECONDS) as ddgs:
            for result in ddgs.text(query, max_results=8):
                url = str(result.get("href") or result.get("url") or "").strip()
                if not url.startswith("http") or _is_news_or_social(url):
                    continue
                normalized = (
                    _homepage(url) if _looks_bad_official_path(url) else url
                )
                validation = validate_source_identity(
                    {"company_name": name},
                    {
                        "url": normalized,
                        "source_type": "web_search",
                        "origin": "ddg",
                        "title": str(result.get("title") or ""),
                        "snippet": str(
                            result.get("body") or result.get("snippet") or ""
                        ),
                        "raw_text": "",
                        "metadata": {},
                    },
                )
                if validation["classification"] != "MATCH":
                    continue
                confidence = int(validation["confidence"])
                if _host_matches_name(normalized, name):
                    confidence += 5
                candidates.append((confidence, normalized))
        if not candidates:
            return "não encontrado"
        return max(candidates, key=lambda item: item[0])[1]
    except Exception:
        return "não encontrado"


def looks_english(text: str | None) -> bool:
    value = f" {str(text or '').casefold()} "
    english_terms = (" the ", " and ", " with ", " for ", " company ", " platform ", " helps ", " uses ", " provides ", " offers ")
    portuguese_terms = (" de ", " para ", " com ", " empresa ", " plataforma ", " oferece ", " usa ", " utiliza ")
    return sum(term in value for term in english_terms) > sum(term in value for term in portuguese_terms)


def _fallback_translate_to_portuguese(text: str) -> str:
    translated = text.strip()
    replacements = (
        (r"\bThe company provides\b", "A empresa fornece"),
        (r"\ban AI platform\b", "uma plataforma de IA"),
        (r"\bAI platform\b", "plataforma de IA"),
        (r"\bfor financial teams\b", "para equipes financeiras"),
    )
    for pattern, replacement in replacements:
        translated = re.sub(pattern, replacement, translated, flags=re.I)
    return translated


def _translate_to_portuguese(text: str) -> str:
    if not text.strip() or not os.getenv("OPENROUTER_API_KEY"):
        return _fallback_translate_to_portuguese(text)
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{config.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.openrouter_api_key()}",
                    "HTTP-Referer": config.OPENROUTER_REFERER,
                    "X-Title": config.OPENROUTER_TITLE,
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.OPENROUTER_MODEL,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Traduza para portugues do Brasil preservando "
                                "todos os fatos, nomes de produtos e contexto. "
                                "Retorne somente a traducao."
                            ),
                        },
                        {"role": "user", "content": text[:2500]},
                    ],
                    "temperature": 0,
                },
            )
            response.raise_for_status()
            payload = response.json()
            translated = (
                payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return re.sub(r"\s+", " ", translated).strip() or text.strip()
    except Exception as error:
        _print(f"traducao da descricao falhou; preservando texto original: {error}")
        return _fallback_translate_to_portuguese(text)


def rewrite_description_portuguese(name: str, description: str | None, cnpj_data: dict[str, Any]) -> str | None:
    source = _description_payload(description)
    if not looks_english(source):
        return source or description
    facts = [f"{name} e uma empresa/startup identificada no catalogo."]
    if cnpj_data.get("cnpj"):
        facts.append(f"CNPJ: {cnpj_data['cnpj']}.")
    if cnpj_data.get("founding_year") and cnpj_data["founding_year"] != "Not specified":
        facts.append(f"Ano de abertura: {cnpj_data['founding_year']}.")
    if cnpj_data.get("location") and cnpj_data["location"] != "Brazil":
        facts.append(f"Localizacao: {cnpj_data['location']}.")
    if cnpj_data.get("cnae") and cnpj_data["cnae"] != "não encontrado":
        facts.append(f"Atividade principal/CNAE: {cnpj_data['cnae']}.")
    if source:
        facts.append(_translate_to_portuguese(source))
    return " ".join(facts)


def correct_row(row: dict[str, Any], *, skip_cnpj: bool = False) -> dict[str, Any]:
    current_name = clean_company_name(row.get("company_name"))
    description = str(row.get("description") or "").strip()

    # 4 -> 1
    allow_web_name = not is_valid_company_name(current_name)
    name = extract_name_from_description(description, current_name, allow_web=allow_web_name)
    name = clean_company_name(name)
    if not is_valid_company_name(name):
        name = current_name if is_valid_company_name(current_name) else ""
    has_valid_name = is_valid_company_name(name)

    # 3
    cnpj_data: dict[str, Any] = {}
    if not skip_cnpj and not _digits(row.get("cnpj")) and has_valid_name:
        try:
            cnpj_data = search_cnpj(name)
        except Exception as error:
            _record_cnpja_error(error)
            _print(f"{name}: CNPJa falhou: {error}")

    # 2
    website = find_official_website(name) if has_valid_name else "não encontrado"

    # 5
    new_description = rewrite_description_portuguese(name or current_name, description, cnpj_data)

    # 6
    founding_year = cnpj_data.get("founding_year") or "Not specified"

    updates: dict[str, Any] = {
        "website": website,
        "description": new_description,
        "founding_year": founding_year,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if has_valid_name:
        updates["company_name"] = name
    if cnpj_data:
        updates.update({
            "cnpj": cnpj_data.get("cnpj") or None,
            "location": cnpj_data.get("location") or "Brazil",
            "socios": cnpj_data.get("socios") or [],
            "cnae": cnpj_data.get("cnae") or "não encontrado",
        })
    else:
        updates["founding_year"] = "Not specified"
    return {key: value for key, value in updates.items() if key in EDITABLE_COLUMNS and key not in PROTECTED_COLUMNS}


def _has_rest_credentials() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"))


def _rest_headers() -> dict[str, str]:
    key = config.supabase_key()
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _table_url(table: str = config.ENRICHMENT_RESULTS_TABLE) -> str:
    return f"{config.supabase_url().rstrip('/')}/rest/v1/{table}"


def load_rows(limit: int | None = None, candidate_id: str | None = None, offset: int = 0) -> list[dict[str, Any]]:
    if not _has_rest_credentials():
        import psycopg2
        import psycopg2.extras

        clauses: list[str] = []
        params: list[Any] = []
        if candidate_id:
            clauses.append("candidate_id = %s")
            params.append(candidate_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = " LIMIT %s" if limit is not None else ""
        offset_sql = " OFFSET %s" if offset else ""
        if limit is not None:
            params.append(limit)
        if offset:
            params.append(offset)
        with psycopg2.connect(_database_url()) as connection:
            with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    f"SELECT * FROM {config.ENRICHMENT_RESULTS_TABLE}{where} ORDER BY updated_at DESC NULLS LAST{limit_sql}{offset_sql}",
                    params,
                )
                return [dict(row) for row in cursor.fetchall()]

    params: dict[str, str] = {"select": "*"}
    if candidate_id:
        params["candidate_id"] = f"eq.{candidate_id}"
    if limit is not None:
        params["limit"] = str(limit)
    if offset:
        params["offset"] = str(offset)
    with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.get(_table_url(), params=params, headers=_rest_headers())
    response.raise_for_status()
    payload = response.json()
    return list(payload if isinstance(payload, list) else [])


def patch_row(candidate_id: str, updates: dict[str, Any]) -> None:
    if not _has_rest_credentials():
        import psycopg2
        from psycopg2.extras import Json

        filtered = {
            key: value for key, value in updates.items()
            if key in EDITABLE_COLUMNS and key not in PROTECTED_COLUMNS
        }
        if not filtered:
            return
        assignments = ", ".join(f"{key} = %s" for key in filtered)
        values = [Json(value) if key == "socios" else value for key, value in filtered.items()]
        with psycopg2.connect(_database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {config.ENRICHMENT_RESULTS_TABLE} SET {assignments} WHERE candidate_id = %s",
                    [*values, candidate_id],
                )
        return

    with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = client.patch(
            _table_url(),
            params={"candidate_id": f"eq.{candidate_id}"},
            json=updates,
            headers={**_rest_headers(), "Prefer": "return=minimal"},
        )
    response.raise_for_status()


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL nao definido; necessario para criar colunas socios/cnae")
    return value


def ensure_extra_columns() -> None:
    import psycopg2

    with psycopg2.connect(_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                ALTER TABLE {config.ENRICHMENT_RESULTS_TABLE}
                ADD COLUMN IF NOT EXISTS socios JSONB NOT NULL DEFAULT '[]'::jsonb,
                ADD COLUMN IF NOT EXISTS cnae TEXT
                """
            )


def run(
    limit: int | None = None,
    candidate_id: str | None = None,
    offset: int = 0,
    dry_run: bool = False,
    skip_cnpj: bool = False,
) -> dict[str, int]:
    if not _has_rest_credentials() and not os.getenv("DATABASE_URL"):
        raise RuntimeError("Defina SUPABASE_URL/SUPABASE_KEY ou DATABASE_URL no .env")
    ensure_extra_columns()
    rows = load_rows(limit=limit, candidate_id=candidate_id, offset=offset)
    stats = {"loaded": len(rows), "updated": 0, "skipped": 0, "failed": 0}
    _print(f"linhas carregadas: {len(rows)}")
    for index, row in enumerate(rows, start=1):
        candidate_id_value = str(row.get("candidate_id") or "")
        label = row.get("company_name") or candidate_id_value or "sem_nome"
        if not candidate_id_value:
            stats["skipped"] += 1
            _print(f"[{index}/{len(rows)}] pulando linha sem candidate_id: {label}")
            continue
        try:
            updates = correct_row(row, skip_cnpj=skip_cnpj)
            if dry_run:
                _print(f"[{index}/{len(rows)}] dry-run {label}: {json.dumps(updates, ensure_ascii=False)}")
            else:
                patch_row(candidate_id_value, updates)
                _print(f"[{index}/{len(rows)}] salvo {label} -> {updates.get('company_name')}")
            stats["updated"] += 1
        except Exception as error:
            stats["failed"] += 1
            _print(f"[{index}/{len(rows)}] falhou {label}: {error}")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Corrige linhas de startup_ai_radar_catalog no Supabase.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--candidate-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-cnpj", action="store_true")
    args = parser.parse_args()
    print(json.dumps(
        run(limit=args.limit, candidate_id=args.candidate_id, offset=args.offset, dry_run=args.dry_run, skip_cnpj=args.skip_cnpj),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
