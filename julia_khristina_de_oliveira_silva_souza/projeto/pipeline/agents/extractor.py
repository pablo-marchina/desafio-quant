import json
import os
import time
from urllib.parse import urlparse
import cohere
from dotenv import load_dotenv
from pipeline.config.settings import COHERE_CHAT_MODEL
from pipeline.db.connection import fetch_one, execute_query
from pipeline.utils.validation import validar_email, normalizar_email_extraido

load_dotenv()

co_chat = cohere.ClientV2(os.environ["COHERE_API_KEY"])

PROMPT_EXTRACAO = """Você é um extrator de dados estruturados de startups brasileiras.

Extraia os campos abaixo do texto fornecido. Responda APENAS com JSON válido, sem preamble, sem markdown, sem explicações.

Schema esperado:
{
  "nome": "nome da startup ou null",
  "website": "url do site ou null",
  "setor": "setor de atuação ou null",
  "descricao": "descrição curta do que a startup faz ou null",
  "produto_principal": "principal produto/serviço ou null",
  "tecnologias_mencionadas": ["lista de tecnologias mencionadas"] ou [] se não houver,
  "cidade": "cidade ou null",
  "email_contato": "email de contato encontrado no texto ou null",
  "estagio": "early/traction/growth/mature ou null"
}

REGRAS:
- NUNCA invente dados. Se não conseguir extrair, retorne null.
- NÃO repita informações.
- Se o texto não for sobre uma startup, retorne {"nome": null, "website": null, ...}

Exemplo 1:
Texto: "A HealthTech AI é uma startup de São Paulo que usa machine learning para diagnosticar exames de imagem. Fundada em 2021, contato@healthtech.ai, já tem 50 clientes."
Resposta: {"nome": "HealthTech AI", "website": null, "setor": "saúde", "descricao": "usa machine learning para diagnosticar exames de imagem", "produto_principal": "diagnóstico de exames de imagem com ML", "tecnologias_mencionadas": ["machine learning"], "cidade": "São Paulo", "email_contato": "contato@healthtech.ai", "estagio": "traction"}

Exemplo 2:
Texto: "Este é um artigo sobre tendências de mercado em 2024."
Resposta: {"nome": null, "website": null, "setor": null, "descricao": null, "produto_principal": null, "tecnologias_mencionadas": [], "cidade": null, "email_contato": null, "estagio": null}

Texto para extrair:
{texto}
"""


def _chat_com_retry(prompt: str, tentativas: int = 3, espera_base: int = 5) -> str:
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = co_chat.chat(
                model=COHERE_CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000
            )
            return resposta.message.content[0].text
        except Exception as e:
            if tentativa == tentativas:
                raise
            espera = espera_base * (2 ** (tentativa - 1))
            print(f"[Extractor] erro na tentativa {tentativa}/{tentativas}: {e}. Tentando novamente em {espera}s...")
            time.sleep(espera)


def _extrair_json(texto: str) -> dict | None:
    prompt = PROMPT_EXTRACAO.replace("{texto}", texto[:3000])
    for _ in range(2):
        try:
            resposta = _chat_com_retry(prompt)
            texto_limpo = resposta.strip()
            if texto_limpo.startswith("```"):
                texto_limpo = texto_limpo.split("\n", 1)[1]
            if texto_limpo.endswith("```"):
                texto_limpo = texto_limpo.rsplit("\n", 1)[0]
            return json.loads(texto_limpo.strip())
        except (json.JSONDecodeError, Exception):
            continue
    return None


def _normalizar_valor(valor) -> str | None:
    if isinstance(valor, list):
        return ", ".join(str(v) for v in valor)
    if isinstance(valor, str):
        return valor
    return str(valor) if valor is not None else None


