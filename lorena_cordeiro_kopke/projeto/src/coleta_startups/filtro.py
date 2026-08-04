from __future__ import annotations
import json
import os
import re
import sys
import time
from pathlib import Path
import spacy
from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

try:
    from agents.extrato_nomes_startups_gemini import extrair_nome_gemini
except ImportError:
    # fallback quando executado diretamente com sys.path apontando para src/
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent / 'agents'))
    from extrato_nomes_startups_gemini import extrair_nome_gemini  # type: ignore[no-redef]

CAMINHO_BRUTOS = str(_RAIZ / 'data/jsons/artigos_nomes_empresas/artigos_brutos.json')
CAMINHO_SAIDA  = str(_RAIZ / 'data/jsons/nomes_empresas/nomes_empresas.json')

MODELO_SPACY = 'pt_core_news_sm'

# Organizações que o NER classifica como ORG mas não são startups-alvo.
DENYLIST: set[str] = {
    'OpenAI', 'Google', 'Meta', 'Apple', 'Amazon', 'Microsoft', 'Nvidia',
    'Tesla', 'Samsung', 'Alphabet', 'SpaceX', 'Twitter', 'X', 'xAI',
    'Stripe', 'Klarna', 'Revolut', 'Figma', 'Perplexity', 'Circle',
    'Andreessen Horowitz', 'SoftBank', 'Goldman Sachs', 'BTG', 'BTG Pactual',
    'Itaú', 'Bradesco', 'Banco do Brasil', 'Caixa', 'Santander',
    'BNDES', 'Finep', 'CVM', 'Banco Central', 'BC',
    'Petrobras', 'XP', 'B3',
    'Kaszek', 'Monashees', 'Sequoia', 'General Atlantic', 'Advent',
    'WhatsApp', 'TikTok', 'Spotify', 'Whatsapp', 'Instagram', 'LinkedIn', 'YouTube', 'Netflix',
    'Brasil', 'México', 'China', 'EUA', 'Europa', 'América Latina',
    'Endeavor', 'WPP', 'Adobe', 'DreamWorks', 'Odontoprev',
    'CVCs', 'IPOs', 'Seleção', 'Startup', 'Startups',
    'Jeff Bezos', 'Sam Altman', 'Elon Musk',
}

# Primeira palavra do título que indica que ele NÃO começa com nome de startup.
BLOCKLIST_INICIO: set[str] = {
    'Na', 'No', 'Em', 'Após', 'Apos', 'O', 'A', 'Os', 'As', 'Um', 'Uma',
    'Por', 'Para', 'Como', 'Quando', 'Se', 'Com', 'Sem', 'Sob', 'Entre',
    'Brasil', 'Sobre', 'Mais', 'Esta', 'Este', 'Estes', 'Estas',
    'Esse', 'Essa', 'Esses', 'Essas', 'Do', 'Da', 'Dos', 'Das',
    'Ao', 'À', 'Nos', 'Nas', 'Num', 'Numa',
    'Pelo', 'Pela', 'Pelos', 'Pelas',
    'Quem', 'Qual', 'Que', 'De',
    'Startup', 'Startups', 'Fintech', 'Healthtech', 'Edtech', 'Agtech',
    'Gestoras', 'Drones', 'Retomada', 'Seleção', 'Boom', 'Alta', 'Crise',
    'Corrida', 'Onda', 'Era', 'Mercado', 'Setor', 'Indústria',
}

