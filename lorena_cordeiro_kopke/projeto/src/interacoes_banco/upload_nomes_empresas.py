import json
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")


def upload() -> int:
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    json_path = _RAIZ / "data" / "jsons" / "nomes_empresas" / "nomes_empresas.json"
    with open(json_path, encoding="utf-8") as f:
        dados = json.load(f)
    response = (
        supabase.table("nomes_empresas")
        .upsert(dados, on_conflict="url")
        .execute()
    )
    print(f"Registros enviados: {len(response.data)}")
    return len(response.data)


if __name__ == "__main__":
    upload()
