from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse


LOGGER = logging.getLogger(__name__)

CUBO_BASE_URL = "https://cubo.itau"
FONTE_URL = "https://cubo.itau/startups-portfolio"
VERSAO_LIMPEZA = "1.0"
RAW_DIR = Path("data/raw/_cubo")
PROCESSED_DIR = Path("data/processed/_cubo")

CAMPOS_TEXTO = (
    "nome",
    "cidade",
    "estado",
    "pais",
    "categoria",
    "descricao_curta",
)
CAMPOS_URL = ("site", "logo_url", "link_perfil_cubo")
CAMPOS_PRINCIPAIS = ("nome", "site", "cidade", "estado", "pais", "categoria")

ESTADOS_BRASIL = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amapá": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "ceará": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "espírito santo": "ES",
    "goias": "GO",
    "goiás": "GO",
    "maranhao": "MA",
    "maranhão": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "pará": "PA",
    "paraiba": "PB",
    "paraíba": "PB",
    "parana": "PR",
    "paraná": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "piauí": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "rondônia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "são paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}
SIGLAS_ESTADOS = set(ESTADOS_BRASIL.values())
CIDADE_ESTADO_ESPERADO = {
    "sao paulo": "SP",
    "são paulo": "SP",
    "rio de janeiro": "RJ",
    "belo horizonte": "MG",
    "curitiba": "PR",
    "porto alegre": "RS",
    "florianopolis": "SC",
    "florianópolis": "SC",
    "recife": "PE",
    "salvador": "BA",
    "fortaleza": "CE",
    "brasilia": "DF",
    "brasília": "DF",
}
TRACKING_PARAMS_PREFIXES = ("utm_",)
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def lapidar_arquivo_cubo(
    input_path: Path | None = None,
    output_dir: Path = PROCESSED_DIR,
) -> dict[str, Any]:
    arquivo = input_path or _arquivo_raw_mais_recente()
    LOGGER.info("Lapidando arquivo bruto do Cubo: %s", arquivo)
    payload = json.loads(arquivo.read_text(encoding="utf-8"))
    resultado = lapidar_dados_cubo(payload)
    _salvar_resultado(resultado, output_dir)
    return resultado


def lapidar_dados_cubo(payload: Any) -> dict[str, Any]:
    startups_brutas = _extrair_lista_startups(payload)
    data_scraping = _extrair_data_scraping(payload)
    registros_removidos = []
    startups_lapidadas = []
    relatorio_startups = []

    for index, raw_startup in enumerate(startups_brutas):
        bruto_normalizado = _adaptar_formato_bruto(raw_startup)
        nome_original = bruto_normalizado.get("nome")
        if not _tem_nome_valido(nome_original):
            registros_removidos.append(
                {
                    "indice": index,
                    "nome": nome_original,
                    "motivo": "Registro removido porque o campo nome estava vazio, nulo ou continha apenas espaços.",
                    "raw": raw_startup,
                }
            )
            continue

        startup, eventos = _lapidar_startup(bruto_normalizado, raw_startup)
        qualidade = _calcular_qualidade(startup, eventos)
        startup["qualidade"] = qualidade
        startups_lapidadas.append(startup)
        relatorio_startups.append(_relatorio_startup(startup, eventos, qualidade))

    total_incompletas = sum(
        1
        for startup in startups_lapidadas
        if startup["qualidade"]["baixa_qualidade"] or startup["qualidade"]["incompleto"]
    )
    completude_media = _completude_media(startups_lapidadas)
    total_alteracoes = sum(
        item["total_alteracoes"] for item in relatorio_startups
    )

    metadados = {
        "fonte_url": FONTE_URL,
        "data_scraping": data_scraping,
        "versao_limpeza": VERSAO_LIMPEZA,
        "total_bruto": len(startups_brutas),
        "total_valido": len(startups_lapidadas),
        "total_incompletas": total_incompletas,
        "registros_removidos": registros_removidos,
    }
    relatorio = _montar_relatorio(
        metadados=metadados,
        relatorio_startups=relatorio_startups,
        total_alteracoes=total_alteracoes,
        completude_media=completude_media,
    )

    return {
        "RELATORIO_DE_LAPIDACAO": relatorio,
        "JSON_LAPIDADO": {
            "metadados": metadados,
            "startups": startups_lapidadas,
        },
    }


