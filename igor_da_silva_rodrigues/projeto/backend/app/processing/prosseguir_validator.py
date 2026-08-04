from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


UFS_BRASIL = {
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
}

SETORES_ALTA_SINERGIA_IA = {
    "fintech",
    "healthtech",
    "agtech",
    "edtech",
    "retailtech",
    "proptech",
    "martech",
    "hrtech",
    "legaltech",
    "insurtech",
    "cybersec",
    "climatech",
    "logtech",
    "energytech",
    "biotech",
    "deeptech",
}

TERMOS_IA = [
    "inteligencia artificial",
    "inteligência artificial",
    "machine learning",
    "aprendizado de maquina",
    "aprendizado de máquina",
    "deep learning",
    "redes neurais",
    "nlp",
    "processamento de linguagem natural",
    "visao computacional",
    "visão computacional",
    "chatbot",
    "assistente virtual",
    "algoritmo preditivo",
    "automacao inteligente",
    "automação inteligente",
    "dados inteligentes",
    "recomendacao inteligente",
    "recomendação inteligente",
    "cognitive",
    "llm",
    "gpt",
    "transformers",
    "analise preditiva",
    "análise preditiva",
    "data science avancado",
    "data science avançado",
]


def validar_flags_prosseguir(payload: Any) -> str:
    startups = _extrair_startups(payload)
    avaliacoes = [_avaliar_startup(startup) for startup in startups]
    return _montar_relatorio(avaliacoes)


def validar_arquivo_prosseguir(input_path: Path) -> str:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    return validar_flags_prosseguir(payload)


def _avaliar_startup(startup: dict[str, Any]) -> dict[str, Any]:
    integridade = _avaliar_integridade(startup)
    potencial_ia = _avaliar_potencial_ia(startup)
    esperado = integridade["ok"] and potencial_ia["ok"]
    atual = bool(startup.get("prosseguir", False))
    divergencia = None

    if atual and not esperado:
        divergencia = "falso_positivo"
    elif not atual and esperado:
        divergencia = "falso_negativo"

    return {
        "startup": startup,
        "nome": startup.get("nome") or "Nome não informado",
        "flag_atual": atual,
        "prosseguir_esperado": esperado,
        "divergencia": divergencia,
        "integridade": integridade,
        "potencial_ia": potencial_ia,
        "potencial_nao_confirmado": (
            integridade["ok"] and potencial_ia["categoria_sinergica"] and not potencial_ia["descricao_menciona_ia"]
        ),
    }


def _avaliar_integridade(startup: dict[str, Any]) -> dict[str, Any]:
    falhas = []
    site = startup.get("site")
    estado = _clean(startup.get("estado")).upper()
    pais = _clean(startup.get("pais"))

    if not _url_valida(site):
        falhas.append("site ausente ou URL inválida")
    if not _clean(startup.get("cidade")):
        falhas.append("cidade ausente")
    if not estado or estado not in UFS_BRASIL:
        falhas.append("estado ausente ou fora da lista de UFs brasileiras")
    if pais != "Brasil":
        falhas.append('país diferente de "Brasil"')
    if not _clean(startup.get("categoria")):
        falhas.append("categoria ausente")
    if startup.get("qualidade", {}).get("incompleto") is True:
        falhas.append("qualidade.incompleto está true")

    return {"ok": not falhas, "falhas": falhas}


def _avaliar_potencial_ia(startup: dict[str, Any]) -> dict[str, Any]:
    categoria = _clean(startup.get("categoria"))
    descricao = _clean(startup.get("descricao_curta"))
    categoria_sinergica = _categoria_tem_sinergia(categoria)
    termos = _termos_ia_encontrados(descricao)
    descricao_menciona_ia = bool(termos)

    ok = descricao_menciona_ia
    if categoria_sinergica and descricao_menciona_ia:
        ok = True
    elif categoria_sinergica and not descricao_menciona_ia:
        ok = False
    elif descricao_menciona_ia and not categoria_sinergica:
        ok = True

    return {
        "ok": ok,
        "categoria": categoria,
        "categoria_sinergica": categoria_sinergica,
        "descricao_menciona_ia": descricao_menciona_ia,
        "termos_encontrados": termos,
        "trecho_evidencia": _trecho_evidencia(descricao, termos),
    }


