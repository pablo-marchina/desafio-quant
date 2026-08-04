from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

from . import brasil_api
from . import cnpj as cnpj_mod

_PORTE_MAP = {
    "MEI": "MEI",
    "MICRO EMPRESA": "ME",
    "EMPRESA DE PEQUENO PORTE": "EPP",
    "DEMAIS": "DEMAIS",
}

_RAIZ = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SAIDA = _RAIZ / "data" / "jsons" / "empresas_uso_ia" / "identidade.json"


def _gravar_json(atualizacoes: list[dict]) -> None:
    _SAIDA.parent.mkdir(parents=True, exist_ok=True)

    existentes: dict[int, dict] = {}
    if _SAIDA.exists():
        for reg in json.loads(_SAIDA.read_text(encoding="utf-8")):
            existentes[int(reg["empresa_id"])] = reg

    for reg in atualizacoes:
        existentes[int(reg["empresa_id"])] = {
            **reg,
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }

    _SAIDA.write_text(
        json.dumps(sorted(existentes.values(), key=lambda r: r["empresa_id"]), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[json] {len(atualizacoes)} registro(s) salvo(s) em {_SAIDA}")


def enriquecer(atualizar_banco: bool = True, nome: str | None = None) -> list[dict]:
    # Busca empresas onde o CNPJ está ausente OU algum campo BrasilAPI ainda está vazio
    registros = (
        supabase.table("empresas_uso_ia")
        .select("empresa_id, cnpj")
        .eq("cnpj_pendente", False)
        .or_(
            "cnpj.is.null,"
            "cnae_principal.is.null,"
            "porte.is.null,"
            "capital_social.is.null,"
            "natureza_juridica.is.null"
        )
        .execute()
        .data
    )

    if not registros:
        print("[info] nenhuma empresa pendente de enriquecimento de identidade")
        return []

    ids = [r["empresa_id"] for r in registros]
    mapa_cnpj = {int(r["empresa_id"]): r for r in registros}

    query = supabase.table("empresas").select("id, nome, dominio").in_("id", ids)
    if nome:
        query = query.eq("nome", nome)
    dominios_rows = query.execute().data
    mapa = {int(r["id"]): r for r in dominios_rows}

    print(f"[info] {len(ids)} empresa(s) para enriquecer\n")

    atualizacoes: list[dict] = []
    sem_dominio: list[str] = []
    sem_cnpj: list[str] = []

    for empresa_id in ids:
        info = mapa.get(empresa_id)
        if not info:
            continue

        info_registro = mapa_cnpj.get(empresa_id, {})
        nome    = info.get("nome", f"id={empresa_id}")
        dominio = info.get("dominio")

        if not dominio:
            print(f"  [skip] {nome} — sem domínio cadastrado")
            sem_dominio.append(nome)
            continue

        cnpj_existente = info_registro.get("cnpj")

        if cnpj_existente:
            # CNPJ já conhecido — só faltam campos BrasilAPI
            print(f"  [→] {nome}  ({dominio})  [cnpj já existe, atualizando campos BrasilAPI]")
            cnpj = cnpj_existente
        else:
            print(f"  [→] {nome}  ({dominio})")
            cnpj = cnpj_mod.obter(dominio, nome=nome)
            if not cnpj:
                print(f"       [✗] CNPJ não encontrado — marcado como pendente (preencher manualmente)")
                sem_cnpj.append(nome)
                if atualizar_banco:
                    supabase.table("empresas_uso_ia").upsert(
                        {"empresa_id": empresa_id, "cnpj_pendente": True},
                        on_conflict="empresa_id",
                    ).execute()
                time.sleep(0.5)
                continue

        print(f"       [cnpj] {cnpj_mod.formatar(cnpj)}")

        time.sleep(0.3)
        dados = brasil_api.consultar_cnpj(cnpj)
        if not dados:
            atualizacoes.append({"empresa_id": empresa_id, "cnpj": cnpj})
            continue

        situacao = brasil_api.situacao(dados)
        if situacao not in ("", "ATIVA"):
            print(f"       [aviso] situação cadastral: {situacao}")

        razao_social     = dados.get("razao_social", "").title()
        nome_fantasia    = dados.get("nome_fantasia", "").title()
        situacao_rf      = brasil_api.situacao(dados)
        municipio        = dados.get("municipio", "").title()
        uf               = dados.get("uf", "")
        data_inicio      = dados.get("data_inicio_atividade")

        cnae_codigo      = str(dados.get("cnae_fiscal", "")).strip()
        cnae_desc        = dados.get("cnae_fiscal_descricao", "").strip()
        cnae_principal   = f"{cnae_codigo} - {cnae_desc}" if cnae_codigo and cnae_desc else (cnae_desc or None)

        porte_raw        = (dados.get("porte") or "").upper().strip()
        porte            = _PORTE_MAP.get(porte_raw) or (porte_raw or None)

        capital_social   = dados.get("capital_social")
        natureza_juridica = dados.get("natureza_juridica") or None

        print(f"       [cnae] {cnae_principal}  |  [porte] {porte}  |  [razao_social] {razao_social[:40]}")
        atualizacoes.append({
            "empresa_id":        empresa_id,
            "cnpj":              cnpj,
            "razao_social":      razao_social or None,
            "nome_fantasia":     nome_fantasia or None,
            "situacao_rf":       situacao_rf or None,
            "municipio":         municipio or None,
            "uf":                uf or None,
            "cnae_principal":    cnae_principal,
            "porte":             porte,
            "capital_social":    capital_social,
            "natureza_juridica": natureza_juridica,
            "ano_fundacao":      int(data_inicio[:4]) if data_inicio else None,
        })

        time.sleep(0.5)

    print(
        f"\n[resumo] {len(atualizacoes)} enriquecida(s) | "
        f"{len(sem_cnpj)} sem CNPJ | {len(sem_dominio)} sem domínio"
    )

    if atualizacoes:
        _gravar_json(atualizacoes)

        if atualizar_banco:
            supabase.table("empresas_uso_ia").upsert(
                atualizacoes, on_conflict="empresa_id"
            ).execute()
            print(f"[banco] {len(atualizacoes)} registro(s) atualizado(s) em empresas_uso_ia")

    return atualizacoes


if __name__ == "__main__":
    enriquecer()