_MAP_SETORES = {
    "fintech": ["fintech", "finanças", "financeiro", "bancário", "banco", "bancos", "pagamentos",
                 "pagamento", "criptomoedas", "criptomoeda", "blockchain", "investimento",
                 "investimentos", "crédito", "crédito digital", "dinheiro", "financial", "banking"],
    "healthtech": ["healthtech", "saúde", "saude", "médico", "medicina", "hospital", "diagnóstico",
                   "diagnóstico por imagem", "telemedicina", "bioinformática", "genômica",
                   "genetica", "farmacêutico", "clinical", "patient", "healthcare"],
    "agritech": ["agritech", "agtech", "agro", "agricultura", "agricola", "agrícola",
                 "agricultura de precisão", "agronegócio", "agronegocio", "foodtech",
                 "fazenda", "fazendas", "lavoura", "pecuária", "irrigação",
                 "agricultura, conservação", "agricultura, tecnologia"],
    "edtech": ["edtech", "educação", "educação digital", "ensino", "aprendizado",
               "escola", "cursos", "learning", "educational", "plataforma de ensino"],
    "legaltech": ["legaltech", "jurídico", "juridico", "advocacia", "direito", "contratos",
                  "compliance", "legal", "jurimetria", "cartório"],
    "retailtech": ["retailtech", "varejo", "e-commerce", "ecommerce", "loja", "vendas",
                   "retail", "omnichannel", "comércio", "comercio"],
    "industria4": ["indústria 4.0", "industria 4.0", "manufatura", "industria", "indústria",
                   "fábrica", "fabrica", "automação industrial", "iiot", "chão de fábrica"],
    "logistica": ["logística", "logistica", "logistics", "supply chain", "entregas", "entrega",
                  "frota", "fretes", "transporte", "armazém", "armazem", "last mile"],
    "cybersecurity": ["cybersecurity", "cibersegurança", "ciberseguranca", "segurança digital",
                      "segurança cibernética", "threat detection", "proteção de dados",
                      "segurança cloud", "antivirus"],
    "energia": ["energia", "clean tech", "renovável", "renováveis", "solar", "eólica",
                "smart grid", "carbono", "eficiência energética", "sustentabilidade",
                "energia limpa", "green tech"],
    "midia": ["mídia", "midia", "entretenimento", "streaming", "games", "game",
              "realidade virtual", "realidade aumentada", "metaverso", "conteúdo",
              "media", "entertainment", "vídeo", "video"],
    "proptech": ["proptech", "imobiliário", "imobiliario", "construção", "construcao",
                 "smart building", "corretagem", "condomínio", "condominio", "bim",
                 "imóveis", "imoveis"],
}


def _normalizar_setor(setor: str | None) -> str | None:
    if not setor:
        return setor
    setor_lower = setor.lower().strip()
    for setor_id, variacoes in _MAP_SETORES.items():
        for variacao in variacoes:
            if variacao in setor_lower or setor_lower in variacao:
                return setor_id
    return setor


