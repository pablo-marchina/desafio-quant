import json
import re
import time
import urllib.request
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from pipeline.config.settings import SCRAPING_DELAY_SECONDS
from pipeline.db.connection import execute_query, fetch_one
from pipeline.utils.validation import (
    normalizar_cidade, validar_cidade, validar_email,
    validar_formato_email, normalizar_email_extraido
)


_PADRAO_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PADRAO_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
_PADRAO_CNPJ_LIMPO = re.compile(r"\b(\d{14})\b")
_PADRAO_CIDADE_BR = re.compile(
    r"(?:em |endereço[:.\s]*|endereco[:.\s]*|localização[:.\s]*|localizacao[:.\s]*|sede[:.\s]*)?"
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)\s*[–—-]?\s*"
    r"(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)"
)


_PADRAO_FUNCIONARIOS = re.compile(
    r"(\d+[\.\d]*(?:mil|k)?)\s*(?:funcionários|funcionarios|colaboradores|colaborador|empregados|pessoas|membros|team|employees)",
    re.IGNORECASE
)

_PADRAO_RODADA = re.compile(
    r"(?:rodada\s+(?:de\s+)?(?:investimento\s+)?|investimento\s+(?:de\s+)?|série\s+[a-zA-Z]\s*(?:de\s+)?)"
    r"(?:de\s+)?R?\$?\s*([\d.,]+\s*(?:milh[ãa]o|mil|mi|m|k|bilhão|bi)?)",
    re.IGNORECASE
)

_PADRAO_CLIENTES = re.compile(
    r"(?:mais\s+de\s+)?(\d+[\.\d]*)\s*(?:clientes|usuários|usuarios|empresas|startups|parceiros|users|companies|customers)\s*(?:em\s+\d+\s*(?:países|paises))?",
    re.IGNORECASE
)

_PADRAO_FATURAMENTO = re.compile(
    r"(?:faturamento|receita|receita\s+recorrente|arr|mrr)\s*(?:de\s+)?R?\$?\s*([\d.,]+\s*(?:milh[ãa]o|mil|mi|m|k|bilhão|bi)?)",
    re.IGNORECASE
)

_CIDADES_BR_FALLBACK = [
    "são paulo", "rio de janeiro", "belo horizonte", "brasília", "salvador",
    "fortaleza", "curitiba", "recife", "porto alegre", "manaus", "belém",
    "goiânia", "campinas", "são luís", "são gonçalo", "maceió", "duque de caxias",
    "natal", "teresina", "são bernardo do campo", "nova iguaçu",
    "joão pessoa", "santo andré", "osasco", "são josé dos campos", "ribeirão preto",
    "uberlândia", "sorocaba", "contagem", "aracaju", "feira de santana",
    "londrina", "juiz de fora", "niterói", "cuiabá",
    "joinville", "florianópolis", "vitória", "blumenau", "são josé",
    "santos", "guarulhos", "piracicaba", "jundiaí", "bauru",
    "porto velho", "macapá", "rio branco", "boa vista", "palmas",
    "campo grande", "são carlos", "são josé do rio preto", "maringá",
    "ponta grossa", "cascavel", "foz do iguaçu"
]


def _buscar_site_oficial(nome: str) -> str | None:
    queries = [
        f"site oficial {nome}",
        f"{nome} site oficial",
        f"{nome} empresa startup",
        f'"{nome}" site',
    ]
    try:
        with DDGS() as ddgs:
            for query in queries:
                for r in ddgs.text(query, max_results=5):
                    url = r.get("href", "")
                    dominio = urlparse(url).netloc.lower()
                    if any(
                        dom in dominio
                        for dom in ["facebook", "instagram", "twitter", "linkedin", "youtube",
                                    "wikipedia", "crunchbase"]
                    ):
                        continue
                    nome_slug = nome.lower().replace(" ", "").replace("-", "").replace(".", "")
                    dominio_clean = dominio.replace("www.", "").replace(".com.br", "").replace(".com", "").replace(".br", "")
                    if nome_slug in dominio_clean:
                        return url
                time.sleep(1)
            for query in queries[:2]:
                for r in ddgs.text(query, max_results=3):
                    url = r.get("href", "")
                    if any(dom in url for dom in ["facebook", "twitter", "linkedin", "wikipedia"]):
                        continue
                    if url:
                        return url
    except Exception as e:
        print(f"  [EmailFinder] Erro buscando site de {nome}: {e}")
    return None


_PAGINAS_CONTATO = [
    "contato", "contact", "fale-conosco", "faleconosco",
    "sobre", "sobre-nos", "quem-somos", "about", "about-us",
    "equipe", "team", "time",
    "mail", "email", "newsletter",
]


