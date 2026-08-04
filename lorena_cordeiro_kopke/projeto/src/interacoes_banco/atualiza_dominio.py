"""
Atualização manual de domínio e re-coleta de sinais_ia.

Uso:
    python -m src.interacoes_banco.atualiza_dominio

Fluxo:
  1. Lista todas as empresas cadastradas com seus domínios atuais
  2. Operador escolhe a empresa e informa o novo domínio
  3. O domínio é gravado em empresas.dominio (e espelhado em empresas_uso_ia.dominio)
  4. O pipeline de sinais_ia é re-executado para a empresa:
       gupy_vagas → institucional → imprensa → neofeed → filtro_ia
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

sys.path.insert(0, str(_RAIZ / "src"))

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_RE_DOMINIO = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")


# ---------------------------------------------------------------------------
# Carregamento de dados
# ---------------------------------------------------------------------------

def _carregar_empresas() -> list[dict]:
    rows = (
        supabase.table("empresas")
        .select("id, nome, dominio")
        .order("nome")
        .execute()
        .data
    )
    return rows or []


# ---------------------------------------------------------------------------
# Exibição
# ---------------------------------------------------------------------------

def _exibir_lista(empresas: list[dict]) -> None:
    print(f"\nEmpresas cadastradas ({len(empresas)}):")
    print("-" * 65)
    for i, emp in enumerate(empresas, 1):
        dominio_atual = emp.get("dominio") or "—"
        print(f"  {i:>3}. {emp['nome']:<40}  {dominio_atual}")
    print("-" * 65)


# ---------------------------------------------------------------------------
# Entrada do operador
# ---------------------------------------------------------------------------

def _ler_escolha(empresas: list[dict]) -> dict | None:
    while True:
        raw = input("\nNúmero da empresa (ou 'q' para sair): ").strip()
        if raw.lower() in ("q", "sair", ""):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(empresas):
            return empresas[int(raw) - 1]
        print(f"  [erro] escolha um número entre 1 e {len(empresas)}")


def _ler_dominio(dominio_atual: str | None) -> str | None:
    """Retorna domínio validado ou None para voltar."""
    hint = f" (atual: {dominio_atual})" if dominio_atual else ""
    while True:
        raw = input(f"  Novo domínio{hint} ('v' para voltar): ").strip().lower()
        if raw in ("v", "voltar", ""):
            return None
        # Remove protocolo caso o operador cole a URL completa
        raw = re.sub(r"^https?://", "", raw).rstrip("/")
        if _RE_DOMINIO.match(raw):
            return raw
        print("  [erro] domínio inválido — formato esperado: empresa.com.br")


# ---------------------------------------------------------------------------
# Gravação no banco
# ---------------------------------------------------------------------------

def _gravar_dominio(empresa_id: int, dominio: str) -> None:
    supabase.table("empresas").update({"dominio": dominio}).eq("id", empresa_id).execute()
    # Espelha em empresas_uso_ia, caso a linha já exista
    supabase.table("empresas_uso_ia").update({"dominio": dominio}).eq("empresa_id", empresa_id).execute()


# ---------------------------------------------------------------------------
# Re-coleta de sinais_ia
# ---------------------------------------------------------------------------

def _reexecutar_pipeline_sinais_ia(nome: str) -> None:
    """
    Re-executa os passos que produzem entradas em sinais_ia e reavalia
    o veredito de IA da empresa.

    Passos (mesma ordem de nova_empresa.py):
      1. descobre_gupy_vagas   → camada gupy_vagas
      2. descobre_institucional → camada institucional
      3. descobre_imprensa     → camada imprensa
      4. analisa_neofeed       → camada neofeed
      5. filtro_ia             → consolida sinais e grava em avaliacoes_ia
    """
    _titulo("re-coleta · gupy_vagas")
    from dados_ia_startups.descobre_gupy_vagas import pesquisar
    pesquisar(nome=nome)

    _titulo("re-coleta · institucional")
    from dados_ia_startups.descobre_institucional import pesquisar as pesquisar_inst
    pesquisar_inst(nome=nome)

    _titulo("re-coleta · imprensa")
    from dados_ia_startups.descobre_imprensa import pesquisar as pesquisar_imp
    pesquisar_imp(nome=nome)

    _titulo("re-coleta · neofeed")
    from dados_ia_startups.analisa_neofeed import classificar
    classificar(nome=nome)

    _titulo("re-coleta · filtro_ia (veredito final)")
    from dados_ia_startups.filtro_ia import filtrar
    filtrar(filtrar_nome=nome)


def _titulo(texto: str) -> None:
    print()
    print("=" * 55)
    print(f"  {texto}")
    print("=" * 55)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def atualizar() -> None:
    print("=" * 65)
    print("  Atualização de domínio + re-coleta de sinais_ia")
    print("=" * 65)

    while True:
        empresas = _carregar_empresas()

        if not empresas:
            print("\n[info] nenhuma empresa cadastrada. Encerrando.")
            break

        _exibir_lista(empresas)

        emp = _ler_escolha(empresas)
        if emp is None:
            print("[info] saindo.")
            break

        print(f"\n  Empresa : {emp['nome']}  (id={emp['id']})")
        print(f"  Domínio : {emp.get('dominio') or '—'}")

        dominio = _ler_dominio(emp.get("dominio"))
        if dominio is None:
            continue

        confirma = input(f"\n  Gravar '{dominio}' para '{emp['nome']}'? (s/n): ").strip().lower()
        if confirma != "s":
            print("  [cancelado] voltando à lista.\n")
            continue

        _gravar_dominio(int(emp["id"]), dominio)
        print(f"  [banco] domínio gravado em empresas.dominio e empresas_uso_ia.dominio")

        re_executar = input("\n  Re-executar pipeline de sinais_ia para esta empresa? (s/n): ").strip().lower()
        if re_executar == "s":
            _reexecutar_pipeline_sinais_ia(emp["nome"])
            print(f"\n  [concluído] sinais_ia re-coletado para '{emp['nome']}'")
        else:
            print("  [info] pipeline não executado.")


# ── API pública para integração com Streamlit ─────────────────────────────────

def validar_e_normalizar_dominio(raw: str) -> str | None:
    """Remove protocolo, normaliza e valida. Retorna None se inválido."""
    raw = re.sub(r"^https?://", "", raw.strip()).rstrip("/")
    return raw if _RE_DOMINIO.match(raw) else None


def gravar_dominio_publico(empresa_id: int, dominio: str) -> None:
    _gravar_dominio(empresa_id, dominio)


def reexecutar_sinais_ia_publico(nome: str) -> str:
    """Roda o pipeline de sinais_ia e retorna o output capturado."""
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _reexecutar_pipeline_sinais_ia(nome)
    return buf.getvalue()


if __name__ == "__main__":
    atualizar()
