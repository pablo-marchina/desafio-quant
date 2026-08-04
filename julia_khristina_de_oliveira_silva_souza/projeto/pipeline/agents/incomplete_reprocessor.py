import time
from urllib.parse import urlparse
from pipeline.db.connection import fetch_all, fetch_one, execute_query
from pipeline.agents.email_finder import (
    _buscar_site_oficial, _extrair_dados_pagina, _filtrar_email_valido,
    _extrair_cidade, _buscar_cnpj, _consultar_receitaws, _extrair_dados_cnpj,
    _buscar_email_ddg, _buscar_linkedin, _extrair_dados_linkedin
)
from pipeline.utils.validation import validar_cidade, normalizar_cidade, validar_formato_email
from pipeline.config.settings import SCRAPING_DELAY_SECONDS


def reprocessar_incompletas(limite: int = 50) -> dict:
    startups = fetch_all(
        """SELECT id, nome, website, email_contato, cidade
           FROM startups
           WHERE (email_contato IS NULL OR email_contato = '')
              OR (cidade IS NULL OR cidade = '')
           ORDER BY updated_at ASC
           LIMIT ?""",
        (limite,)
    )

    resultados = {
        "processadas": 0,
        "emails_encontrados": 0,
        "cidades_encontradas": 0,
        "sem_email": 0,
        "sem_cidade": 0,
        "erros": []
    }

    for startup in startups:
        startup_id = startup["id"]
        nome = startup["nome"]
        website_atual = startup.get("website", "")
        tem_email = startup.get("email_contato")
        tem_cidade = startup.get("cidade")

        print(f"[Reprocessor] {nome}: email={'sim' if tem_email else 'não'}, cidade={'sim' if tem_cidade else 'não'}")

        email = tem_email
        cidade = tem_cidade

        site_para_buscar = website_atual if website_atual and urlparse(website_atual).netloc else None
        if not site_para_buscar:
            site_para_buscar = _buscar_site_oficial(nome)

        if site_para_buscar and (not email or not cidade):
            try:
                emails_set, soup_texto, soup = _extrair_dados_pagina(site_para_buscar)
                if not email:
                    email = _filtrar_email_valido(emails_set, nome)
                if not cidade and soup:
                    cidade = _extrair_cidade(soup, soup_texto)
            except Exception as e:
                print(f"  [Reprocessor] Erro ao processar site {site_para_buscar}: {e}")
            time.sleep(SCRAPING_DELAY_SECONDS)

        if not email or not cidade:
            try:
                cnpj = _buscar_cnpj(nome)
                if cnpj:
                    dados_cnpj = _consultar_receitaws(cnpj)
                    if dados_cnpj:
                        cnpj_data = _extrair_dados_cnpj(dados_cnpj)
                        if not email:
                            email = cnpj_data.get("email")
                        if not cidade:
                            cidade = cnpj_data.get("cidade")
                    time.sleep(6)
            except Exception as e:
                print(f"  [Reprocessor] Erro ReceitaWS para {nome}: {e}")

        if not email:
            try:
                email_ddg = _buscar_email_ddg(nome)
                if email_ddg:
                    email = email_ddg
            except Exception as e:
                print(f"  [Reprocessor] Erro DDG para {nome}: {e}")

        if (not email or not cidade) and nome:
            try:
                linkedin_url = _buscar_linkedin(nome)
                if linkedin_url:
                    dados_li = _extrair_dados_linkedin(linkedin_url)
                    if not email and dados_li.get("email"):
                        email = dados_li["email"]
                    if not cidade and dados_li.get("cidade"):
                        cidade = dados_li["cidade"]
                    time.sleep(SCRAPING_DELAY_SECONDS)
            except Exception as e:
                print(f"  [Reprocessor] Erro LinkedIn para {nome}: {e}")

        if email and not tem_email:
            if not validar_formato_email(email):
                email = None

    if cidade:
        from pipeline.utils.validation import _MUNICIPIOS_IBGE
        valida, normalizada = validar_cidade(cidade)
        if valida:
            cidade = normalizada
        elif _MUNICIPIOS_IBGE is not None:
            print(f"  [Reprocessor] cidade '{cidade}' não encontrada no IBGE, ignorando")
            cidade = None
        else:
            cidade = normalizar_cidade(cidade)

        updates = []
        params = []
        if email and not tem_email:
            updates.append("email_contato = ?")
            params.append(email)
            resultados["emails_encontrados"] += 1
        if cidade and not tem_cidade:
            updates.append("cidade = ?")
            params.append(cidade)
            resultados["cidades_encontradas"] += 1

        if updates:
            updates.append("updated_at = datetime('now')")
            params.append(startup_id)
            execute_query(
                f"UPDATE startups SET {', '.join(updates)} WHERE id = ?",
                tuple(params)
            )
            print(f"  [Reprocessor] {nome}: atualizado email={email or '-'}, cidade={cidade or '-'}")

        if not tem_email and not email:
            resultados["sem_email"] += 1
        if not tem_cidade and not cidade:
            resultados["sem_cidade"] += 1
        resultados["processadas"] += 1

    print(f"[Reprocessor] Concluído: {resultados['processadas']} processadas, "
          f"{resultados['emails_encontrados']} emails, {resultados['cidades_encontradas']} cidades")
    return resultados