_VERBOS = [
    'anuncia', 'anunciam', 'lança', 'lançam', 'levanta', 'levantam',
    'fecha', 'fecham', 'capta', 'captam', 'recebe', 'recebem',
    'expande', 'expandem', 'estreia', 'estreiam', 'vai', 'vão',
    'quer', 'querem', 'busca', 'buscam', 'aposta', 'apostam',
    'cresce', 'crescem', 'contrata', 'contratam', 'demite', 'demitem',
    'projeta', 'projetam', 'prevê', 'preveem', 'atrai', 'atraem',
    'avança', 'avançam', 'acelera', 'aceleram', 'prepara', 'preparam',
    'investe', 'investem', 'adquire', 'adquirem', 'compra', 'compram',
    'vende', 'vendem', 'conquista', 'conquistam', 'dispara', 'disparam',
    'registra', 'registram', 'fatura', 'faturam', 'atinge', 'atingem',
    'supera', 'superam', 'fortalece', 'fortalecem', 'reforça', 'reforçam',
    'amplia', 'ampliam', 'abre', 'abrem', 'firma', 'firmam', 'assina',
    'assinam', 'garante', 'garantem', 'mira', 'miram', 'planeja', 'planejam',
    'negocia', 'negociam', 'integra', 'integram', 'consolida', 'consolidam',
    'monta', 'montam', 'estrutura', 'estruturam', 'sai', 'saem', 'chega',
    'chegam', 'entra', 'entram', 'ganha', 'ganham', 'perde', 'perdem',
    'soma', 'somam', 'dobra', 'dobram', 'eleva', 'elevam', 'reduz',
    'reduzem', 'corta', 'cortam', 'faz', 'fazem', 'traz', 'trazem',
    'passa', 'passam', 'une', 'unem', 'muda', 'mudam', 'vira', 'viram',
    'torna', 'tornam', 'leva', 'levam',
    'cria', 'criam', 'desenvolve', 'desenvolvem', 'oferece', 'oferecem',
    'obtém', 'obtêm', 'consegue', 'conseguem', 'alcança', 'alcançam',
    'ultrapassa', 'ultrapassam', 'completa', 'completam', 'transforma', 'transformam',
    'impulsiona', 'impulsionam', 'monetiza', 'monetizam', 'adota', 'adotam',
    'implementa', 'implementam', 'revela', 'revelam', 'divulga', 'divulgam',
    'confirma', 'confirmam', 'encerra', 'encerram', 'retoma', 'retomam',
    'lidera', 'lideram', 'assume', 'assumem', 'foca', 'focam',
    'escala', 'escalam', 'pivota', 'pivotam', 'cobra', 'cobram',
    'melhora', 'melhoram', 'usa', 'usam', 'alia', 'aliam',
    'testa', 'testam', 'compete', 'competem', 'aprimora', 'aprimoram',
]

_VERBOS_REGEX = re.compile(r'\b(' + '|'.join(_VERBOS) + r')\b', re.IGNORECASE)


def _extrair_via_regex(titulo: str) -> str | None:
    """Fallback: captura o trecho antes do primeiro verbo como candidato a nome."""
    t = titulo.strip()
    primeira = t.split()[0] if t else ''
    if primeira in BLOCKLIST_INICIO:
        return None
    match = _VERBOS_REGEX.search(t)
    if not match:
        return None
    candidato = t[:match.start()].strip().rstrip(',')
    if not candidato or not candidato[0].isupper():
        return None
    return candidato


def _is_valido(nome: str) -> bool:
    if not nome or len(nome) < 3:
        return False
    if nome in DENYLIST:
        return False
    if not nome[0].isupper():
        return False
    if ',' in nome or ':' in nome or '"' in nome:
        return False
    if nome.split()[0] in BLOCKLIST_INICIO:
        return False
    # Descarta frases longas — provavelmente não é um nome de empresa
    if len(nome.split()) > 6:
        return False
    return True


def _salvar(resultado: list[dict], caminho_saida: str) -> None:
    destino = Path(caminho_saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)


