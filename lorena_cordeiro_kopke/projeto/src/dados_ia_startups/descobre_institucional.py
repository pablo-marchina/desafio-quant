from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client

_PLAYWRIGHT_MIN_CHARS = 200
_CLOUDFLARE_MARKERS = ["ray id:", "performing security verification", "just a moment", "cloudflare"]
_TEMPO_MAX_POR_DOMINIO = 90  # segundos — limite total de análise por domínio


def _chromium_executable() -> str | None:
    """Retorna o caminho do executável Chromium disponível.

    Preferência: chrome-headless-shell.exe (mais leve).
    Fallback: chrome.exe (Chromium completo) — usado quando o headless shell
    é removido por antivírus.
    """
    import os
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    headless = next(base.glob("chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe"), None)
    if headless and headless.exists():
        return str(headless)
    full = next(base.glob("chromium-*/chrome-win64/chrome.exe"), None)
    if full and full.exists():
        return str(full)
    return None

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Paths tentados em ordem de prioridade — para na primeira evidência forte
_PATHS = [
    "/",
    "/produto", "/product", "/platform", "/plataforma", "/solucao", "/solution",
    "/sobre", "/about", "/about-us", "/quem-somos",
    "/tecnologia", "/technology", "/tech", "/como-funciona", "/how-it-works",
    "/cases", "/clientes", "/customers", "/recursos", "/features",
    "/blog",
    # Paths adicionais para sites que escondem conteúdo em páginas internas
    "/empresa", "/nossa-empresa", "/our-company",
    "/servicos", "/services", "/solucoes", "/solutions",
    "/produtos", "/products",
    "/inteligencia-artificial", "/ia", "/ai",
    "/inovacao", "/innovation",
    "/logistica", "/logistic",  # para Loggi
    "/saude", "/health", "/medical",  # para NeuralMed
]

# Sinais fortes: tecnologia específica — peso alto
_SINAIS_FORTES = [
    # Frameworks e bibliotecas
    "tensorflow", "pytorch", "keras", "scikit-learn", "xgboost", "lightgbm",
    "hugging face", "transformers", "langchain", "llamaindex", "openai",
    "anthropic", "gpt", "claude", "gemini", "llama", "mistral",
    # Infraestrutura de ML
    "vertex ai", "sagemaker", "azure ml", "azure machine learning",
    "databricks", "mlflow", "kubeflow", "airflow", "prefect", "metaflow",
    "weights & biases", "wandb", "dvc", "bentoml", "seldon", "triton",
    # Conceitos técnicos de ML
    "embeddings", "fine-tuning", "finetuning", "feature store",
    "retrieval augmented", "retrieval-augmented", "vector database", "banco vetorial",
    "modelo treinado", "trained model", "treinamento do modelo",
    "rede neural", "neural network", "transformer", "attention mechanism",
    "gradient descent", "backpropagation", "overfitting", "underfitting",
    "hiperparâmetro", "hyperparameter", "epoch", "batch size",
    "inferência", "inference", "serving de modelo", "model serving",
    "mlops", "llmops", "reinforcement learning", "aprendizado por reforço",
    "generative ai", "ia generativa", "genai", "foundation model",
    "large language model", "llm", "slm", "multimodal",
    # Dados e engenharia
    "data lake", "data lakehouse", "data warehouse", "data mesh",
    "feature engineering", "engenharia de features",
    "etl", "elt", "dbt", "spark", "flink", "kafka", "dask",
    "pipeline de machine learning", "ml pipeline",
    "data catalog", "catálogo de dados", "data lineage",
    "data quality", "qualidade de dados", "observabilidade de dados",
    # Casos de uso técnicos
    "processamento de linguagem natural", "natural language processing",
    "visão computacional", "computer vision", "reconhecimento de imagem",
    "image recognition", "object detection", "detecção de objetos",
    "speech recognition", "reconhecimento de voz", "text to speech",
    "sentiment analysis", "análise de sentimento",
    "fraud detection", "detecção de fraude", "anomaly detection",
    "detecção de anomalia", "recommendation engine", "motor de recomendação",
    "sistemas de recomendação", "churn prediction", "previsão de churn",
    "demand forecasting", "previsão de demanda", "credit scoring",
    "precificação dinâmica", "dynamic pricing",
]

