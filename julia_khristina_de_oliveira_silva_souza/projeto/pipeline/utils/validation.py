import gzip
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional
from unicodedata import normalize

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

_CACHE_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / ".." / "data"
_CIDADES_IBGE_CACHE = _CACHE_DIR / "municipios_ibge.json"

_IBGE_API_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"


def validar_formato_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def verificar_mx(dominio: str) -> bool:
    try:
        result = subprocess.run(
            ["nslookup", "-type=mx", dominio],
            capture_output=True, text=True, timeout=5
        )
        return "mail exchanger" in result.stdout.lower()
    except Exception:
        try:
            socket.gethostbyname(dominio)
            return True
        except Exception:
            return False


def validar_email(email: str) -> tuple[bool, str]:
    if not email or not validar_formato_email(email):
        return False, "Formato de email inválido"
    dominio = email.split("@")[1]
    if not verificar_mx(dominio):
        return False, f"Domínio {dominio} não possui registros MX ou não resolve"
    return True, ""


_PREPOSICOES = {"de", "da", "do", "das", "dos", "e"}


def _capitalizar_cidade(nome: str) -> str:
    palavras = nome.strip().split()
    resultado = []
    for i, palavra in enumerate(palavras):
        if i > 0 and palavra.lower() in _PREPOSICOES:
            resultado.append(palavra.lower())
        else:
            resultado.append(palavra[0].upper() + palavra[1:].lower())
    return " ".join(resultado)


def normalizar_cidade(nome: str) -> str:
    if not nome:
        return nome
    nome = nome.strip()
    nome = re.sub(r"\s*[–—-]\s*(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)$", r" - \1", nome)
    nome = re.sub(r"\s+", " ", nome)
    parts = nome.split(" - ")
    if len(parts) == 2:
        cidade = _capitalizar_cidade(parts[0].strip())
        uf = parts[1].strip().upper()
        if re.match(r"^[A-Z]{2}$", uf):
            return f"{cidade} - {uf}"
    return _capitalizar_cidade(nome)


def _baixar_cidades_ibge() -> list[dict]:
    try:
        import urllib.request
        req = urllib.request.Request(
            _IBGE_API_URL,
            headers={"User-Agent": "NVIDIA-Startup-Radar/1.0",
                     "Accept-Encoding": "gzip, deflate"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            dados = json.loads(raw.decode("utf-8"))
        municipios = []
        for m in dados:
            nome = m.get("nome", "")
            mr = m.get("microrregiao")
            uf_obj = None
            if mr and isinstance(mr, dict):
                meso = mr.get("mesorregiao")
                if meso and isinstance(meso, dict):
                    uf_obj = meso.get("UF")
            if not uf_obj:
                ri = m.get("regiao-imediata")
                if ri and isinstance(ri, dict):
                    rii = ri.get("regiao-intermediaria")
                    if rii and isinstance(rii, dict):
                        uf_obj = rii.get("UF")
            sigla = uf_obj.get("sigla", "") if uf_obj else ""
            if nome and sigla:
                municipios.append({
                    "nome": nome,
                    "uf": sigla,
                    "nome_normalizado": normalize("NFKD", nome).encode("ASCII", "ignore").decode().lower()
                })
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CIDADES_IBGE_CACHE, "w", encoding="utf-8") as f:
            json.dump(municipios, f, ensure_ascii=False)
        return municipios
    except Exception as e:
        print(f"[Validation] Erro ao baixar cidades IBGE: {e}")
        return []


def carregar_cidades_ibge() -> list[dict]:
    if _CIDADES_IBGE_CACHE.exists():
        try:
            with open(_CIDADES_IBGE_CACHE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    cidades = _baixar_cidades_ibge()
    if cidades:
        return cidades
    return []


_MUNICIPIOS_IBGE = None


def _get_municipios() -> list[dict]:
    global _MUNICIPIOS_IBGE
    if _MUNICIPIOS_IBGE is None:
        _MUNICIPIOS_IBGE = carregar_cidades_ibge()
    return _MUNICIPIOS_IBGE


def validar_cidade(cidade_str: str) -> tuple[bool, str]:
    if not cidade_str:
        return False, "Cidade não informada"
    normalizada = normalizar_cidade(cidade_str)
    municipios = _get_municipios()
    if not municipios:
        return True, normalizada
    parts = normalizada.split(" - ")
    if len(parts) != 2:
        return False, f"Formato inválido. Use 'Cidade - UF' (ex: São Paulo - SP)"
    nome_cidade, uf = parts
    nome_key = normalize("NFKD", nome_cidade).encode("ASCII", "ignore").decode().lower()
    for m in municipios:
        if m["nome_normalizado"] == nome_key and m["uf"] == uf:
            return True, normalizada
    return False, f"Município '{nome_cidade} - {uf}' não encontrado na base do IBGE"


def normalizar_email_extraido(email: str) -> Optional[str]:
    email = email.strip().lower()
    if validar_formato_email(email):
        return email
    return None
