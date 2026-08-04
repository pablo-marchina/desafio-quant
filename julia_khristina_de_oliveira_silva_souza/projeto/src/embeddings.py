# embeddings.py
import json
import os
import time
import cohere
from dotenv import load_dotenv

load_dotenv()

with open("chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)

co = cohere.Client(os.environ["COHERE_API_KEY"])

textos = [c["text"] for c in chunks]


def embed_com_retry(lote: list, tentativas: int = 3, espera_base: int = 5) -> list:
    for tentativa in range(1, tentativas + 1):
        try:
            resposta = co.embed(
                texts=lote,
                model="embed-multilingual-v3.0",
                input_type="search_document"
            )
            return resposta.embeddings
        except Exception as e:
            if tentativa == tentativas:
                raise
            espera = espera_base * (2 ** (tentativa - 1))
            print(f"[Cohere] erro na tentativa {tentativa}/{tentativas}: {e}. Tentando de novo em {espera}s...")
            time.sleep(espera)


embeddings = []
BATCH_SIZE = 90

for i in range(0, len(textos), BATCH_SIZE):
    lote = textos[i:i + BATCH_SIZE]
    embeddings.extend(embed_com_retry(lote))
    print(f"Embeddings gerados: {i + len(lote)}/{len(textos)}")

for chunk, vetor in zip(chunks, embeddings):
    chunk["embedding"] = vetor

with open("chunks_with_embeddings.json", "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False)

print(f"\nTotal: {len(chunks)} chunks x {len(embeddings[0])} dimensões")