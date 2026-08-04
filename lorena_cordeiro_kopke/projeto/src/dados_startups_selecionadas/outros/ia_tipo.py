from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

from src.agents.classificador_ia_tipo_gemini import classificar_ia_tipo

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SAIDA = _RAIZ / "data" / "jsons" / "empresas_uso_ia" / "ia_tipo.json"


def _gravar_json(registros: list[dict]) -> None:
    _SAIDA.parent.mkdir(parents=True, exist_ok=True)

    existentes: dict[int, dict] = {}
    if _SAIDA.exists():
        for reg in json.loads(_SAIDA.read_text(encoding="utf-8")):
            existentes[int(reg["empresa_id"])] = reg

    for reg in registros:
        existentes[int(reg["empresa_id"])] = {
            **reg,
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }

    _SAIDA.write_text(
        json.dumps(
            sorted(existentes.values(), key=lambda r: r["empresa_id"]),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[json] {len(registros)} registro(s) salvo(s) em {_SAIDA}")


def descobrir(atualizar_banco: bool = True, nome: str | None = None) -> list[dict]:
    """Para cada empresa em empresas_uso_ia sem ia_tipo preenchido,
    classifica o tipo principal de IA e atualiza o campo."""
    query = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, produto, uso_ia_descricao")
        .is_("ia_tipo", "null")
        .not_.is_("cnpj", "null")
        .eq("cnpj_pendente", False)
    )
    registros = query.execute().data

    if not registros:
        print("[info] nenhuma empresa pendente de classificação de ia_tipo")
        return []

    ids = [r["empresa_id"] for r in registros]
    mapa_empresa = {int(r["empresa_id"]): r for r in registros}

    nomes_rows = (
        supabase.table("empresas")
        .select("id, nome")
        .in_("id", ids)
        .execute()
        .data
    )
    if nome:
        nomes_rows = [r for r in nomes_rows if r["nome"] == nome]

    print(f"[info] {len(nomes_rows)} empresa(s) para classificar ia_tipo\n")

    atualizacoes: list[dict] = []
    incertos: list[str] = []

    for row in nomes_rows:
        empresa_id = int(row["id"])
        nome_emp = row["nome"]
        empresa = mapa_empresa.get(empresa_id, {})

        print(f"  [→] {nome_emp}")

        resultado = classificar_ia_tipo(
            nome_empresa=nome_emp,
            produto=empresa.get("produto"),
            uso_ia=empresa.get("uso_ia_descricao"),
        )

        if resultado is None:
            print("       [?] não foi possível determinar")
            incertos.append(nome_emp)
        else:
            print(f"       [✓] ia_tipo = {resultado}")
            atualizacoes.append({"empresa_id": empresa_id, "ia_tipo": resultado})

        time.sleep(0.3)

    print(f"\n[resumo] {len(atualizacoes)} classificada(s) | {len(incertos)} incerta(s)")

    if incertos:
        print("[incertas — verificar manualmente]:")
        for n in incertos:
            print(f"  - {n}")

    if atualizacoes:
        _gravar_json(atualizacoes)

        if atualizar_banco:
            supabase.table("empresas_uso_ia").upsert(
                atualizacoes, on_conflict="empresa_id"
            ).execute()
            print(f"[banco] {len(atualizacoes)} ia_tipo atualizado(s) em empresas_uso_ia")

    return atualizacoes


if __name__ == "__main__":
    import sys

    _nome = None
    _apenas_json = "--dry-run" in sys.argv
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            _nome = arg

    descobrir(atualizar_banco=not _apenas_json, nome=_nome)