def _extrair_dados_pagina(url: str, profundidade: int = 1) -> tuple[set, str, BeautifulSoup | None]:
    emails = set()
    texto_completo = ""
    soup = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        texto_completo = soup.get_text(separator="\n")

        for a in soup.find_all("a", href=re.compile(r"^mailto:")):
            email = a["href"].replace("mailto:", "").split("?")[0].strip()
            if email and "@" in email:
                emails.add(email.lower())

        for match in _PADRAO_EMAIL.findall(texto_completo):
            emails.add(match.lower())

        if profundidade > 0:
            links_paginas = set()
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                if any(p in href for p in _PAGINAS_CONTATO):
                    link_url = urljoin(url, a["href"])
                    domain = urlparse(link_url).netloc
                    target_domain = urlparse(url).netloc
                    if domain == target_domain:
                        links_paginas.add(link_url)

            for link_url in links_paginas:
                try:
                    req2 = urllib.request.Request(link_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req2, timeout=8) as resp2:
                        html2 = resp2.read().decode("utf-8", errors="replace")
                    for match in _PADRAO_EMAIL.findall(html2):
                        emails.add(match.lower())
                except Exception:
                    continue

    except Exception as e:
        print(f"  [EmailFinder] Erro acessando {url}: {e}")
    return emails, texto_completo, soup


def _extrair_funcionarios(texto: str) -> str | None:
    match = _PADRAO_FUNCIONARIOS.search(texto)
    if match:
        return match.group(0).strip()
    return None


def _extrair_rodada(texto: str) -> tuple[str | None, str | None]:
    match = _PADRAO_RODADA.search(texto)
    if match:
        return match.group(0).strip(), match.group(1).strip()
    return None, None


def _extrair_clientes(texto: str) -> str | None:
    match = _PADRAO_CLIENTES.search(texto)
    if match:
        return match.group(0).strip()
    return None


def _extrair_faturamento(texto: str) -> str | None:
    match = _PADRAO_FATURAMENTO.search(texto)
    if match:
        return match.group(0).strip()
    return None


def _buscar_dados_economicos(nome: str) -> dict:
    dados = {}
    queries = [
        f"{nome} faturamento rodada investimento 2025 2026",
        f"{nome} startup funcionarios clientes receita"
    ]
    for q in queries:
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(q, max_results=3):
                    url = r.get("href", "")
                    dominio = urlparse(url).netloc.lower()
                    if any(dom in dominio for dom in ["facebook", "instagram", "twitter", "linkedin", "youtube"]):
                        continue
                    _emails, texto, _ = _extrair_dados_pagina(url)
                    if not texto:
                        continue
                    func = _extrair_funcionarios(texto)
                    if func and not dados.get("funcionarios"):
                        dados["funcionarios"] = func
                    rodada_label, rodada_valor = _extrair_rodada(texto)
                    if rodada_valor and not dados.get("rodada"):
                        dados["rodada"] = rodada_label
                        dados["rodada_valor"] = rodada_valor
                    cli = _extrair_clientes(texto)
                    if cli and not dados.get("clientes"):
                        dados["clientes"] = cli
                    fat = _extrair_faturamento(texto)
                    if fat and not dados.get("faturamento"):
                        dados["faturamento"] = fat
                    time.sleep(SCRAPING_DELAY_SECONDS)
        except Exception as e:
            print(f"  [EmailFinder] Erro buscando dados econômicos de {nome}: {e}")
    return dados


def _buscar_cnpj(nome: str) -> str | None:
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(f"{nome} CNPJ", max_results=5):
                texto = (r.get("title", "") + " " + r.get("body", "") + " " + r.get("href", ""))
                match = _PADRAO_CNPJ.search(texto)
                if match:
                    return match.group(0)
                match = _PADRAO_CNPJ_LIMPO.search(texto.replace(".", "").replace("/", "").replace("-", ""))
                if match:
                    c = match.group(1)
                    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
    except Exception as e:
        print(f"  [EmailFinder] Erro buscando CNPJ de {nome}: {e}")
    return None


def _consultar_receitaws(cnpj: str, tentativas: int = 3) -> dict | None:
    cnpj_limpo = re.sub(r"\D", "", cnpj)
    for tentativa in range(tentativas):
        try:
            url = f"https://receitaws.com.br/v1/cnpj/{cnpj_limpo}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
            if dados.get("status") == "ERROR":
                print(f"  [EmailFinder] ReceitaWS erro: {dados.get('message', 'desconhecido')}")
                time.sleep(5)
                continue
            return dados
        except Exception as e:
            print(f"  [EmailFinder] ReceitaWS falha (tentativa {tentativa+1}/{tentativas}): {e}")
            if tentativa < tentativas - 1:
                time.sleep(6)
    return None


