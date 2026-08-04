from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PROCESSED_DIR = Path("data/processed/_cubo")
CURATED_DIR = Path("data/curated/_cubo")


def construir_curated_cubo(
    input_path: Path | None = None,
    output_dir: Path = CURATED_DIR,
) -> dict[str, Any]:
    arquivo = input_path or _arquivo_lapidado_mais_recente()
    payload = json.loads(arquivo.read_text(encoding="utf-8"))
    resultado = construir_curated_cubo_de_payload(payload)
    _salvar_curated(resultado, output_dir)
    return resultado


def construir_curated_cubo_de_payload(payload: dict[str, Any]) -> dict[str, Any]:
    startups = payload.get("startups", [])
    grupos = _agrupar_startups(startups)
    empresas = [_consolidar_grupo(grupo) for grupo in grupos]
    empresas = sorted(empresas, key=lambda item: item["nome"].lower())

    return {
        "metadados": {
            "fonte": "Cubo Itaú - Vitrine de Startups",
            "camada": "curated",
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "total_entrada": len(startups),
            "total_curado": len(empresas),
            "duplicatas_consolidadas": len(startups) - len(empresas),
        },
        "startups": empresas,
    }


def _agrupar_startups(startups: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    grupos: list[list[dict[str, Any]]] = []

    for startup in startups:
        for grupo in grupos:
            if any(_mesma_empresa(startup, existente) for existente in grupo):
                grupo.append(startup)
                break
        else:
            grupos.append([startup])

    return grupos


def _mesma_empresa(first: dict[str, Any], second: dict[str, Any]) -> bool:
    first_domain = _dominio(first.get("site"))
    second_domain = _dominio(second.get("site"))
    if first_domain and second_domain and first_domain == second_domain:
        return True

    first_name = _normalizar_nome(first.get("nome"))
    second_name = _normalizar_nome(second.get("nome"))
    if first_name and second_name and first_name == second_name:
        return True

    first_profile = first.get("link_perfil_cubo")
    second_profile = second.get("link_perfil_cubo")
    return bool(first_profile and second_profile and first_profile == second_profile)


def _consolidar_grupo(grupo: list[dict[str, Any]]) -> dict[str, Any]:
    melhor = _melhor_registro(grupo)
    nome = melhor.get("nome") or "Startup sem nome"
    aliases = sorted(
        {
            str(item["nome"])
            for item in grupo
            if item.get("nome") and item.get("nome") != nome
        }
    )
    fontes = _consolidar_fontes(grupo)
    qualidade = _consolidar_qualidade(grupo)
    prosseguir_info = _decisao_pipeline(melhor)
    dominio = _dominio(melhor.get("site"))

    return {
        "startup_id": _startup_id(nome, dominio),
        "nome": nome,
        "aliases": aliases,
        "site": melhor.get("site"),
        "dominio": dominio,
        "cidade": melhor.get("cidade"),
        "estado": melhor.get("estado"),
        "pais": melhor.get("pais"),
        "categoria": melhor.get("categoria"),
        "descricao_curta": melhor.get("descricao_curta"),
        "logo_url": melhor.get("logo_url"),
        "qualidade": qualidade,
        "decisao_pipeline": prosseguir_info,
        "fontes": fontes,
        "raw_refs": [
            {
                "nome": item.get("nome"),
                "site": item.get("site"),
                "link_perfil_cubo": item.get("link_perfil_cubo"),
                "qualidade_score": item.get("qualidade", {}).get("score"),
            }
            for item in grupo
        ],
    }


def _melhor_registro(grupo: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        grupo,
        key=lambda item: (
            item.get("qualidade", {}).get("score", 0),
            _campos_preenchidos(item),
            len(item.get("descricao_curta") or ""),
        ),
        reverse=True,
    )[0]


def _consolidar_fontes(grupo: list[dict[str, Any]]) -> list[dict[str, str]]:
    fontes = []
    vistos = set()

    for item in grupo:
        for tipo, url in (
            ("cubo_perfil", item.get("link_perfil_cubo")),
            ("site_oficial", item.get("site")),
        ):
            if not url or url in vistos:
                continue
            vistos.add(url)
            fontes.append({"tipo": tipo, "url": url})

    return fontes


def _consolidar_qualidade(grupo: list[dict[str, Any]]) -> dict[str, Any]:
    melhor_score = max(item.get("qualidade", {}).get("score", 0) for item in grupo)
    alertas = []
    for item in grupo:
        alertas.extend(item.get("qualidade", {}).get("alertas", []))

    return {
        "score": melhor_score,
        "status": _status_qualidade(melhor_score),
        "merged_from_count": len(grupo),
        "alertas": sorted(set(alertas)),
    }


def _decisao_pipeline(startup: dict[str, Any]) -> dict[str, Any]:
    qualidade = startup.get("qualidade", {})
    motivos = list(qualidade.get("alertas", []))
    campos_obrigatorios = ("site", "cidade", "estado", "pais", "categoria")

    for campo in campos_obrigatorios:
        if not startup.get(campo):
            motivos.append(f"{campo} ausente")

    prosseguir = not motivos and qualidade.get("score", 0) >= 0.8
    return {
        "prosseguir": prosseguir,
        "motivos": sorted(set(motivos)),
    }


def _status_qualidade(score: float) -> str:
    if score >= 0.8:
        return "boa"
    if score >= 0.6:
        return "media"
    return "baixa"


def _startup_id(nome: str, dominio: str | None) -> str:
    base = _slugify(dominio or nome)
    digest = hashlib.sha1(f"{nome}|{dominio}".encode("utf-8")).hexdigest()[:8]
    return f"cubo_{base}_{digest}"


def _campos_preenchidos(startup: dict[str, Any]) -> int:
    return sum(
        1
        for campo in ("nome", "site", "cidade", "estado", "pais", "categoria", "descricao_curta")
        if startup.get(campo)
    )


def _dominio(url: Any) -> str | None:
    if not url:
        return None
    parsed = urlparse(str(url))
    if not parsed.netloc:
        return None
    return parsed.netloc.lower().replace("www.", "")


def _normalizar_nome(value: Any) -> str:
    text = _remover_acentos(str(value or "")).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _slugify(value: str) -> str:
    text = _remover_acentos(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "startup"


def _remover_acentos(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _arquivo_lapidado_mais_recente() -> Path:
    arquivos = sorted(
        PROCESSED_DIR.glob("vitrine_cubo_lapidado_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not arquivos:
        raise FileNotFoundError(f"Nenhum arquivo lapidado encontrado em {PROCESSED_DIR}")
    return arquivos[-1]


def _salvar_curated(resultado: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"vitrine_cubo_curated_{timestamp}.json"
    path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
