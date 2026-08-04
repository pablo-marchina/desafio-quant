from __future__ import annotations

import sys
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(_RAIZ / "src"))


def _titulo(texto: str) -> None:
    separador = "=" * 60
    print(f"\n{separador}")
    print(f"  {texto}")
    print(separador)


def main() -> None:
    inicio = time.time()

    # 1. Coleta artigos brutos do Neofeed
    _titulo("1/14 · coleta_neofeed.py — raspagem Neofeed")
    from coleta_startups.coleta_neofeed import coletar
    coletar()

    # 2. Filtra e extrai nomes de startups
    _titulo("2/14 · filtro.py — extração de nomes")
    from coleta_startups.filtro import filtrar
    filtrar()

    # 3. Envia nomes brutos para Supabase 
    _titulo("3/14 · upload_nomes_empresas.py — upload para Supabase")
    from interacoes_banco.upload_nomes_empresas import upload as upload_nomes
    upload_nomes()

    # 4. Envia empresas para Supabase (tabela empresas)
    _titulo("4/14 · upload_empresas.py — upload para Supabase")
    from interacoes_banco.upload_empresas import upload as upload_empresas
    upload_empresas()

    # 5. Descobre domínio de cada empresa
    _titulo("5/14 · descobre_dominio.py — descoberta de domínios")
    from dados_startups.descobre_dominio import descobrir as descobrir_dominio
    descobrir_dominio()

    # 6. Descobre subdomínio Gupy de cada empresa
    _titulo("6/14 · descobre_gupy.py — descoberta de subdominios Gupy")
    from dados_startups.descobre_gupy import descobrir as descobrir_gupy
    descobrir_gupy()

    # 7. Pesquisa vagas de IA no Gupy
    _titulo("7/14 · descobre_gupy_vagas.py — vagas de IA no Gupy")
    from dados_ia_startups.descobre_gupy_vagas import pesquisar
    pesquisar()

    # 8. Analisa site institucional de cada empresa
    _titulo("8/14 · descobre_institucional.py — análise site institucional")
    from dados_ia_startups.descobre_institucional import pesquisar as pesquisar_institucional
    pesquisar_institucional()

    # 9. Pesquisa notícias de IA na News API
    _titulo("9/14 · descobre_imprensa.py — notícias de IA (News API)")
    from dados_ia_startups.descobre_imprensa import pesquisar as pesquisar_imprensa
    pesquisar_imprensa()

    # 10. Classifica artigos Neofeed quanto à menção de IA
    _titulo("10/14 · analisa_neofeed.py — tag neofeed")
    from dados_ia_startups.analisa_neofeed import classificar as classificar_neofeed
    classificar_neofeed()

    # 11. Avalia sinais e grava veredito em avaliacoes_ia
    _titulo("11/14 · filtro_ia.py — veredito de uso de IA")
    from dados_ia_startups.filtro_ia import filtrar as filtrar_ia
    filtrar_ia()

    # 12. Cria linhas em empresas_uso_ia para aprovadas (seed)
    _titulo("12/14 · inicia_aprofundamento.py — seed de aprovadas")
    from dados_startups_selecionadas.inicia_aprofundamento import _seed_aprovadas
    _seed_aprovadas()

    # 13. Atualiza situação de coleta das empresas no banco
    _titulo("13/14 · atualiza_situacao_coleta.py — situação de coleta")
    from interacoes_banco.atualiza_situacao_coleta import atualizar
    atualizar()

    # 14. Gera recomendações de tecnologias NVIDIA via LangGraph
    _titulo("14/14 · inicia_recomendacao.py — recomendações NVIDIA")
    from recomendacao.inicia_recomendacao import rodar
    rodar()

    elapsed = time.time() - inicio
    print(f"\n{'=' * 60}")
    print(f"  Fluxo completo em {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