def _montar_relatorio(avaliacoes: list[dict[str, Any]]) -> str:
    total = len(avaliacoes)
    falsos_positivos = [a for a in avaliacoes if a["divergencia"] == "falso_positivo"]
    falsos_negativos = [a for a in avaliacoes if a["divergencia"] == "falso_negativo"]
    nao_confirmados = [a for a in avaliacoes if a["potencial_nao_confirmado"]]
    flags_corretas = total - len(falsos_positivos) - len(falsos_negativos)
    taxa = (flags_corretas / total * 100) if total else 0.0

    linhas = [
        'RELATÓRIO DE VALIDAÇÃO DA FLAG "PROSSEGUIR" (COM CRITÉRIO DE IA)',
        "=================================================================",
        f"Total de startups: {total}",
        f"Flags corretas: {flags_corretas}",
        f"Erros: {len(falsos_positivos) + len(falsos_negativos)} (Falsos positivos: {len(falsos_positivos)}, Falsos negativos: {len(falsos_negativos)})",
        f"Potencial de IA não confirmado (requer revisão): {len(nao_confirmados)}",
        f"Taxa de acerto: {taxa:.2f}%",
        "",
        "ALERTAS:",
    ]

    divergencias = falsos_positivos + falsos_negativos
    if not divergencias:
        linhas.append("Nenhum alerta.")
    else:
        for index, avaliacao in enumerate(divergencias, start=1):
            linhas.extend(_linhas_alerta(index, avaliacao))

    linhas.append("")
    linhas.append("STARTUPS COM POTENCIAL DE IA NÃO CONFIRMADO:")
    if not nao_confirmados:
        linhas.append("Nenhuma startup nesta condição.")
    else:
        for avaliacao in nao_confirmados:
            linhas.append(
                f"- {avaliacao['nome']}: categoria '{avaliacao['potencial_ia']['categoria']}' é de alta sinergia, mas a descrição não contém menção inequívoca a IA."
            )

    linhas.append("")
    linhas.append("RECOMENDAÇÃO:")
    if taxa < 90 or nao_confirmados:
        linhas.append("- Recomenda-se auditoria manual antes de prosseguir.")
    else:
        linhas.append("- Alta confiabilidade. Pode-se prosseguir com as flags validadas.")

    return "\n".join(linhas)


def _linhas_alerta(index: int, avaliacao: dict[str, Any]) -> list[str]:
    integridade = avaliacao["integridade"]
    potencial = avaliacao["potencial_ia"]
    motivos = []
    if integridade["falhas"]:
        motivos.append("Falhas de integridade: " + "; ".join(integridade["falhas"]))
    if not potencial["ok"]:
        motivos.append(
            "Potencial de IA não confirmado pela descrição e/ou categoria."
        )
    if potencial["ok"] and not potencial["categoria_sinergica"]:
        motivos.append(
            "Descrição menciona IA, mas categoria não está na lista orientativa de alta sinergia."
        )

    evidencia = potencial["trecho_evidencia"] or "sem trecho explícito encontrado"
    return [
        "",
        f"{index}. Startup: {avaliacao['nome']}",
        f"   Flag atual: {str(avaliacao['flag_atual']).lower()}",
        f"   Esperado: {str(avaliacao['prosseguir_esperado']).lower()}",
        f"   Tipo de erro: {avaliacao['divergencia']}",
        f"   Motivo: {' '.join(motivos)}",
        f"   Evidência de IA: \"{evidencia}\" / Categoria: {potencial['categoria'] or 'não informada'}",
    ]


def _extrair_startups(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("startups"), list):
            return payload["startups"]
        json_lapidado = payload.get("JSON_LAPIDADO")
        if isinstance(json_lapidado, dict) and isinstance(json_lapidado.get("startups"), list):
            return json_lapidado["startups"]
    return []


def _url_valida(value: Any) -> bool:
    texto = _clean(value)
    if not texto:
        return False
    parsed = urlparse(texto)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _categoria_tem_sinergia(categoria: str) -> bool:
    normalizada = _normalizar_categoria(categoria)
    return any(setor in normalizada for setor in SETORES_ALTA_SINERGIA_IA)


def _termos_ia_encontrados(descricao: str) -> list[str]:
    normalizada = descricao.lower()
    encontrados = []
    for termo in TERMOS_IA:
        pattern = rf"(?<!\w){re.escape(termo.lower())}(?!\w)"
        if re.search(pattern, normalizada):
            encontrados.append(termo)
    if re.search(r"(?<!\w)ia(?!\w)", normalizada):
        encontrados.append("IA")
    return sorted(set(encontrados))


def _trecho_evidencia(descricao: str, termos: list[str]) -> str | None:
    if not descricao or not termos:
        return None
    lower = descricao.lower()
    for termo in termos:
        pos = lower.find(termo.lower())
        if pos >= 0:
            start = max(0, pos - 60)
            end = min(len(descricao), pos + len(termo) + 60)
            return descricao[start:end].strip()
    return None


def _normalizar_categoria(categoria: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", categoria.lower())


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()