def _lapidar_startup(
    startup: dict[str, Any],
    raw_original: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    eventos: list[dict[str, Any]] = []
    tratado = {campo: startup.get(campo) for campo in CAMPOS_TEXTO + CAMPOS_URL}

    _normalizar_textos(tratado, eventos)
    _separar_cidade_estado(tratado, eventos)
    _normalizar_estado(tratado, eventos)
    _inferir_pais(tratado, eventos)
    _normalizar_urls(tratado, eventos)
    _verificar_consistencia_cidade_estado(tratado, eventos)

    tratado["raw"] = raw_original
    return tratado, eventos


def _normalizar_textos(
    startup: dict[str, Any],
    eventos: list[dict[str, Any]],
) -> None:
    for campo in CAMPOS_TEXTO:
        original = startup.get(campo)
        if original is None:
            continue

        limpo = _limpar_espacos(original)
        if campo == "cidade":
            normalizado = limpo.title()
        elif campo == "estado":
            normalizado = limpo.upper()
        elif campo in {"pais", "categoria"}:
            normalizado = limpo.title()
        else:
            normalizado = limpo

        _registrar_alteracao(eventos, campo, original, normalizado, "normalizacao_texto")
        startup[campo] = normalizado or None


def _separar_cidade_estado(
    startup: dict[str, Any],
    eventos: list[dict[str, Any]],
) -> None:
    cidade = startup.get("cidade")
    estado = startup.get("estado")
    if not cidade or estado:
        return

    match = re.match(r"^(.+?),\s*([A-Za-z]{2})$", cidade)
    if not match:
        return

    nova_cidade = _limpar_espacos(match.group(1)).title()
    novo_estado = match.group(2).upper()
    startup["cidade"] = nova_cidade
    startup["estado"] = novo_estado
    eventos.append(
        {
            "tipo": "inferencia_controlada",
            "campo": "cidade_estado",
            "antes": cidade,
            "depois": {"cidade": nova_cidade, "estado": novo_estado},
            "motivo": "Cidade estava no formato 'Cidade, UF'.",
        }
    )


def _normalizar_estado(
    startup: dict[str, Any],
    eventos: list[dict[str, Any]],
) -> None:
    estado = startup.get("estado")
    if not estado:
        return

    estado_limpo = _limpar_espacos(estado)
    if estado_limpo.upper() in SIGLAS_ESTADOS and len(estado_limpo) == 2:
        startup["estado"] = estado_limpo.upper()
        return

    convertido = ESTADOS_BRASIL.get(estado_limpo.lower())
    if convertido:
        startup["estado"] = convertido
        eventos.append(
            {
                "tipo": "normalizacao_estado",
                "campo": "estado",
                "antes": estado,
                "depois": convertido,
                "motivo": "Nome do estado convertido para sigla.",
            }
        )
        return

    eventos.append(
        {
            "tipo": "alerta",
            "campo": "estado",
            "antes": estado,
            "depois": estado,
            "motivo": "Estado nao reconhecido como sigla brasileira ou nome mapeado.",
        }
    )


def _inferir_pais(
    startup: dict[str, Any],
    eventos: list[dict[str, Any]],
) -> None:
    if startup.get("pais"):
        return

    startup["pais"] = "Brasil"
    eventos.append(
        {
            "tipo": "inferencia_controlada",
            "campo": "pais",
            "antes": None,
            "depois": "Brasil",
            "motivo": "Pais vazio preenchido pela regra padrao do ecossistema Cubo.",
        }
    )


def _normalizar_urls(
    startup: dict[str, Any],
    eventos: list[dict[str, Any]],
) -> None:
    for campo in CAMPOS_URL:
        original = startup.get(campo)
        normalizada, evento = _normalizar_url(original, campo)
        if evento:
            eventos.append(evento)
        _registrar_alteracao(eventos, campo, original, normalizada, "normalizacao_url")
        startup[campo] = normalizada


def _normalizar_url(value: Any, campo: str) -> tuple[str | None, dict[str, Any] | None]:
    if value is None or _limpar_espacos(value) == "":
        return None, None

    texto = _limpar_espacos(value)
    if texto.lower() in {"sem site", "nao possui", "não possui", "n/a"}:
        return None, {
            "tipo": "url_invalida",
            "campo": campo,
            "antes": texto,
            "depois": None,
            "motivo": "Valor textual nao representa uma URL.",
        }

    absoluta = texto
    if texto.startswith("//"):
        absoluta = f"https:{texto}"
    elif texto.startswith("/"):
        absoluta = urljoin(CUBO_BASE_URL, texto)
    elif not re.match(r"^https?://", texto, flags=re.IGNORECASE):
        absoluta = f"https://{texto}"

    parsed = urlparse(absoluta)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, {
            "tipo": "url_invalida",
            "campo": campo,
            "antes": texto,
            "depois": None,
            "motivo": "URL nao possui esquema HTTP/HTTPS e dominio valido.",
        }

    query = parse_qsl(parsed.query, keep_blank_values=True)
    query_filtrada = [
        (key, val)
        for key, val in query
        if key not in TRACKING_PARAMS
        and not any(key.startswith(prefix) for prefix in TRACKING_PARAMS_PREFIXES)
    ]
    nova_query = urlencode(query_filtrada)
    sem_tracking = urlunparse(parsed._replace(query=nova_query))

    if sem_tracking != absoluta:
        return sem_tracking, {
            "tipo": "tracking_removido",
            "campo": campo,
            "antes": absoluta,
            "depois": sem_tracking,
            "motivo": "Parametros obvios de rastreamento foram removidos.",
        }

    return absoluta, None


def _verificar_consistencia_cidade_estado(
    startup: dict[str, Any],
    eventos: list[dict[str, Any]],
) -> None:
    cidade = startup.get("cidade")
    estado = startup.get("estado")
    if not cidade or not estado:
        return

    esperado = CIDADE_ESTADO_ESPERADO.get(cidade.lower())
    if esperado and esperado != estado:
        eventos.append(
            {
                "tipo": "alerta",
                "campo": "cidade_estado",
                "antes": {"cidade": cidade, "estado": estado},
                "depois": {"cidade": cidade, "estado": estado},
                "motivo": f"Inconsistencia suspeita: cidade costuma pertencer a {esperado}, mas estado informado foi {estado}.",
            }
        )


def _calcular_qualidade(
    startup: dict[str, Any],
    eventos: list[dict[str, Any]],
) -> dict[str, Any]:
    preenchidos = sum(1 for campo in CAMPOS_PRINCIPAIS if startup.get(campo))
    completude = preenchidos / len(CAMPOS_PRINCIPAIS)
    site_valido = 1.0 if startup.get("site") else 0.0
    consistencia = 0.0 if _tem_alerta_cidade_estado(eventos) else 1.0
    sem_conflitos = 0.0 if _tem_alertas(eventos) else 1.0
    score = round(
        (completude * 0.5)
        + (site_valido * 0.2)
        + (consistencia * 0.2)
        + (sem_conflitos * 0.1),
        4,
    )
    alertas = [evento["motivo"] for evento in eventos if evento["tipo"] == "alerta"]
    incompleto = preenchidos < 4
    if incompleto:
        alertas.append("Registro incompleto: menos de 4 campos principais preenchidos.")
    if score < 0.4:
        alertas.append("Baixa qualidade: score abaixo de 0.4.")

    return {
        "score": score,
        "completude": f"{preenchidos}/{len(CAMPOS_PRINCIPAIS)}",
        "completude_percentual": round(completude, 4),
        "incompleto": incompleto,
        "baixa_qualidade": score < 0.4,
        "componentes": {
            "completude_peso_0_5": round(completude * 0.5, 4),
            "site_valido_peso_0_2": round(site_valido * 0.2, 4),
            "cidade_estado_consistente_peso_0_2": round(consistencia * 0.2, 4),
            "normalizacao_sem_conflitos_peso_0_1": round(sem_conflitos * 0.1, 4),
        },
        "alertas": alertas,
    }


def _adaptar_formato_bruto(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "nome": raw.get("nome"),
        "site": raw.get("site"),
        "cidade": raw.get("cidade"),
        "estado": raw.get("estado"),
        "pais": raw.get("pais"),
        "categoria": raw.get("categoria") or raw.get("segmento"),
        "descricao_curta": raw.get("descricao_curta"),
        "logo_url": raw.get("logo_url") or raw.get("image_url"),
        "link_perfil_cubo": raw.get("link_perfil_cubo") or raw.get("url_perfil"),
    }


def _extrair_lista_startups(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        startups = payload.get("startups") or payload.get("dados") or []
        return startups if isinstance(startups, list) else []
    return []


def _extrair_data_scraping(payload: Any) -> str:
    if isinstance(payload, dict):
        metadados = payload.get("metadados", {})
        data = metadados.get("data_scraping") or payload.get("data_scraping")
        if data:
            return str(data)
    return datetime.now(timezone.utc).date().isoformat()


def _arquivo_raw_mais_recente() -> Path:
    arquivos = sorted(RAW_DIR.glob("vitrine_cubo_*.json"), key=lambda path: path.stat().st_mtime)
    if not arquivos:
        raise FileNotFoundError(f"Nenhum arquivo bruto encontrado em {RAW_DIR}")
    return arquivos[-1]


def _salvar_resultado(resultado: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"vitrine_cubo_lapidado_{timestamp}.json"
    report_path = output_dir / f"relatorio_lapidacao_cubo_{timestamp}.md"

    json_path.write_text(
        json.dumps(resultado["JSON_LAPIDADO"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path.write_text(resultado["RELATORIO_DE_LAPIDACAO"], encoding="utf-8")
    LOGGER.info("JSON lapidado salvo em %s", json_path)
    LOGGER.info("Relatorio de lapidacao salvo em %s", report_path)


def _montar_relatorio(
    metadados: dict[str, Any],
    relatorio_startups: list[dict[str, Any]],
    total_alteracoes: int,
    completude_media: float,
) -> str:
    linhas = [
        "# RELATORIO_DE_LAPIDACAO",
        "",
        "## Resumo estatistico",
        f"- Total bruto recebido: {metadados['total_bruto']}",
        f"- Total valido apos remocao: {metadados['total_valido']}",
        f"- Total de registros incompletos ou baixa qualidade: {metadados['total_incompletas']}",
        f"- Total de alteracoes registradas: {total_alteracoes}",
        f"- Completude media: {completude_media:.2%}",
        "",
        "## Formula de qualidade",
        "- Completude dos campos principais: peso 0.5",
        "- Presenca de site valido: peso 0.2",
        "- Consistencia cidade/estado: peso 0.2",
        "- Normalizacao sem conflitos: peso 0.1",
        "- Scores abaixo de 0.4 sao classificados como baixa qualidade.",
        "",
        "## Registros removidos",
    ]

    if metadados["registros_removidos"]:
        for removido in metadados["registros_removidos"]:
            linhas.append(f"- Indice {removido['indice']}: {removido['motivo']}")
    else:
        linhas.append("- Nenhum registro removido.")

    linhas.extend(["", "## Tratamento por startup"])
    for item in relatorio_startups:
        linhas.append(f"### {item['nome']}")
        linhas.append(f"- Score de qualidade: {item['score']} ({item['completude']})")
        if item["alteracoes"]:
            linhas.append("- Campos alterados:")
            for alteracao in item["alteracoes"]:
                linhas.append(
                    f"  - {alteracao['campo']}: {alteracao['antes']!r} -> {alteracao['depois']!r} ({alteracao['motivo']})"
                )
        else:
            linhas.append("- Nenhum campo alterado alem da preservacao do raw.")
        if item["alertas"]:
            linhas.append("- Alertas:")
            for alerta in item["alertas"]:
                linhas.append(f"  - {alerta}")
        else:
            linhas.append("- Nenhuma inconsistencia detectada.")
        linhas.append("")

    return "\n".join(linhas)


def _relatorio_startup(
    startup: dict[str, Any],
    eventos: list[dict[str, Any]],
    qualidade: dict[str, Any],
) -> dict[str, Any]:
    alteracoes = [
        evento
        for evento in eventos
        if evento.get("antes") != evento.get("depois")
        and evento["tipo"] != "alerta"
    ]
    return {
        "nome": startup["nome"],
        "score": qualidade["score"],
        "completude": qualidade["completude"],
        "alteracoes": alteracoes,
        "alertas": qualidade["alertas"],
        "total_alteracoes": len(alteracoes),
    }


def _completude_media(startups: list[dict[str, Any]]) -> float:
    if not startups:
        return 0.0
    return sum(
        startup["qualidade"]["completude_percentual"] for startup in startups
    ) / len(startups)


def _tem_nome_valido(value: Any) -> bool:
    return bool(_limpar_espacos(value))


def _limpar_espacos(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip() if value is not None else ""


def _registrar_alteracao(
    eventos: list[dict[str, Any]],
    campo: str,
    antes: Any,
    depois: Any,
    tipo: str,
) -> None:
    if antes != depois:
        eventos.append(
            {
                "tipo": tipo,
                "campo": campo,
                "antes": antes,
                "depois": depois,
                "motivo": "Valor normalizado conforme regras de lapidacao.",
            }
        )


def _tem_alertas(eventos: list[dict[str, Any]]) -> bool:
    return any(evento["tipo"] == "alerta" for evento in eventos)


def _tem_alerta_cidade_estado(eventos: list[dict[str, Any]]) -> bool:
    return any(
        evento["tipo"] == "alerta" and evento["campo"] == "cidade_estado"
        for evento in eventos
    )


def _configurar_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    _configurar_logging()
    resultado_final = lapidar_arquivo_cubo()
    print(resultado_final["RELATORIO_DE_LAPIDACAO"])
    print("\nJSON_LAPIDADO:")
    print(json.dumps(resultado_final["JSON_LAPIDADO"], ensure_ascii=False, indent=2))