def _extrair_dados_cnpj(dados: dict) -> dict:
    result = {}
    if dados.get("municipio") and dados.get("uf"):
        result["cidade"] = f"{dados['municipio']} - {dados['uf']}"
    if dados.get("email"):
        result["email"] = dados["email"].strip().lower()
    if dados.get("porte"):
        # Porte: "MEI", "ME", "EPP", "DEMAIS" (grande)
        mapa_porte = {"mei": "1 funcionário", "me": "1-9 funcionários", "epp": "10-49 funcionários", "demais": "50+ funcionários"}
        porte_key = dados["porte"].lower().strip()
        result["funcionarios"] = mapa_porte.get(porte_key, dados["porte"])
    if dados.get("capital_social"):
        try:
            val = float(dados["capital_social"].replace(",", "."))
            if val >= 1_000_000:
                result["faturamento"] = f"Capital social: R$ {val/1_000_000:.1f}M"
            elif val >= 1000:
                result["faturamento"] = f"Capital social: R$ {val/1000:.0f}K"
            else:
                result["faturamento"] = f"Capital social: R$ {val:.0f}"
        except ValueError:
            pass
    if dados.get("telefone"):
        telefone = re.sub(r"\D", "", dados["telefone"])
        if not result.get("email") and len(telefone) >= 8:
            pass  # só guardamos telefone como fallback se não achar nada
    return result


def _buscar_linkedin(nome: str) -> str | None:
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(f"{nome} linkedin", max_results=5):
                url = r.get("href", "")
                if "linkedin.com/company/" in url or "linkedin.com/school/" in url:
                    return url.split("?")[0]
                if "linkedin.com/in/" in url and "/company/" not in url and "/school/" not in url:
                    continue
    except Exception as e:
        print(f"  [EmailFinder] Erro buscando LinkedIn de {nome}: {e}")
    return None


def _extrair_dados_linkedin(linkedin_url: str) -> dict:
    dados = {"email": None, "cidade": None, "funcionarios": None}
    try:
        req = urllib.request.Request(
            linkedin_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "lxml")

        for meta in soup.find_all("meta"):
            prop = (meta.get("property") or "").lower()
            name = (meta.get("name") or "").lower()
            content = meta.get("content", "")
            if "og:description" in prop or "description" in name:
                texto = content
                for match in _PADRAO_EMAIL.findall(texto):
                    dados["email"] = match.lower()
                for m in _PADRAO_CIDADE_BR.findall(texto):
                    cidade, uf = m
                    dados["cidade"] = f"{cidade.strip()} - {uf}"

        page_text = soup.get_text(separator=" ") if soup else ""
        if not dados.get("email"):
            for match in _PADRAO_EMAIL.findall(page_text):
                dados["email"] = match.lower()
                break
        if not dados.get("cidade"):
            for m in _PADRAO_CIDADE_BR.findall(page_text):
                cidade, uf = m
                dados["cidade"] = f"{cidade.strip()} - {uf}"
                break
        funcionario_match = _PADRAO_FUNCIONARIOS.search(page_text)
        if funcionario_match:
            dados["funcionarios"] = funcionario_match.group(0).strip()
    except Exception as e:
        print(f"  [EmailFinder] Erro ao acessar LinkedIn {linkedin_url}: {e}")
    return dados


def _buscar_email_ddg(nome: str) -> str | None:
    emails_encontrados = set()
    queries = [
        f'"{nome}" "contato@"',
        f'"{nome}" email contato',
        f'{nome} "mailto:"',
        f'"{nome}" contato comercial email',
    ]
    try:
        with DDGS() as ddgs:
            for q in queries:
                for r in ddgs.text(q, max_results=5):
                    texto = (r.get("title", "") + " " + r.get("body", "") + " " + r.get("href", ""))
                    for m in _PADRAO_EMAIL.findall(texto):
                        if "noreply" not in m and "no-reply" not in m:
                            emails_encontrados.add(m.lower())
                time.sleep(SCRAPING_DELAY_SECONDS)
    except Exception as e:
        print(f"  [EmailFinder] Erro buscando email DDG para {nome}: {e}")

    if not emails_encontrados:
        return None
    return _filtrar_email_valido(emails_encontrados, nome)


