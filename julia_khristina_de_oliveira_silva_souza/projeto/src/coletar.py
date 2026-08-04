# coletar.py
import json
import re
import time
import trafilatura


def parse_pagina_industria(texto: str, vertical: str, url: str):
    """
    Divide uma hub page (industry vertical) em chunks por produto,
    usando os headers H3 (### Nome do Produto) como delimitador.
    Necessário porque essas páginas misturam vários produtos numa só URL.
    """
    blocos = re.split(r"\n###\s+", texto)
    resultados = []

    for bloco in blocos[1:]:  # primeiro split é o texto antes do 1º produto
        linhas = bloco.strip().split("\n", 1)
        nome_produto = linhas[0].strip()
        conteudo = linhas[1] if len(linhas) > 1 else ""

        if len(conteudo.strip()) < 50:  # bloco vazio/ruído, ignora
            continue

        resultados.append({
            "tech": nome_produto,
            "category": vertical,
            "url": url,
            "raw_text": conteudo.strip()
        })

    return resultados


with open("sources.json", "r", encoding="utf-8") as f:
    sources = json.load(f)

documents = []

for entry in sources:
    for url in entry["urls"]:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            print(f"[FALHOU] {url}")
            continue

        # hub pages precisam de output_format="markdown" pra preservar os headers (###),
        # que é o que o parse_pagina_industria usa pra separar os produtos.
        # Sem isso, trafilatura retorna texto puro e o regex não acha nada pra separar
        # (foi exatamente esse bug que zerou os chunks de saúde na primeira rodada).
        if entry.get("type") == "hub_page":
            text = trafilatura.extract(downloaded, include_tables=True, output_format="markdown")
        else:
            text = trafilatura.extract(downloaded, include_tables=True)

        if not text or len(text) < 200:
            print(f"[VAZIO/CURTO] {url}")
            continue

        if entry.get("type") == "hub_page":
            sub_docs = parse_pagina_industria(text, entry["category"], url)
            documents.extend(sub_docs)
            print(f"[OK - HUB PAGE] {url} -> {len(sub_docs)} produtos extraídos")
        else:
            documents.append({
                "tech": entry["tech"],
                "category": entry["category"],
                "url": url,
                "raw_text": text
            })
            print(f"[OK] {url} ({len(text)} chars)")

        time.sleep(1)  # educado com o servidor

with open("raw_documents.json", "w", encoding="utf-8") as f:
    json.dump(documents, f, ensure_ascii=False, indent=2)

print(f"\nTotal coletado: {len(documents)} documentos")