def _upsert_startup(dados: dict, url: str, fonte_origem: str) -> str | None:
    if not dados.get("nome"):
        return None

    nome = _normalizar_valor(dados.get("nome"))
    setor = _normalizar_setor(_normalizar_valor(dados.get("setor")))
    descricao = _normalizar_valor(dados.get("descricao"))
    produto = _normalizar_valor(dados.get("produto_principal"))
    cidade = _normalizar_valor(dados.get("cidade"))
    estagio = _normalizar_valor(dados.get("estagio"))
    email_raw = dados.get("email_contato")
    email = normalizar_email_extraido(email_raw) if email_raw else None
    site_llm = _normalizar_valor(dados.get("website"))
    website_final = site_llm if site_llm and urlparse(site_llm).netloc else url

    existente = fetch_one("SELECT id, email_contato, website FROM startups WHERE website = ?", (website_final,))
    if not existente and nome:
        existente = fetch_one("SELECT id, email_contato, website FROM startups WHERE nome = ?", (nome,))
    if existente:
        existing_website = existente.get("website", "")
        email_final = email or existente.get("email_contato")
        execute_query(
            """UPDATE startups SET
                nome = COALESCE(?, nome),
                setor = COALESCE(?, setor),
                descricao = COALESCE(?, descricao),
                produto_principal = COALESCE(?, produto_principal),
                cidade = COALESCE(?, cidade),
                estagio = COALESCE(?, estagio),
                email_contato = COALESCE(?, email_contato),
                website = CASE WHEN ? <> ? AND ? IS NOT NULL AND ? <> '' THEN ? ELSE website END,
                tecnologias_detectadas = COALESCE(?, tecnologias_detectadas),
                updated_at = datetime('now')
            WHERE id = ?""",
            (
                nome, setor, descricao,
                produto, cidade,
                estagio, email_final,
                site_llm, existing_website, site_llm, site_llm, site_llm,
                json.dumps(dados.get("tecnologias_mencionadas", [])),
                existente["id"]
            )
        )
        startup_id = existente["id"]
    else:
        import uuid
        sid = str(uuid.uuid4())
        execute_query(
            """INSERT INTO startups (id, nome, website, setor, descricao, produto_principal, cidade, estagio, email_contato, tecnologias_detectadas, fontes_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sid, nome, website_final, setor, descricao,
                produto, cidade,
                estagio, email,
                json.dumps(dados.get("tecnologias_mencionadas", [])),
                json.dumps([fonte_origem])
            )
        )
        startup_id = sid

    return startup_id


def _salvar_evidencia(startup_id: str, url: str, conteudo_raw: str, fonte_origem: str):
    execute_query(
        """INSERT INTO evidencias (startup_id, tipo, url, conteudo_bruto, score_qualidade)
        VALUES (?, ?, ?, ?, ?)""",
        (startup_id, "website" if fonte_origem == url else "diretorio_br", url, conteudo_raw[:5000], 0.5)
    )


def run_extractor(resultados_scraper: list[dict]) -> list[dict]:
    import trafilatura
    startups_extraidas = []

    for item in resultados_scraper:
        print(f"[Extractor] Processando: {item['url']}")
        dados = _extrair_json(item["conteudo_raw"])
        if not dados or not dados.get("nome"):
            print(f"[Extractor] Falha ao extrair dados de {item['url']}")
            continue

        site_llm = _normalizar_valor(dados.get("website"))
        website_final = site_llm if site_llm and urlparse(site_llm).netloc else item["url"]

        if site_llm and urlparse(site_llm).netloc and site_llm != item["url"]:
            try:
                extra = trafilatura.extract(trafilatura.fetch_url(site_llm))
                if extra and len(extra) > 200:
                    dados2 = _extrair_json(extra)
                    if dados2 and dados2.get("nome"):
                        for campo in ["descricao", "produto_principal", "cidade", "email_contato", "estagio"]:
                            if dados2.get(campo) and not dados.get(campo):
                                dados[campo] = dados2[campo]
                        if dados2.get("tecnologias_mencionadas"):
                            existentes = set(dados.get("tecnologias_mencionadas", []))
                            novas = [t for t in dados2["tecnologias_mencionadas"] if t not in existentes]
                            dados["tecnologias_mencionadas"] = dados.get("tecnologias_mencionadas", []) + novas
                        print(f"  [Extractor] Site oficial raspado: dados complementares obtidos")
                        time.sleep(1)
            except Exception:
                pass

        startup_id = _upsert_startup(dados, item["url"], item.get("fonte_origem", ""))
        if startup_id:
            _salvar_evidencia(startup_id, item["url"], item["conteudo_raw"], item.get("fonte_origem", ""))
            startups_extraidas.append({
                "id": startup_id,
                "nome": dados["nome"],
                "website": website_final,
                "setor": dados.get("setor"),
                "descricao": dados.get("descricao"),
                "produto_principal": dados.get("produto_principal"),
                "tecnologias_detectadas": dados.get("tecnologias_mencionadas", []),
                "fontes_url": [item.get("fonte_origem", "")]
            })

    print(f"[Extractor] Startups extraídas: {len(startups_extraidas)}")
    return startups_extraidas
