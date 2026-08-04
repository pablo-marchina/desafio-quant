"""Registro canônico de fontes do projeto.

Diretórios de startups e fontes de notícias. Essas listas
servem para priorizar resultados da busca web (domínios confiáveis) e
descartar fontes restritivas (LinkedIn). Não são seed por empresa — a
descoberta de URLs é feita por busca (ver app/search_planner.py).
"""

from urllib.parse import urlparse

# diretórios e aceleradoras
FONTES_DIRETORIOS = [
    "https://www.startse.com/",
    "https://distrito.me/",
    "https://www.latitud.com/",
    "https://cubo.network/",
    "https://acestartups.com.br/",
    "https://endeavor.org.br/",
    "https://abstartups.com.br/",
    "https://bossainvest.com/",
    "https://www.anjosdobrasil.net/",
    "https://www.darwinstartups.com/",
    "https://liga.ventures/",
    "https://www.wow.ac/",
    "https://www.inovativabrasil.com.br/",
    "https://www.openstartups.net/",
]

# notícias e sinais públicos
FONTES_NOTICIAS = [
    "https://braziljournal.com/",
    "https://neofeed.com.br/",
    "https://exame.com/bussola/startups/",
    "https://startups.com.br/",
    "https://revistapegn.globo.com/",
    "https://valor.globo.com/",
    "https://www.meioemensagem.com.br/",
    "https://www.mobiletime.com.br/",
]


def _dominio(url: str) -> str:
    """Extrai o domínio (sem www) de uma URL."""
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


# Domínios confiáveis (para priorizar resultados da busca)
DOMINIOS_CONFIAVEIS = {
    _dominio(u) for u in FONTES_DIRETORIOS + FONTES_NOTICIAS
}

# Base de conhecimento NVIDIA — URLs amigáveis a scraping (docs/GitHub/rapids),
# cobrindo os produtos NVIDIA. Ingeridas uma vez por app/ingest.py.
NVIDIA_DOCS = [
    {"titulo": "NVIDIA Inception", "url": "https://www.nvidia.com/en-us/startups/"},
    {"titulo": "NIM", "url": "https://github.com/NVIDIA/nim-deploy"},
    {"titulo": "NeMo", "url": "https://github.com/NVIDIA/NeMo"},
    {"titulo": "NeMo Guardrails", "url": "https://github.com/NVIDIA/NeMo-Guardrails"},
    {"titulo": "Triton Inference Server", "url": "https://github.com/triton-inference-server/server"},
    {"titulo": "TensorRT-LLM", "url": "https://github.com/NVIDIA/TensorRT-LLM"},
    {"titulo": "RAPIDS", "url": "https://github.com/rapidsai/cudf"},
    {"titulo": "cuML", "url": "https://github.com/rapidsai/cuml"},
    {"titulo": "NVIDIA Riva", "url": "https://github.com/nvidia-riva/python-clients"},
    {"titulo": "NVIDIA Isaac", "url": "https://github.com/NVIDIA-Omniverse/IsaacSim"},
    {"titulo": "NVIDIA Morpheus", "url": "https://github.com/nv-morpheus/Morpheus"},
    {"titulo": "CUDA", "url": "https://github.com/NVIDIA/cuda-samples"},
    {"titulo": "NVIDIA Omniverse", "url": "https://github.com/NVIDIA-Omniverse/kit-app-template"},
    {"titulo": "NVIDIA Clara / MONAI", "url": "https://github.com/Project-MONAI/MONAI"},
    {"titulo": "NVIDIA AI Enterprise", "url": "https://github.com/NVIDIA/GenerativeAIExamples"},
    {"titulo": "Bolo de 5 camadas da IA (NVIDIA)", "url": "https://blogs.nvidia.com/blog/ai-5-layer-cake/"},
    # materiais conceituais (AI-native services)
    {"titulo": "AI services (Sequoia)", "url": "https://www.sequoiacap.com/article/services-the-new-software/"},
    {"titulo": "AI-native services playbook (Emergence)", "url": "https://www.emcap.com/thoughts/the-ai-native-services-playbook"},
]

# Domínios a descartar (restritivos ou de baixo sinal)
DOMINIOS_BLOQUEADOS = {
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "tiktok.com",
}