def _extrair_nome(titulo: str, nlp: object) -> str | None:
    """Extrai nome de startup: tenta Gemini primeiro, cai em NER+regex se falhar."""
    try:
        nome = extrair_nome_gemini(titulo)
        if nome:
            return nome
    except Exception as exc:
        print(f"\n[aviso] Gemini falhou ({exc}); usando fallback NER+regex", flush=True)

    # Fallback: spaCy NER
    doc = nlp(titulo)
    candidatos = [ent.text.strip() for ent in doc.ents if ent.label_ == 'ORG']
    for c in candidatos:
        c = c.strip().rstrip(',')
        if _is_valido(c):
            return c

    # Fallback final: regex por posição verbal
    return _extrair_via_regex(titulo)


def _urls_ja_no_banco() -> set[str]:
    """Retorna o conjunto de URLs já presentes em nomes_empresas no Supabase."""
    try:
        supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        rows = supabase.table("nomes_empresas").select("url").execute().data
        return {r["url"] for r in rows if r.get("url")}
    except Exception as exc:
        print(f"[aviso] não foi possível consultar URLs do banco: {exc} — processando tudo")
        return set()


def filtrar(
    caminho_json: str = CAMINHO_BRUTOS,
    caminho_saida: str | None = CAMINHO_SAIDA,
    delay_entre_chamadas: float = 1.0,
) -> list[dict]:
    """Lê artigos brutos gerados por coleta_neofeed.py, extrai nomes de startups via
    Gemini API (com fallback spaCy NER + regex), aplica denylist e heurísticas,
    e retorna lista deduplicada.

    Caminho padrão de entrada : data/jsons/artigos_nomes_empresas/artigos_brutos.json
    Caminho padrão de saída   : data/jsons/nomes_empresas/nomes_empresas.json
    delay_entre_chamadas      : pausa em segundos entre chamadas à Gemini API
                                (reduz risco de 429 no tier gratuito)
    """
    nlp = spacy.load(MODELO_SPACY)

    with open(caminho_json, encoding='utf-8') as f:
        artigos = json.load(f)

    urls_existentes = _urls_ja_no_banco()
    if urls_existentes:
        print(f"[info] {len(urls_existentes)} URL(s) já no banco — serão puladas\n")

    total = len(artigos)
    resultado: list[dict] = []
    vistos: set[str] = set()

    for i, artigo in enumerate(artigos, 1):
        titulo = (artigo.get('titulo') or '').strip()
        url = artigo.get('url', '')
        tags = artigo.get('tags', [])
        if not titulo:
            continue
        if '/startups/' not in url:
            print(f"[{i}/{total}] descartado (seção incorreta): {url[:80]}")
            continue
        if url in urls_existentes:
            print(f"[{i}/{total}] já no banco — pulado: {url[:80]}")
            continue

        print(f"[{i}/{total}] {titulo[:80]}", end=' ... ', flush=True)

        nome = _extrair_nome(titulo, nlp)

        if not nome or not _is_valido(nome) or nome in vistos:
            print("descartado")
            if i < total:
                time.sleep(delay_entre_chamadas)
            continue

        vistos.add(nome)
        resultado.append({'startup': nome, 'titulo': titulo, 'url': url, 'tags': tags})
        print(f"→ {nome}")
        if caminho_saida:
            _salvar(resultado, caminho_saida)

        if i < total:
            time.sleep(delay_entre_chamadas)

    if caminho_saida:
        print(f"\n[info] {len(resultado)} startups salvas em {caminho_saida}")

    print(f"\nStartups encontradas ({len(resultado)}):")
    for i, r in enumerate(resultado, 1):
        tag_str = f"  [{', '.join(r['tags'])}]" if r['tags'] else ''
        print(f"{i}. {r['startup']}{tag_str}")

    return resultado


def main() -> None:
    # uso: python filtro.py [caminho_entrada] [caminho_saida]
    entrada = sys.argv[1] if len(sys.argv) > 1 else CAMINHO_BRUTOS
    saida   = sys.argv[2] if len(sys.argv) > 2 else CAMINHO_SAIDA
    filtrar(caminho_json=entrada, caminho_saida=saida)


if __name__ == '__main__':
    main()
