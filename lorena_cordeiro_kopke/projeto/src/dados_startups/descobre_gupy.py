from __future__ import annotations

import json
import os
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from supabase import create_client

_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; pesquisa-academica/1.0)"


def _slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().replace("&", "e").replace("/", " ")
    # remove qualquer char que não seja letra, número ou espaço
    texto = "".join(c if c.isalnum() or c == " " else " " for c in texto)
    return texto.strip()


def _candidatos(nome: str) -> list[str]:
    base = _slugify(nome)
    palavras = base.split()

    candidatos: list[str] = []

    # nome completo com hífen e sem espaço
    if len(palavras) > 1:
        candidatos.append("-".join(palavras))
        candidatos.append("".join(palavras))

    # só a primeira palavra (marca mais curta)
    candidatos.append(palavras[0])

    # sigla (iniciais de cada palavra com 3+ letras)
    sigla = "".join(p[0] for p in palavras if len(p) >= 3)
    if len(sigla) >= 2:
        candidatos.append(sigla)

    # primeira palavra + segunda (sem o resto)
    if len(palavras) >= 3:
        candidatos.append("-".join(palavras[:2]))
        candidatos.append("".join(palavras[:2]))

    return list(dict.fromkeys(candidatos))  # dedup mantendo ordem


def _provar_subdominio(slug: str, timeout: int = 5, debug: bool = False) -> bool:
    url = f"https://{slug}.gupy.io"
    try:
        r = _SESSION.get(url, timeout=timeout, allow_redirects=True)
        destino_final = r.url.rstrip("/")
        redirecionou_para_raiz = destino_final in (
            "https://www.gupy.io",
            "https://gupy.io",
        )
        if debug:
            print(f"      [debug] {url} → {destino_final}  status={r.status_code}")
        return r.status_code == 200 and not redirecionou_para_raiz
    except requests.RequestException as e:
        if debug:
            print(f"      [debug] {url} → erro: {e}")
        return False


_SAIDA = _RAIZ / "data" / "jsons" / "gupy_empresas"


def descobrir(debug: bool = False, nome: str | None = None) -> None:
    query = supabase.table("empresas").select("id, nome, gupy_subdominio")
    if nome:
        query = query.eq("nome", nome)
    rows = query.execute().data

    pendentes = [r for r in rows if not r.get("gupy_subdominio")]
    print(f"[info] {len(pendentes)} empresa(s) sem gupy_subdominio registrado")

    encontrados: list[dict] = []
    nao_encontrados: list[str] = []

    for empresa in pendentes:
        nome = empresa["nome"]
        candidatos = _candidatos(nome)
        print(f"\n[→] {nome}  |  candidatos: {candidatos}")

        achou = False
        for slug in candidatos:
            time.sleep(0.4)
            if _provar_subdominio(slug, debug=debug):
                print(f"    [✓] encontrado: {slug}.gupy.io")
                registro = {
                    "empresa_id": empresa["id"],
                    "nome": nome,
                    "gupy_subdominio": slug,
                    "gupy_url": f"https://{slug}.gupy.io",
                    "descoberto_em": datetime.now(timezone.utc).isoformat(),
                }
                encontrados.append(registro)
                supabase.table("empresas").update(
                        {"gupy_subdominio": slug}
                    ).eq("id", empresa["id"]).execute()
                achou = True
                break

        if not achou:
            print(f"    [✗] nenhum candidato confirmado")
            nao_encontrados.append(nome)

    if encontrados:
        _SAIDA.mkdir(parents=True, exist_ok=True)
        caminho = _SAIDA / "gupy_encontrados.json"
        existentes: list[dict] = []
        if caminho.exists():
            existentes = json.loads(caminho.read_text(encoding="utf-8"))
        ids_existentes = {r["empresa_id"] for r in existentes}
        novos = [r for r in encontrados if r["empresa_id"] not in ids_existentes]
        caminho.write_text(
            json.dumps(existentes + novos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[json] {len(novos)} registro(s) novo(s) salvo(s) em {caminho}")

    print(f"\n[resumo] encontrados: {len(encontrados)} / {len(pendentes)}")
    if nao_encontrados:
        print("[revisão manual necessária]:")
        for n in nao_encontrados:
            print(f"  - {n}")


if __name__ == "__main__":
    import sys
    debug = "--debug" in sys.argv
    descobrir(debug=debug)