def _extrair_cidade(soup: BeautifulSoup, texto: str) -> str | None:
    from pipeline.utils.validation import _MUNICIPIOS_IBGE
    
    # Try structured data first
    for tag in soup.find_all(["meta", "span", "div", "p"], attrs={"itemprop": "addressLocality"}):
        cid = tag.get("content") or tag.get_text()
        if cid and len(cid.strip()) > 2:
            valido, normalizada = validar_cidade(cid.strip())
            if valido:
                return normalizada
            if _MUNICIPIOS_IBGE is not None:
                return None
            return cid.strip()

    # Try "Cidade - UF" pattern
    for match in _PADRAO_CIDADE_BR.findall(texto):
        cidade, uf = match
        raw = f"{cidade.strip()} - {uf}"
        valido, normalizada = validar_cidade(raw)
        if valido:
            return normalizada
        if _MUNICIPIOS_IBGE is not None:
            continue
        return raw

    # Try known cities in text
    texto_lower = texto.lower()
    for cidade in _CIDADES_BR_FALLBACK:
        if cidade in texto_lower:
            return normalizar_cidade(cidade)
    return None


def _filtrar_email_valido(emails: set, nome: str) -> str | None:
    dominio_esperado = nome.lower().replace(" ", "").replace("-", "").replace(".", "")
    preferencia = []
    for email in emails:
        if "noreply" in email or "no-reply" in email or "donotreply" in email:
            continue
        if any(email.endswith(f".{tld}") for tld in ["jpg", "png", "gif", "pdf"]):
            continue
        preferencia.append(email)

    if not preferencia:
        return None

    # Preferir emails com dominio parecido com o nome
    for email in preferencia:
        local, dominio = email.split("@")
        if dominio_esperado in dominio.replace(".", "").replace("-", ""):
            return email

    # Preferir contato@ / hello@ / comercial@
    for email in preferencia:
        local = email.split("@")[0]
        if local in ["contato", "contact", "hello", "oi", "comercial", "vendas", "talk"]:
            return email

    return preferencia[0]


