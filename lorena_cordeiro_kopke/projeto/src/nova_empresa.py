from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))          # permite: from src.agents...
sys.path.insert(0, str(_RAIZ / "src"))  # permite: from dados_startups...

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(_RAIZ / ".env")


def _titulo(texto: str) -> None:
    separador = "=" * 60
    print(f"\n{separador}")
    print(f"  {texto}")
    print(separador)


def _inserir_empresa(nome: str) -> None:
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    response = (
        supabase.table("empresas")
        .upsert({"nome": nome}, on_conflict="nome")
        .execute()
    )
    print(f"[banco] empresa '{nome}' inserida/confirmada em 'empresas'")
    return response


def main(nome: str) -> None:
    inicio = time.time()

    _titulo(f"nova_empresa · adicionando: {nome}")
    _inserir_empresa(nome)

    _titulo("1/10 · descobre_dominio.py — descoberta de domínios")
    from dados_startups.descobre_dominio import descobrir as descobrir_dominio
    descobrir_dominio(nome=nome)

    _titulo("2/10 · descobre_gupy.py — descoberta de subdominios Gupy")
    from dados_startups.descobre_gupy import descobrir as descobrir_gupy
    descobrir_gupy(nome=nome)

    _titulo("3/10 · descobre_gupy_vagas.py — vagas de IA no Gupy")
    from dados_ia_startups.descobre_gupy_vagas import pesquisar
    pesquisar(nome=nome)

    _titulo("4/10 · descobre_institucional.py — análise site institucional")
    from dados_ia_startups.descobre_institucional import pesquisar as pesquisar_institucional
    pesquisar_institucional(nome=nome)

    _titulo("5/10 · descobre_imprensa.py — notícias de IA (News API)")
    from dados_ia_startups.descobre_imprensa import pesquisar as pesquisar_imprensa
    pesquisar_imprensa(nome=nome)

    _titulo("6/10 · analisa_neofeed.py — tag neofeed")
    from dados_ia_startups.analisa_neofeed import classificar as classificar_neofeed
    classificar_neofeed(nome=nome)

    _titulo("7/10 · filtro_ia.py — veredito de uso de IA")
    from dados_ia_startups.filtro_ia import filtrar as filtrar_ia
    filtrar_ia(filtrar_nome=nome)

    _titulo("8/10 · inicia_aprofundamento.py — seed + enriquecimento completo")
    from dados_startups_selecionadas.inicia_aprofundamento import atualizar as aprofundar
    aprofundar(nome=nome)

    _titulo("9/10 · atualiza_situacao_coleta.py — situação de coleta")
    from interacoes_banco.atualiza_situacao_coleta import atualizar
    atualizar()

    _titulo("10/10 · inicia_recomendacao.py — recomendações NVIDIA")
    from recomendacao.inicia_recomendacao import rodar
    rodar()

    elapsed = time.time() - inicio
    print(f"\n{'=' * 60}")
    print(f"  '{nome}' processada em {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python src/nova_empresa.py \"Nome da Empresa\"")
        sys.exit(1)

    nome_empresa = " ".join(sys.argv[1:])
    main(nome_empresa)
