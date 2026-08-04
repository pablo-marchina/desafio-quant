# limpar.py
import json
import re

with open("raw_documents.json", "r", encoding="utf-8") as f:
    documents = json.load(f)

def limpar_texto(texto: str) -> str:
    # remove linhas de cookie/legal comuns
    linhas_ignorar = ["cookie", "terms of service", "all rights reserved", "©"]
    linhas = texto.split("\n")
    linhas_filtradas = [
        l for l in linhas
        if not any(termo in l.lower() for termo in linhas_ignorar)
    ]
    texto_limpo = "\n".join(linhas_filtradas)

    # normaliza espaços
    texto_limpo = re.sub(r"\n{3,}", "\n\n", texto_limpo)
    texto_limpo = re.sub(r" {2,}", " ", texto_limpo)
    return texto_limpo.strip()

for doc in documents:
    doc["clean_text"] = limpar_texto(doc["raw_text"])

with open("clean_documents.json", "w", encoding="utf-8") as f:
    json.dump(documents, f, ensure_ascii=False, indent=2)