def run_email_finder(startups_coletadas: list[dict]) -> list[dict]:
    encontrados = 0
    for startup in startups_coletadas:
        startup_id = startup.get("id")
        nome = startup.get("nome", "")
        website_atual = startup.get("website", "")

        if not nome or not startup_id:
            continue

        existente = fetch_one("SELECT email_contato, cidade FROM startups WHERE id = ?", (startup_id,))
        email_existente = existente and existente.get("email_contato")
        cidade_existente = existente and existente.get("cidade")

        if email_existente and cidade_existente:
            print(f"  [EmailFinder] {nome}: email ({email_existente}) e cidade ({cidade_existente}) já cadastrados")
            continue

        print(f"  [EmailFinder] Buscando email para: {nome}")

    site_para_buscar = None
    if website_atual and urlparse(website_atual).netloc:
        dominio_stored = urlparse(website_atual).netloc.lower()
        nome_slug = nome.lower().replace(" ", "").replace("-", "").replace(".", "")
        dominio_clean = dominio_stored.replace("www.", "").replace(".com", "").replace(".br", "").replace(".com.br", "")
        parece_site_proprio = nome_slug in dominio_clean or len(dominio_clean.split(".")) <= 2
        if parece_site_proprio:
            site_para_buscar = website_atual
        else:
            site_oficial = _buscar_site_oficial(nome)
            if site_oficial:
                site_para_buscar = site_oficial
                website_atual = site_oficial
            else:
                site_para_buscar = website_atual
    if not site_para_buscar:
        site_para_buscar = _buscar_site_oficial(nome)

        email = None
        cidade = None
        funcionarios = None
        rodada_label = None
        rodada_valor = None
        clientes = None
        faturamento = None

        if site_para_buscar:
            emails, soup_texto, soup = _extrair_dados_pagina(site_para_buscar)
            email = _filtrar_email_valido(emails, nome)
            cidade = _extrair_cidade(soup, soup_texto) if soup else None
            funcionarios = _extrair_funcionarios(soup_texto) if soup_texto else None
            rodada_label, rodada_valor = _extrair_rodada(soup_texto) if soup_texto else (None, None)
            clientes = _extrair_clientes(soup_texto) if soup_texto else None
            faturamento = _extrair_faturamento(soup_texto) if soup_texto else None

        # Search DDG for economic data if not found on site
        econ = _buscar_dados_economicos(nome)
        funcionarios = funcionarios or econ.get("funcionarios")
        if not rodada_valor:
            rodada_label = econ.get("rodada")
            rodada_valor = econ.get("rodada_valor")
        clientes = clientes or econ.get("clientes")
        faturamento = faturamento or econ.get("faturamento")

        # Fallback: buscar CNPJ na ReceitaWS se faltar email ou cidade
        if not email or not cidade:
            cnpj = _buscar_cnpj(nome)
            if cnpj:
                print(f"  [EmailFinder] {nome}: CNPJ encontrado ({cnpj}), consultando ReceitaWS...")
                dados_cnpj = _consultar_receitaws(cnpj)
                if dados_cnpj:
                    cnpj_data = _extrair_dados_cnpj(dados_cnpj)
                    if not email:
                        email = cnpj_data.get("email")
                    if not cidade:
                        cidade = cidade or cnpj_data.get("cidade")
                    funcionarios = funcionarios or cnpj_data.get("funcionarios")
                    faturamento = faturamento or cnpj_data.get("faturamento")
                time.sleep(6)

        # Fallback: buscar email via DDG específico
        if not email and nome:
            email_ddg = _buscar_email_ddg(nome)
            if email_ddg:
                print(f"  [EmailFinder] {nome}: email encontrado via DDG: {email_ddg}")
                email = email_ddg

        # Fallback: buscar dados no LinkedIn
        if (not email or not cidade) and nome:
            linkedin_url = _buscar_linkedin(nome)
            if linkedin_url:
                print(f"  [EmailFinder] {nome}: LinkedIn encontrado ({linkedin_url})")
                dados_li = _extrair_dados_linkedin(linkedin_url)
                if not email and dados_li.get("email"):
                    print(f"  [EmailFinder] {nome}: email encontrado via LinkedIn: {dados_li['email']}")
                    email = dados_li["email"]
                if not cidade and dados_li.get("cidade"):
                    print(f"  [EmailFinder] {nome}: cidade encontrada via LinkedIn: {dados_li['cidade']}")
                    cidade = dados_li["cidade"]
                funcionarios = funcionarios or dados_li.get("funcionarios")
                time.sleep(SCRAPING_DELAY_SECONDS)

        if email:
            email_valido, erro = validar_email(email)
            if not email_valido and validar_formato_email(email):
                print(f"  [EmailFinder] {nome}: email {email} não passou validação MX ({erro}), mas será armazenado")
            elif not validar_formato_email(email):
                print(f"  [EmailFinder] {nome}: email inválido {email}, ignorando")
                email = None

        if cidade:
            from pipeline.utils.validation import _MUNICIPIOS_IBGE
            cidade_valida, cidade_normalizada = validar_cidade(cidade)
            if cidade_valida:
                cidade = cidade_normalizada
            elif _MUNICIPIOS_IBGE is not None:
                print(f"  [EmailFinder] {nome}: cidade '{cidade}' não encontrada no IBGE, ignorando")
                cidade = None
            else:
                cidade_norm = normalizar_cidade(cidade)
                if cidade_norm and cidade_norm != cidade:
                    print(f"  [EmailFinder] {nome}: cidade normalizada '{cidade}' -> '{cidade_norm}'")
                    cidade = cidade_norm

        if email or cidade or funcionarios or rodada_valor:
            updates = []
            params = []
            if email:
                updates.append("email_contato = ?")
                params.append(email)
            if cidade:
                updates.append("cidade = ?")
                params.append(cidade)
            if funcionarios:
                updates.append("numero_funcionarios_faixa = ?")
                params.append(funcionarios)
            if rodada_valor:
                updates.append("ultima_rodada_valor = ?")
                params.append(rodada_valor)
            if rodada_label:
                updates.append("ultima_rodada_data = ?")
                params.append(rodada_label)
            updates.append("updated_at = datetime('now')")
            params.append(startup_id)
            execute_query(
                f"UPDATE startups SET {', '.join(updates)} WHERE id = ?",
                tuple(params)
            )
            print(f"  [EmailFinder] {nome}: email={email or '-'}, cidade={cidade or '-'}, "
                  f"func={funcionarios or '-'}, rodada={rodada_valor or '-'}, "
                  f"clientes={clientes or '-'}, fat={faturamento or '-'}")
            encontrados += 1
        else:
            print(f"  [EmailFinder] {nome}: nada encontrado")

        startup["email_contato"] = email
        startup["cidade"] = cidade or startup.get("cidade")
        startup["funcionarios"] = funcionarios
        startup["rodada_valor"] = rodada_valor
        startup["clientes"] = clientes
        startup["faturamento"] = faturamento
        time.sleep(SCRAPING_DELAY_SECONDS)

    print(f"  [EmailFinder] Total: {encontrados} emails encontrados")
    return {"startups_coletadas": startups_coletadas}
