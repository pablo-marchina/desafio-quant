import json
import time
import trafilatura
from datetime import datetime, timezone
from pipeline.config.settings import MIN_EVIDENCE_SCORE
from pipeline.db.connection import fetch_one, execute_query, fetch_all


def _buscar_noticias(nome_startup: str) -> list[dict]:
    fontes_noticias = [
        "https://braziljournal.com/",
        "https://neofeed.com.br/",
        "https://exame.com/bussola/startups/",
        "https://startups.com.br/",
    ]
    evidencias = []
    for fonte_url in fontes_noticias:
        try:
            downloaded = trafilatura.fetch_url(fonte_url)
            if not downloaded:
                continue
            texto = trafilatura.extract(downloaded)
            if texto and nome_startup.lower() in texto.lower():
                evidencias.append({
                    "tipo": "noticia",
                    "url": fonte_url,
                    "titulo": f"Menção em {fonte_url}",
                    "conteudo_bruto": texto[:2000],
                    "data_publicacao": None
                })
        except Exception:
            continue
        time.sleep(1)
    return evidencias


def _buscar_blog_proprio(website: str | None) -> list[dict]:
    if not website:
        return []
    urls_blog = [
        f"{website.rstrip('/')}/blog",
        f"{website.rstrip('/')}/blog/",
    ]
    evidencias = []
    for url in urls_blog:
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                continue
            texto = trafilatura.extract(downloaded)
            if texto and len(texto) > 200:
                evidencias.append({
                    "tipo": "blog",
                    "url": url,
                    "titulo": f"Blog em {website}",
                    "conteudo_bruto": texto[:2000],
                    "data_publicacao": None
                })
        except Exception:
            continue
        time.sleep(1)
    return evidencias


def _calcular_score_recencia(data_publicacao) -> float:
    if not data_publicacao:
        return 0.5
    try:
        dias = (datetime.now(timezone.utc) - data_publicacao).days
    except Exception:
        return 0.5
    if dias < 180:
        return 1.0
    if dias < 365:
        return 0.7
    return 0.4


def _calcular_score_qualidade(evidencia: dict) -> float:
    score = _calcular_score_recencia(evidencia.get("data_publicacao"))

    tipo_scores = {"noticia": 0.8, "blog": 0.5}
    score *= tipo_scores.get(evidencia.get("tipo", ""), 0.5)

    tec_keywords = [
        "inteligência artificial", "machine learning", "deep learning",
        "gpu", "nvidia", "llm", "neural", "dados", "big data",
        "transformação digital", "cloud", "ia generativa"
    ]
    texto = evidencia.get("conteudo_bruto", "").lower()
    if any(kw in texto for kw in tec_keywords):
        score = min(score + 0.2, 1.0)

    return round(score, 2)


def run_evidence_validator(startups_classificadas: list[dict]) -> list[dict]:
    startups_validadas = []

    for startup in startups_classificadas:
        nome = startup.get("nome", "")
        website = startup.get("website", "")
        print(f"[EvidenceValidator] Buscando evidências para: {nome}")

        evidencias = _buscar_noticias(nome)
        evidencias.extend(_buscar_blog_proprio(website))

        for ev in evidencias:
            ev["score_qualidade"] = _calcular_score_qualidade(ev)

        scores = [ev["score_qualidade"] for ev in evidencias]
        media_score = sum(scores) / len(scores) if scores else 0.0
        low_confidence = media_score < MIN_EVIDENCE_SCORE

        startup_id = startup.get("startup_id")
        if startup_id:
            for ev in evidencias:
                execute_query(
                    """INSERT INTO evidencias (startup_id, tipo, url, titulo, conteudo_bruto, score_qualidade)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (startup_id, ev["tipo"], ev["url"], ev.get("titulo", ""),
                     ev.get("conteudo_bruto", ""), ev["score_qualidade"])
                )

        startups_validadas.append({
            **startup,
            "evidencias": evidencias,
            "score_medio_evidencias": round(media_score, 2),
            "low_confidence": low_confidence
        })

        time.sleep(1)

    print(f"[EvidenceValidator] {len(startups_validadas)} startups validadas")
    return startups_validadas
