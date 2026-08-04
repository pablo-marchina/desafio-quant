# enriquecer.py
import json
import os
import time
import cohere
from dotenv import load_dotenv

load_dotenv()

# Cliente separado (ClientV2) só pra chat — o "co" do embed/rerank nos outros
# scripts continua sendo cohere.Client() normalmente, sem mudança lá.
co_chat = cohere.ClientV2(os.environ["COHERE_API_KEY"])

with open("categorias_gap.json", "r", encoding="utf-8") as f:
    categorias_gap = json.load(f)

with open("raw_documents.json", "r", encoding="utf-8") as f:
    documents = json.load(f)

# agrupa o texto já raspado por tecnologia (pode ter mais de 1 URL por tech)
techs = {}
for doc in documents:
    if doc["tech"] not in techs:
        techs[doc["tech"]] = {"category": doc["category"], "texto": ""}
    techs[doc["tech"]]["texto"] += " " + doc["raw_text"][:500]


def gerar_com_retry(prompt: str, tentativas: int = 3, espera: int = 5) -> str:
    """Tenta de novo em caso de erro transitório do servidor da Cohere."""
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = co_chat.chat(
                model="command-a-03-2025",
                messages=[{"role": "user", "content": prompt}]
            )
            return resposta.message.content[0].text
        except Exception as e:
            if tentativa == tentativas:
                raise
            print(f"[Cohere] erro na tentativa {tentativa}/{tentativas}: {e}. Tentando de novo em {espera}s...")
            time.sleep(espera)


gerados = []

for tech, info in techs.items():
    categoria = info["category"]
    gap = categorias_gap.get(categoria)

    if not gap:
        print(f"[AVISO] categoria '{categoria}' (tech: {tech}) sem descrição em categorias_gap.json — pulando")
        continue

    prompt = (
        f"Você é um especialista em recomendar tecnologias NVIDIA para startups.\n\n"
        f"Tecnologia: {tech}\n"
        f"Descrição da tecnologia (fonte oficial): {info['texto'][:800]}\n\n"
        f"Escreva 1 parágrafo curto (2-3 frases), em português, explicando especificamente "
        f"por que essa tecnologia é recomendada para uma startup {gap}. "
        f"Seja direto e técnico, sem linguagem de marketing. Cite o nome da tecnologia."
    )

    texto_gerado = gerar_com_retry(prompt)

    gerados.append({
        "tech": tech,
        "category": categoria,
        "url": "gerado_automaticamente:enriquecimento_caso_uso",
        "raw_text": texto_gerado
    })
    print(f"[OK] {tech} -> parágrafo gerado")
    time.sleep(1)

documents.extend(gerados)

with open("raw_documents.json", "w", encoding="utf-8") as f:
    json.dump(documents, f, ensure_ascii=False, indent=2)

print(f"\nAdicionados {len(gerados)} parágrafos gerados automaticamente. Total: {len(documents)} documentos")