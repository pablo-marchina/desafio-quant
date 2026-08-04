import json
from pathlib import Path
from urllib.parse import urlparse
import httpx
from models.startup import Startup
from config.llm import chat_json, DEFAULT_MODEL


def extract_startup(raw_json_path: str, model: str = DEFAULT_MODEL) -> Startup:
    import asyncio
    return asyncio.run(_extract(raw_json_path, model))


async def extract_startup_async(raw_json_path: str, model: str = DEFAULT_MODEL) -> Startup:
    return await _extract(raw_json_path, model)


async def _extract(raw_json_path: str, model: str) -> Startup:
    data = json.loads(Path(raw_json_path).read_text())
    blocks = []
    for p in data["pages"]:
        source_label = f"[Fonte: {p.get('url', '?')} | {p.get('source', 'http')}]"
        blocks.append(f"{source_label}\n{p['text']}")
    text = "\n\n---\n\n".join(blocks)[:14000]
    schema = Startup.model_json_schema()

    result = await chat_json(
        messages=[
            {
                "role": "system",
                "content": """Você é um analista técnico especializado em avaliar startups de IA brasileiras para o programa NVIDIA Inception.

Pergunta norteadora: Como a NVIDIA pode identificar, atrair e nutrir startups brasileiras AI-native num contexto onde grandes labs (OpenAI, Anthropic, Google) ameaçam startups dependentes apenas de wrappers de LLM?

Critérios de classificação:
- AI-native: IA é o produto principal, tem dados proprietários, modelos próprios ou pipeline de ML em produção
- AI-enabled: usa IA como feature auxiliar, produto principal não é IA
- non-AI: IA ausente ou superficial

Instruções de extração:
- tech_stack: linguagens, frameworks, ferramentas de ML/AI, infraestrutura, bancos de dados
- products: nomes dos produtos/soluções oferecidos (ex: "Plataforma de Analytics", "API de Score de Crédito")
- use_cases: casos de uso concretos (ex: "Detecção de fraude em tempo real", "Análise preditiva de churn")
- business_model: modelo de negócio (ex: "B2B SaaS", "API as a Service", "Enterprise Licensing")
- target_market: segmento de clientes alvo (ex: "Bancos e fintechs brasileiras", "Varejo de médio porte")
- funding_stage: rodada mais recente (ex: "Seed", "Series A", "Series B", "Bootstrapped")
- investors: nomes dos investidores identificados
- employee_count: número aproximado de funcionários se mencionado
- hq_location: cidade e país (ex: "São Paulo, Brasil")
- founding_year: ano de fundação (inteiro)
- github_url: URL do GitHub da organização se encontrado
- linkedin_url: URL do LinkedIn da empresa se encontrado

Extraia apenas o que está explicitamente nas fontes. Não invente dados. Retorne JSON válido.""",
            },
            {
                "role": "user",
                "content": f"""Analise as fontes abaixo (site oficial, GitHub, Crunchbase, notícias, LinkedIn) e extraia informações completas da startup.

FONTES:
{text}

Retorne JSON seguindo exatamente este schema:
{json.dumps(schema, ensure_ascii=False, indent=2)}""",
            },
        ],
        model=model,
        max_tokens=3000,
    )

    startup = Startup(**result)
    startup.logo_url = await _fetch_logo_url(startup.website, startup.name)
    return startup


_LOGO_DENYLIST = [
    "vercel.com", "vercel-storage.com", "vercel.app",
    "netlify.com", "_next/static", "nextjs.org",
]


def _is_hosting_logo(url: str) -> bool:
    return any(bad in url.lower() for bad in _LOGO_DENYLIST)


async def _fetch_logo_url(website: str | None, name: str) -> str | None:
    domain = None
    if website:
        try:
            domain = urlparse(website if "://" in website else f"https://{website}").hostname
            if domain:
                domain = domain.removeprefix("www.")
        except Exception:
            domain = None

    if not domain:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://autocomplete.clearbit.com/v1/companies/suggest",
                    params={"query": name},
                )
                results = resp.json()
                if results:
                    domain = results[0].get("domain")
        except Exception:
            domain = None

    if not domain:
        return None

    logo_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
    if _is_hosting_logo(logo_url):
        return None
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            resp = await client.get(logo_url)
            if resp.status_code != 200:
                return None
            if _is_hosting_logo(str(resp.url)):
                return None
    except Exception:
        return None

    return logo_url


if __name__ == "__main__":
    import asyncio
    result = asyncio.run(extract_startup_async("data/raw/cortex_intelligence.json"))
    print(result)
