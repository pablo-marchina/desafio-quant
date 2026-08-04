# chunking.py
import json
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter

with open("clean_documents.json", "r", encoding="utf-8") as f:
    documents = json.load(f)

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,      # ~caracteres, aprox 350-400 tokens
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " "]
)

chunks = []

for doc in documents:
    pedacos = splitter.split_text(doc["clean_text"])
    for i, pedaco in enumerate(pedacos):
        chunks.append({
            "id": str(uuid.uuid4()),
            "tech": doc["tech"],
            "category": doc["category"],
            "url": doc["url"],
            "chunk_index": i,
            "text": pedaco
        })

with open("chunks.json", "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)

print(f"Total de chunks gerados: {len(chunks)}")