from __future__ import annotations

import json
import os
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; pesquisa-academica/1.0)"

_TLDS = [".com.br", ".com", ".io", ".ai", ".tech", ".co"]

# Domínios conhecidos de estacionamento/registro — confirmam que não há site real
_PARKING = {
    "godaddy.com", "uol.com.br", "registro.br", "locaweb.com.br",
    "hostgator.com.br", "kinghost.com.br", "sedoparking.com",
    "parkingcrew.net", "dan.com", "hugedomains.com",
}

# Domínios que existem mas pertencem a outra empresa — nunca devem ser aceitos
_DOMINIOS_ERRADOS = {
    "segura.com.br",  # imobiliária em Canoas, não a startup Segura
    "btg.com", # banco BTG Pactual, não a startup BTG
    "daki.com",  # empresa de logística, não a startup Daki
    "neuralmed.com",  # empresa de saúde, não a startup NeuralMed
    "digibee.com.br",  # empresa de integração, não a startup Digibee
    "loggi.com.br",  # empresa de logística, não a startup Loggi
    "btg.io",  # empresa de tecnologia, não a startup BTG
    "segura.com", # empresa de seguros, não a startup Segura
    "fintalk.com.br",  # empresa de fintech, não a startup Fintalk
    "fintalk.com",  # empresa de fintech, não a startup Fintalk
}


def _slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().replace("&", "e").replace("/", " ")
    texto = "".join(c if c.isalnum() or c == " " else " " for c in texto)
    return texto.strip()


def _extrair_tld_embutido(nome: str) -> str | None:
    """Detecta se o nome já termina com um TLD conhecido (ex: 'Segura.ai' → 'segura.ai')."""
    nome_lower = nome.lower().strip()
    for tld in _TLDS:
        sufixo = tld  # ex: ".ai"
        if nome_lower.endswith(sufixo):
            base = nome_lower[: -len(sufixo)]
            base = "".join(c for c in base if c.isalnum() or c == "-")
            if base:
                return base + sufixo
    return None


def _candidatos(nome: str) -> list[str]:
    candidatos: list[str] = []

    # Se o nome já carrega um TLD (ex: "Segura.ai"), esse domínio vai na frente
    embutido = _extrair_tld_embutido(nome)
    if embutido:
        candidatos.append(embutido)

    base = _slugify(nome)
    palavras = base.split()

    slugs: list[str] = []

    if len(palavras) > 1:
        slugs.append("-".join(palavras))
        slugs.append("".join(palavras))

    slugs.append(palavras[0])

    sigla = "".join(p[0] for p in palavras if len(p) >= 3)
    if len(sigla) >= 2:
        slugs.append(sigla)

    if len(palavras) >= 3:
        slugs.append("-".join(palavras[:2]))
        slugs.append("".join(palavras[:2]))

    slugs = list(dict.fromkeys(slugs))

    for slug in slugs:
        for tld in _TLDS:
            candidato = slug + tld
            if candidato not in candidatos:
                candidatos.append(candidato)

    return candidatos


def _is_parking(url_final: str) -> bool:
    host = urlparse(url_final).netloc.lower().lstrip("www.")
    return any(host == p or host.endswith("." + p) for p in _PARKING)


def _is_dominio_errado(dominio: str) -> bool:
    return dominio.lstrip("www.") in _DOMINIOS_ERRADOS


def _provar_dominio(dominio: str, timeout: int = 6, debug: bool = False) -> bool:
    if _is_dominio_errado(dominio):
        if debug:
            print(f"      [debug] {dominio} → bloqueado (domínio errado conhecido)")
        return False

    url = f"https://{dominio}"
    try:
        r = _SESSION.get(url, timeout=timeout, allow_redirects=True)
        url_final = r.url.rstrip("/")
        content_type = r.headers.get("Content-Type", "")

        eh_parking = _is_parking(url_final)
        eh_html = "text/html" in content_type

        if debug:
            print(
                f"      [debug] {url} → {url_final}"
                f"  status={r.status_code}"
                f"  html={eh_html}"
                f"  parking={eh_parking}"
            )

        return r.status_code == 200 and eh_html and not eh_parking

    except requests.RequestException as e:
        if debug:
            print(f"      [debug] {url} → erro: {e}")
        return False


def _normalizar_dominio(url_final: str) -> str:
    """Extrai apenas o apex domain da URL final após redirecionamentos."""
    host = urlparse(url_final).netloc.lower().lstrip("www.")
    return host


_SAIDA = _RAIZ / "data" / "jsons" / "dominio_empresas"
_APENAS_JSON = False


def descobrir(debug: bool = False, nome: str | None = None) -> None:
    query = supabase.table("empresas").select("id, nome, dominio")
    if nome:
        query = query.eq("nome", nome)
    rows = query.execute().data

    pendentes = [r for r in rows if not r.get("dominio")]
    print(f"[info] {len(pendentes)} empresa(s) sem dominio registrado")

    encontrados: list[dict] = []
    nao_encontrados: list[str] = []

    for empresa in pendentes:
        nome = empresa["nome"]
        candidatos = _candidatos(nome)
        print(f"\n[→] {nome}  |  {len(candidatos)} candidato(s) a testar")

        achou = False
        for dominio in candidatos:
            time.sleep(0.4)
            if _provar_dominio(dominio, debug=debug):
                print(f"    [✓] encontrado: {dominio}")
                registro = {
                    "empresa_id": empresa["id"],
                    "nome": nome,
                    "dominio": dominio,
                    "descoberto_em": datetime.now(timezone.utc).isoformat(),
                }
                encontrados.append(registro)
                if not _APENAS_JSON:
                    supabase.table("empresas").update(
                        {"dominio": dominio}
                    ).eq("id", empresa["id"]).execute()
                achou = True
                break

        if not achou:
            print(f"    [✗] nenhum candidato confirmado")
            nao_encontrados.append(nome)

    if encontrados:
        _SAIDA.mkdir(parents=True, exist_ok=True)
        caminho = _SAIDA / "dominios_encontrados.json"
        existentes: list[dict] = []
        if caminho.exists():
            existentes = json.loads(caminho.read_text(encoding="utf-8"))
        ids_existentes = {r["empresa_id"] for r in existentes}
        novos = [r for r in encontrados if r["empresa_id"] not in ids_existentes]
        caminho.write_text(
            json.dumps(existentes + novos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[json] {len(novos)} registro(s) salvo(s) em {caminho}")
        if _APENAS_JSON:
            print("[aviso] _APENAS_JSON=True — Supabase não foi atualizado")

    print(f"\n[resumo] encontrados: {len(encontrados)} / {len(pendentes)}")
    if nao_encontrados:
        print("[revisão manual necessária]:")
        for n in nao_encontrados:
            print(f"  - {n}")


if __name__ == "__main__":
    import sys
    debug = "--debug" in sys.argv
    descobrir(debug=debug)
