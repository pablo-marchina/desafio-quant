from __future__ import annotations
import json
import os
import time
import logging
from pathlib import Path
import httpx
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Carrega o .env da raiz do projeto (dois níveis acima de src/agents/)
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / '.env'
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _, _v = _line.partition('=')
            os.environ.setdefault(_k.strip(), _v.strip())

_SCHEMA_EXTRACAO = {
    "type": "OBJECT",
    "properties": {
        "startup": {
            "type": "STRING",
            "nullable": True,
            "description": (
                "Nome da startup que é o sujeito principal da notícia "
                "(a empresa que recebeu investimento, foi fundada, fez a captação etc.), "
                "ou null se a notícia não tiver uma startup como sujeito."
            ),
        }
    },
    "required": ["startup"],
}

_PROMPT_TEMPLATE = """\
Dado o título de uma notícia sobre o ecossistema de startups brasileiro, \
identifique APENAS a startup que é o sujeito principal da ação descrita \
(quem captou, quem foi adquirida, quem lançou o produto etc.).

Regras:
- Retorne apenas o nome da startup, sem artigos ou complementos.
- Se o título citar um investidor, fundo, banco ou gestora como sujeito, retorne null.
- Se não houver nenhuma startup como sujeito (notícia regulatória, opinião, mercado em geral), retorne null.
- Se duas empresas aparecerem e uma for investidora da outra, retorne a que recebeu o investimento.
- Se o sujeito for uma pessoa física (não uma empresa), retorne null.
- Se o título descrever um tipo genérico de empresa sem citar um nome próprio específico (ex: "IA para dentistas", "fintech de crédito"), retorne null mesmo que investidores nomeados apareçam no título.
- Se o título tratar de múltiplas startups sem uma protagonista clara (ex: "startups entram na guerra"), retorne null.
- Se o sujeito for um fenômeno, tendência ou movimento genérico (ex: "Boom da IA", "Alta dos juros", "Crise do setor", "Corrida das fintechs"), retorne null — mesmo que apareça como sujeito gramatical da frase.

Exemplos:
Título: "Trace Finance capta mais de R$ 160 milhões em rodada Série B"
Resposta: {{"startup": "Trace Finance"}}

Título: "Andreessen Horowitz e Kaszek investem na Segura.me"
Resposta: {{"startup": "Segura.me"}}

Título: "Na crise dos CVCs, o Banco do Brasil nada contra a maré"
Resposta: {{"startup": null}}

Título: "Governo pretende reestruturar BC e CVM para 2025"
Resposta: {{"startup": null}}

Título: "Shopper fecha rodada de R$ 50 mi liderada pela Headline e XP"
Resposta: {{"startup": "Shopper"}}

Título: "Jeff Bezos prepara sua próxima grande aposta: um fundo de US$ 100 bilhões"
Resposta: {{"startup": null}}

Título: "IA para dentistas atrai Triaxis, Crescera e cofundador da Odontoprev"
Resposta: {{"startup": null}}

Título: "Andreessen Horowitz investe US$ 200 milhões na Kavak, seu maior aporte na América Latina"
Resposta: {{"startup": "Kavak"}}

Título: "Gestoras internacionais compram tese de fintech para avançar em pagamentos via stablecoins"
Resposta: {{"startup": null}}

Título: "Drones versus mísseis: startups entram na guerra para resolver equação desfavorável aos EUA"
Resposta: {{"startup": null}}

Título: "Retomada dos IPOs deve começar a fomentar indústria de venture capital"
Resposta: {{"startup": null}}

Título: "Boom da IA cria nova safra de bilionários (pelo menos no papel)"
Resposta: {{"startup": null}}

Agora analise:
Título: "{titulo}"
"""

_MODEL = "gemini-flash-lite-latest"
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 5.0  # segundos


def _get_client() -> genai.Client:
    # Singleton simples — evita recriar o client a cada chamada.
    # verify=False contorna SSL inspection de proxies corporativos no Windows.
    if not hasattr(_get_client, "_instance"):
        http = httpx.Client(verify=False)
        _get_client._instance = genai.Client(
            http_options=types.HttpOptions(httpx_client=http)
        )
    return _get_client._instance


def extrair_nome_gemini(titulo: str) -> str | None:
    """Extrai o nome da startup do título via Gemini API com JSON estruturado.

    Retorna None se não houver startup como sujeito, se a API falhar após
    retries, ou se a resposta vier malformada.
    """
    if not titulo or not titulo.strip():
        return None

    prompt = _PROMPT_TEMPLATE.format(titulo=titulo.strip().replace('"', '\\"'))
    client = _get_client()

    for tentativa in range(1, _MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_SCHEMA_EXTRACAO,
                ),
            )
            dados = json.loads(response.text)
            startup = dados.get("startup") or None
            if startup:
                startup = startup.strip()
            return startup if startup else None

        except json.JSONDecodeError:
            logger.warning("Gemini retornou JSON inválido para: %r", titulo)
            return None

        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if code == 429 and tentativa < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** (tentativa - 1))
                logger.warning(
                    "Rate limit (429). Tentativa %d/%d — aguardando %.0fs.",
                    tentativa, _MAX_RETRIES, delay,
                )
                time.sleep(delay)
                continue
            logger.error("Erro na API Gemini (tentativa %d/%d): %s", tentativa, _MAX_RETRIES, exc)
            return None

    return None