# Sinais fracos: termos genéricos — podem ser marketing
_SINAIS_FRACOS = [
    # Termos amplos PT
    "inteligência artificial", "machine learning", "aprendizado de máquina",
    "deep learning", "ciência de dados", "mineração de dados",
    "automação inteligente", "hiperautomação", "hyperautomation",
    "processamento inteligente", "decisão baseada em dados",
    "data driven", "orientado a dados", "cultura de dados",
    "preditivo", "prescritivo", "cognitivo",
    "scoring", "propensão", "segmentação", "clusterização",
    "previsão", "forecast", "insights automáticos",
    # Termos amplos EN
    "artificial intelligence", "data science", "data-driven",
    "predictive analytics", "prescriptive analytics",
    "business intelligence", "augmented analytics",
    "intelligent automation", "smart automation",
    # Infraestrutura genérica
    "big data", "relatório automatizado", "automated report",
    "api de dados", "data api",
    # Abreviações
    " ia ", " ai ", " ml ", " nlp ", " cv ",
    "rpa", "bpm",
]


# Blocklist: se o termo aparecer junto com qualquer uma dessas frases → descarta
_BLOCKLIST: dict[str, list[str]] = {
    "analytics":      ["google analytics", "meta pixel", "cookie", "preferências de cookie",
                       "pixel de rastreamento", "gtag", "facebook pixel"],
    "modelos":        ["modelos de negócio", "modelo comercial", "novos modelos de",
                       "novos modelos.", "novos modelos,", "novos modelos ",
                       "modelo de gestão", "modelos de atendimento", "modelo de franquia"],
    "treinamento":    ["treinamento de equipe", "treinamento de clientes", "academy",
                       "treinamento para", "curso", "capacitação", "onboarding"],
    "pipeline":       ["pipeline de vendas", "pipeline comercial", "pipeline de leads",
                       "funil de vendas"],
    "personalização": ["personalização de cookies", "personalização de comunicação",
                       "personalização de e-mail", "preferências de personalização"],
    "otimização":     ["otimização de campanhas", "otimização de anúncios",
                       "otimização de seo", "otimização de conversão"],
    "previsão":       ["previsão do tempo", "previsão climática"],
    "recomendação":   ["carta de recomendação", "recomendação de uso"],
    # Headline é VC — ter empresa de IA no portfólio não é usar IA
    "mistral":        ["mistral ai", "portfólio", "portfolio", "invested", "investimento"],
    " ai ":           ["portfólio", "portfolio", "invested", "investimento",
                       "mistral ai", "openai", "anthropic"],
    # Kavak — cores e filiais de carros
    "silver":         ["vermelho", "azul", "preto", "branco", "filiais", "arena"],
}

# Pontuação mínima para marcar encontrado=true
_PESO_FORTE = 3
_PESO_FRACO = 1
_THRESHOLD = 4


def _termo_bloqueado(termo: str, trecho: str) -> bool:
    frases_proibidas = _BLOCKLIST.get(termo, [])
    trecho_lower = trecho.lower()
    return any(f in trecho_lower for f in frases_proibidas)


