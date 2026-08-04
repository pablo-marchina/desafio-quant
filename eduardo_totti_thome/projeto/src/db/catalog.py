"""Catálogo de startups: uma seed curada + as já analisadas (persistidas).

Serve para o frontend oferecer um SELETOR de startups — o usuário escolhe uma da
lista, sem precisar digitar nome e URL toda vez. Combina uma lista curada de
startups brasileiras de IA com as que já foram analisadas e salvas no Postgres
(marcando quais já têm análise e o nível obtido).
"""

from __future__ import annotations

# Seed curada de startups brasileiras (nome, URL). Ponto de partida do catálogo;
# expansível à vontade. URLs verificadas ao longo do desenvolvimento.
SEED_STARTUPS: list[tuple[str, str]] = [
    ("Maritaca AI", "https://www.maritaca.ai/"),
    ("Hand Talk", "https://www.handtalk.me/"),
    ("Tractian", "https://tractian.com.br/"),
    ("Gupy", "https://www.gupy.io/"),
    ("Fintalk", "https://www.fintalk.ai/"),
    ("Semantix", "https://www.semantix.ai/"),
    ("Zenvia", "https://www.zenvia.com/"),
    ("Portal Telemedicina", "https://portaltelemedicina.com.br/"),
    ("Blip", "https://www.blip.ai/"),
    # --- expansão da base (URLs verificadas por coleta) ---
    ("Kunumi", "https://kunumi.com"),
    ("ClearSale", "https://www.clear.sale"),
    ("Neurotech", "https://www.neurotech.com.br"),
    ("Idwall", "https://idwall.co"),
    ("Datarisk", "https://www.datarisk.io"),
    ("Birdie", "https://birdie.ai"),
    ("Huggy", "https://www.huggy.io"),
    ("Weni", "https://weni.ai"),
    ("Aquarela", "https://aquare.la"),
    ("Meetime", "https://www.meetime.com.br"),
    ("CI&T", "https://ciandt.com"),
    ("Pipefy", "https://www.pipefy.com"),
    ("Cortex Intelligence", "https://www.cortex-intelligence.com"),
    ("Nubank", "https://nubank.com.br"),
    ("QuintoAndar", "https://www.quintoandar.com.br"),
    ("Memed", "https://memed.com.br"),
    ("Robbu", "https://www.robbu.global"),
    ("Zup", "https://www.zup.com.br"),
]


def get_catalog() -> list[dict]:
    """Devolve o catálogo combinado, ordenado por nome.

    Cada item: {startup_name, url, analisada (bool), level, level_name}.
    Começa da seed; as startups já analisadas (do banco) sobrescrevem/entram
    marcadas como analisada=True. Se o banco estiver indisponível, usa só a seed.
    """
    por_nome: dict[str, dict] = {}
    for nome, url in SEED_STARTUPS:
        por_nome[nome] = {
            "startup_name": nome,
            "url": url,
            "analisada": False,
            "level": None,
            "level_name": "",
        }

    # Junta com as análises já salvas (marca analisada=True e traz o nível).
    try:
        from db.repository import list_analyses

        for a in list_analyses(limit=200):
            nome = a["startup_name"]
            base = por_nome.get(nome, {})
            por_nome[nome] = {
                "startup_name": nome,
                "url": a.get("url") or base.get("url", ""),
                "analisada": True,
                "level": a.get("level"),
                "level_name": a.get("level_name") or "",
            }
    except Exception:  # noqa: BLE001 — banco fora do ar: cai pra só a seed
        pass

    return sorted(por_nome.values(), key=lambda s: s["startup_name"].lower())
