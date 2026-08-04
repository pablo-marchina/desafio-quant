"""
Filtro de relevancia AI-native (mineracao leve, sem custo de LLM).

Antes de gastar uma chamada de LLM (Classifier Agent, Dia 3) ou uma
requisicao extra de scraping, fazemos uma triagem rapida e barata por
palavras-chave para decidir se um texto (noticia, descricao de startup)
tem sinal suficiente de uso de IA para valer a pena aprofundar a coleta.

Isso implementa a ideia de "minerar para selecionar apenas o que e
interessante", reduzindo ruido antes das etapas mais caras do pipeline
(scraping profundo, extracao estruturada via LLM, classificacao).
"""
import re
import unicodedata

# Termos que indicam uso de IA/ML, organizados por forca de sinal.
# Termos fortes = quase certeza de relevancia (LLM, agentes, IA generativa).
# Termos medios = indicam tecnologia mas podem ser genericos demais sozinhos.
TERMOS_FORTES = [
    "inteligencia artificial",
    "artificial intelligence",
    "ia generativa",
    "generative ai",
    "llm",
    "large language model",
    "modelo de linguagem",
    "machine learning",
    "aprendizado de maquina",
    "agentes de ia",
    "agente de ia",
    "ai agent",
    "ai agents",
    "deep learning",
    "redes neurais",
    "neural networks",
    "chatgpt",
    "openai",
    "anthropic",
    "nvidia",
    "gpu",
    "rag",
    "retrieval augmented",
    "computer vision",
    "visao computacional",
    "nlp",
    "processamento de linguagem natural",
    "ai-first",
    "ai first",
    "ai-native",
    "ai native",
]

TERMOS_MEDIOS = [
    "automacao",
    "algoritmo",
    "dados em tempo real",
    "personalizacao",
    "predicao",
    "preditivo",
    "copilot",
    "assistente virtual",
    "chatbot",
    "analytics",
    "predictions",
]

PADROES_FORTES = [
    re.compile(r"\bia\b"),
    re.compile(r"\bai\b"),
]


def _normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return texto.lower()


def calcular_score_relevancia_ia(texto: str) -> dict:
    """
    Calcula um score simples de relevancia AI a partir de contagem de
    termos-chave. Nao substitui o Classifier Agent (que usara LLM no
    Dia 3) - e uma triagem barata para decidir o que vale aprofundar.

    Retorna um dict com o score, os termos encontrados e uma sugestao
    booleana de "vale aprofundar a coleta".
    """
    texto_normalizado = _normalizar_texto(texto)

    termos_fortes_encontrados = [
        termo for termo in TERMOS_FORTES if termo in texto_normalizado
    ]
    termos_medios_encontrados = [
        termo for termo in TERMOS_MEDIOS if termo in texto_normalizado
    ]

    for padrao in PADROES_FORTES:
        match = padrao.search(texto_normalizado)
        if match:
            termo = match.group(0)
            if termo not in termos_fortes_encontrados:
                termos_fortes_encontrados.append(termo)

    # Pesos: termo forte vale 3 pontos, termo medio vale 1 ponto.
    score = len(termos_fortes_encontrados) * 3 + len(termos_medios_encontrados) * 1

    # Heuristica de corte: qualquer termo forte, ou 2+ termos medios,
    # ja justifica aprofundar a coleta.
    vale_aprofundar = (
        len(termos_fortes_encontrados) >= 1
        or len(termos_medios_encontrados) >= 2
    )

    return {
        "score": score,
        "termos_fortes_encontrados": termos_fortes_encontrados,
        "termos_medios_encontrados": termos_medios_encontrados,
        "vale_aprofundar": vale_aprofundar,
    }


def extrair_trecho_relevante(texto: str, janela_chars: int = 200) -> str:
    """
    Extrai um pequeno trecho do texto em torno do primeiro termo forte
    encontrado, util para preview rapido sem precisar ler o texto todo.
    """
    texto = texto or ""
    texto_normalizado = _normalizar_texto(texto)

    for termo in TERMOS_FORTES:
        idx = texto_normalizado.find(termo)
        if idx != -1:
            inicio = max(0, idx - janela_chars // 2)
            fim = min(len(texto), idx + len(termo) + janela_chars // 2)
            return texto[inicio:fim].strip()

    for padrao in PADROES_FORTES:
        match = padrao.search(texto_normalizado)
        if match:
            inicio = max(0, match.start() - janela_chars // 2)
            fim = min(len(texto), match.end() + janela_chars // 2)
            return texto[inicio:fim].strip()

    return texto[:janela_chars].strip()