def _extrair_texto(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def _trecho(texto: str, termo: str, janela: int = 200) -> str:
    idx = texto.lower().find(termo.lower())
    if idx == -1:
        return ""
    inicio = max(0, idx - janela // 2)
    fim = min(len(texto), idx + len(termo) + janela // 2)
    return "..." + texto[inicio:fim].strip() + "..."


def _buscar_pagina_playwright(url: str, pw_page, debug: bool = False) -> str | None:
    try:
        pw_page.goto(url, timeout=12000, wait_until="domcontentloaded")
        time.sleep(1.5)
        html = pw_page.content()
        if debug:
            print(f"      [playwright] {url} → {len(html)} chars")
        return html
    except Exception as e:
        if debug:
            print(f"      [playwright] erro em {url}: {e}")
        return None


def _buscar_pagina_requests(url: str, debug: bool = False, tentativas: int = 3) -> str | None:
    for tentativa in range(1, tentativas + 1):
        try:
            r = _SESSION.get(url, timeout=12, allow_redirects=True)
            if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
                r.encoding = r.apparent_encoding
                return r.text
            if debug:
                print(f"      [debug] {url} → status={r.status_code} (tentativa {tentativa})")
            return None
        except requests.RequestException as e:
            if debug:
                print(f"      [debug] {url} → erro (tentativa {tentativa}): {e}")
            if tentativa < tentativas:
                time.sleep(2 * tentativa)

    if url.startswith("https://"):
        url_http = url.replace("https://", "http://", 1)
        if debug:
            print(f"      [debug] fallback http: {url_http}")
        try:
            r = _SESSION.get(url_http, timeout=12, allow_redirects=True)
            if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
                r.encoding = r.apparent_encoding
                return r.text
        except requests.RequestException:
            pass

    return None


def _buscar_pagina(url: str, debug: bool = False, tentativas: int = 3, pw_page=None) -> str | None:
    html = _buscar_pagina_requests(url, debug=debug, tentativas=tentativas)

    if html is None:
        return None

    if pw_page is not None and len(_extrair_texto(html)) < _PLAYWRIGHT_MIN_CHARS:
        if debug:
            print(f"      [debug] texto curto → tentando Playwright para {url}")
        html_pw = _buscar_pagina_playwright(url, pw_page, debug=debug)
        if html_pw:
            return html_pw

    return html


def _pontuar_pagina(texto: str, debug: bool = False) -> tuple[int, str, str, str]:
    """
    Percorre todos os sinais da página acumulando pontuação.
    Retorna (pontuação_total, melhor_termo, melhor_trecho, tipo_sinal).
    O melhor termo é o de maior peso não bloqueado encontrado.
    """
    pontuacao = 0
    melhor_termo = ""
    melhor_trecho = ""
    melhor_tipo = ""
    texto_lower = texto.lower()

    for termo in _SINAIS_FORTES:
        if termo in texto_lower:
            trecho = _trecho(texto, termo)
            if _termo_bloqueado(termo, trecho):
                if debug:
                    print(f"        [blocklist] '{termo}' bloqueado")
                continue
            pontuacao += _PESO_FORTE
            if not melhor_termo:
                melhor_termo, melhor_trecho, melhor_tipo = termo, trecho, "forte"
            if debug:
                print(f"        [+{_PESO_FORTE}] forte: '{termo}'  total={pontuacao}")

    for termo in _SINAIS_FRACOS:
        if termo in texto_lower:
            trecho = _trecho(texto, termo)
            if _termo_bloqueado(termo, trecho):
                if debug:
                    print(f"        [blocklist] '{termo}' bloqueado")
                continue
            pontuacao += _PESO_FRACO
            if not melhor_termo:
                melhor_termo, melhor_trecho, melhor_tipo = termo, trecho, "fraco"
            if debug:
                print(f"        [+{_PESO_FRACO}] fraco: '{termo}'  total={pontuacao}")

    return pontuacao, melhor_termo, melhor_trecho, melhor_tipo


def _eh_cloudflare(texto: str) -> bool:
    texto_lower = texto.lower()
    return sum(1 for m in _CLOUDFLARE_MARKERS if m in texto_lower) >= 2


def _eh_js_heavy(dominio: str, debug: bool = False) -> bool:
    html = _buscar_pagina_requests(f"https://{dominio}/", debug=debug, tentativas=1)
    if not html:
        return False
    return len(_extrair_texto(html)) < _PLAYWRIGHT_MIN_CHARS


def _analisar_loop(dominio: str, debug: bool, max_falhas_consecutivas: int, pw_page) -> dict | None:
    pontuacao_total = 0
    melhor: tuple[str, str, str, str] = ("", "", "", "")
    falhas_consecutivas = 0
    inicio = time.time()

    for path in _PATHS:
        elapsed = time.time() - inicio
        if elapsed >= _TEMPO_MAX_POR_DOMINIO:
            if debug:
                print(f"      [timeout] {dominio} — limite de {_TEMPO_MAX_POR_DOMINIO}s atingido ({elapsed:.0f}s)")
            break

        url = f"https://{dominio}{path}"
        html = _buscar_pagina(url, debug=debug, pw_page=pw_page)
        if not html:
            falhas_consecutivas += 1
            if falhas_consecutivas >= max_falhas_consecutivas:
                if debug:
                    print(f"      [debug] {falhas_consecutivas} falhas consecutivas → abandona {dominio}")
                break
            time.sleep(0.5)
            continue

        falhas_consecutivas = 0
        texto = _extrair_texto(html)
        pontos, termo, trecho, tipo = _pontuar_pagina(texto, debug=debug)

        if debug and pontos > 0:
            print(f"      [debug] {url} → +{pontos} ponto(s)")

        pontuacao_total += pontos
        if termo and not melhor[1]:
            melhor = (url, termo, trecho, tipo)

        if pontuacao_total >= _THRESHOLD:
            break

        time.sleep(1)

    if pontuacao_total >= _THRESHOLD and melhor[1]:
        if debug:
            print(f"      [debug] pontuação final={pontuacao_total} ≥ {_THRESHOLD} → POSITIVO")
        return {
            "fonte_url": melhor[0],
            "termo": melhor[1],
            "evidencia": melhor[2],
            "tipo_sinal": melhor[3],
            "pontuacao": pontuacao_total,
        }

    if debug:
        print(f"      [debug] pontuação final={pontuacao_total} < {_THRESHOLD} → negativo")
    return None


_CLOUDFLARE = {"cloudflare": True}


def _analisar(dominio: str, debug: bool = False, max_falhas_consecutivas: int = 10) -> dict | None:
    html_home = _buscar_pagina_requests(f"https://{dominio}/", debug=debug, tentativas=1)
    texto_home = _extrair_texto(html_home) if html_home else ""

    if _eh_cloudflare(texto_home):
        if debug:
            print(f"      [cloudflare] {dominio} bloqueado pelo Cloudflare → revisão manual")
        return _CLOUDFLARE

    if len(texto_home) >= _PLAYWRIGHT_MIN_CHARS:
        return _analisar_loop(dominio, debug, max_falhas_consecutivas, pw_page=None)

    if debug:
        print(f"      [playwright] site JS detectado, abrindo browser para {dominio}")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=_chromium_executable())
        pw_page = browser.new_page()

        # Verifica Cloudflare na homepage renderizada
        html_pw = _buscar_pagina_playwright(f"https://{dominio}/", pw_page, debug=debug)
        if html_pw and _eh_cloudflare(_extrair_texto(html_pw)):
            browser.close()
            if debug:
                print(f"      [cloudflare] {dominio} bloqueado pelo Cloudflare → revisão manual")
            return _CLOUDFLARE

        resultado = _analisar_loop(dominio, debug, max_falhas_consecutivas, pw_page=pw_page)
        browser.close()
    return resultado


_SAIDA = _RAIZ / "data" / "jsons" / "institucional"


def pesquisar(debug: bool = False, nome: str | None = None) -> None:
    query = supabase.table("empresas").select("id, nome, dominio, revisao_manual").not_.is_("dominio", "null")
    if nome:
        query = query.eq("nome", nome)
    rows = query.execute().data
    empresas = [r for r in rows if r.get("dominio")]
    print(f"[info] {len(empresas)} empresa(s) com dominio no Supabase\n")

    def _ja_checado(empresa_id: int, revisao_manual: bool) -> bool:
        if revisao_manual:
            return True
        res = supabase.table("sinais_ia").select("id").eq("empresa_id", empresa_id).eq("camada", "institucional").limit(1).execute()
        return len(res.data) > 0

    todos_registros: list[dict] = []

    for empresa in empresas:
        empresa_id = empresa["id"]
        nome = empresa["nome"]
        dominio = empresa["dominio"]

        print(f"[→] {nome}  ({dominio})")

        revisao_manual = empresa.get("revisao_manual", False)
        if _ja_checado(empresa_id, revisao_manual):
            motivo = "revisão manual pendente" if revisao_manual else "já checado anteriormente"
            print(f"    [skip] {motivo}")
            continue

        resultado = _analisar(dominio, debug=debug)

        if resultado is _CLOUDFLARE:
            supabase.table("empresas").update({"revisao_manual": True}).eq("id", empresa_id).execute()
            print(f"    [⚠] Cloudflare detectado — marcado para revisão manual")
            continue

        if resultado:
            supabase.table("sinais_ia").insert({
                "empresa_id": empresa_id,
                "camada": "institucional",
                "encontrado": True,
                "evidencia": resultado["evidencia"],
                "fonte_url": resultado["fonte_url"],
            }).execute()
            print(f"    [✓] sinal {resultado['tipo_sinal']}: '{resultado['termo']}' (pontuação={resultado['pontuacao']}) em {resultado['fonte_url']}")
            todos_registros.append({
                "empresa_id": empresa_id,
                "nome_empresa": nome,
                "dominio": dominio,
                "encontrado": True,
                **resultado,
                "coletado_em": datetime.now(timezone.utc).isoformat(),
            })
        else:
            supabase.table("sinais_ia").insert({
                "empresa_id": empresa_id,
                "camada": "institucional",
                "encontrado": False,
                "evidencia": None,
                "fonte_url": f"https://{dominio}",
            }).execute()
            print(f"    [✗] nenhum sinal encontrado")
            todos_registros.append({
                "empresa_id": empresa_id,
                "nome_empresa": nome,
                "dominio": dominio,
                "encontrado": False,
                "fonte_url": f"https://{dominio}",
                "termo": None,
                "evidencia": None,
                "tipo_sinal": None,
                "coletado_em": datetime.now(timezone.utc).isoformat(),
            })

        time.sleep(1)

    _SAIDA.mkdir(parents=True, exist_ok=True)
    caminho = _SAIDA / "institucional.json"
    existentes: list[dict] = []
    if caminho.exists():
        existentes = json.loads(caminho.read_text(encoding="utf-8"))
    ids_existentes = {r["empresa_id"] for r in existentes}
    novos = [r for r in todos_registros if r["empresa_id"] not in ids_existentes]
    caminho.write_text(
        json.dumps(existentes + novos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[json] {len(novos)} registro(s) salvo(s) em {caminho}")

    positivos = sum(1 for r in todos_registros if r["encontrado"])
    print(f"[resumo] {positivos}/{len(empresas)} empresa(s) com sinal institucional de IA")


if __name__ == "__main__":
    import sys
    debug = "--debug" in sys.argv
    pesquisar(debug=debug)
