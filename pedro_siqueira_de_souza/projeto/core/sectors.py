"""Taxonomia canônica de setores — usada pela página Analytics.

Problema: o Extractor preenche `sector` como TEXTO LIVRE (ex.: "agtech",
"fintech", "finanças", ou NULL). Agregar isso direto no banco fazia cada string
crua virar um "setor" próprio — daí o top de setores vinha com `'—'` (nulos) e
jargões soltos ("agtech") em vez de nomes concretos.

Aqui mora a LISTA FIXA de setores (concretos, em PT) e o mapeamento de cada
string crua para um deles por palavra-chave. O que não casa cai em "Outros".
Assim a startup entra num bucket conhecido em vez de criar um setor novo.

Decisão de design: a taxonomia é aplicada na AGREGAÇÃO (analytics), não na
escrita — o banco continua guardando o texto cru (auditável), e a página mostra
os buckets canônicos. Se um dia quisermos travar o Extractor nessa mesma lista,
ela já está centralizada aqui.
"""
from __future__ import annotations

OUTROS = "Outros"

# Ordem = prioridade de checagem: o primeiro setor cujo alguma palavra-chave
# aparecer na string crua vence. Por isso os mais específicos vêm antes dos
# genéricos (ex.: "foodtech" cai em Varejo, não em Software por conter "tech").
SECTOR_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Finanças", ("fintech", "finan", "pagament", "payment", "banc", "bank",
                  "crédit", "credit", "seguro", "insurtech", "insurance",
                  "investiment", "wealth", "contábil", "contabil", "cripto",
                  "crypto", "lending", "empréstim")),
    ("Saúde", ("health", "saúde", "saude", "medic", "médic", "hospital",
               "clínic", "clinic", "biotech", "pharma", "farma", "odonto",
               "mental", "wellness", "bem-estar")),
    ("Agronegócio", ("agro", "agtech", "agri", "agricult", "rural", "pecuár",
                     "pecuar", "fazend", "lavoura", "safra")),
    ("Varejo & E-commerce", ("varejo", "retail", "ecommerce", "e-commerce",
                             "comérci", "comerci", "marketplace", "consum",
                             "foodtech", "restaurant", "moda", "fashion",
                             "beleza", "loja")),
    ("Educação", ("educ", "edtech", "ensino", "escola", "aprend", "learning",
                  "curso", "treinament")),
    ("Logística", ("logístic", "logistic", "logtech", "supply", "frete",
                   "entrega", "delivery", "last mile", "armazé", "armazem",
                   "cadeia de suprim")),
    ("Jurídico", ("legal", "jurídic", "juridic", "lawtech", "advoc", "direito",
                  "compliance", "regtech")),
    ("Recursos Humanos", ("hrtech", "recursos humanos", "human resources",
                          "recrutament", "talent", "people", " rh ", "rh,",
                          "gestão de pessoas")),
    ("Indústria", ("indústr", "industr", "indtech", "manufatur", "manufactur",
                   "fábric", "fabric", "hardware", "maker", "semicond",
                   "semiconductor", "chip", "automação industrial",
                   "iot industrial")),
    ("Energia", ("energ", "energy", "cleantech", "solar", "petró", "petro",
                 "óleo e gás", "oleo e gas", "gás natural", "sustentab",
                 "climate", "carbon", "renová", "renova")),
    ("Mídia & Marketing", ("marketing", "martech", "mídia", "midia", "adtech",
                           "publicid", "advertis", "conteúdo", "conteudo",
                           "influenc", "social media", "creator")),
    ("Mobilidade", ("mobilidad", "mobility", "automotiv", "veícul", "veicul",
                    "ride-hail", "micromobilidad", "urban mobility")),
    ("Imobiliário/Construção", ("imobili", "real estate", "proptech",
                                "construt", "construc", "construction",
                                "building", "incorporad")),
    ("Software/SaaS", ("saas", "software", "devtool", "cloud", "cibersegur",
                       "cybersec", "ciberseg", "segurança da informação",
                       "data analytics", "machine learning", "inteligência "
                       "artificial", "no-code", "nocode", "low-code", "api ",
                       "infraestrutura de dados", "crm", "erp",
                       # catch-all: por vir POR ÚLTIMO, só pega "tech" genérico
                       # — os verticais (fintech, agtech, edtech...) já casaram
                       # com seus setores específicos acima.
                       "tech")),
]

# Ordem de exibição/declaração da taxonomia (útil se o Extractor for travado).
CANONICAL_SECTORS: list[str] = [nome for nome, _ in SECTOR_KEYWORDS] + [OUTROS]


def canonical_sector(raw: str | None) -> str:
    """Mapeia um setor cru (texto livre/NULL) para um setor canônico da lista.

    Casamento por substring, case-insensitive. Sem match (ou entrada vazia) =>
    "Outros" — a startup nunca some da contagem nem cria um setor novo.
    """
    if not raw:
        return OUTROS
    alvo = raw.strip().lower()
    if not alvo:
        return OUTROS
    for nome, palavras in SECTOR_KEYWORDS:
        if any(p in alvo for p in palavras):
            return nome
    return OUTROS


def bucket_sectors(raw_counts: list[dict], limit: int = 8) -> list[dict]:
    """Dobra contagens cruas por setor numa taxonomia canônica.

    Entrada: linhas `{"sector": <texto cru|None>, "count": <int>}` (o GROUP BY
    cru do banco). Saída: `{"sector": <canônico>, "count": <int>}` somado por
    bucket, ordenado por contagem desc e limitado a `limit` setores.
    """
    somas: dict[str, int] = {}
    for linha in raw_counts:
        bucket = canonical_sector(linha.get("sector"))
        somas[bucket] = somas.get(bucket, 0) + int(linha.get("count", 0))

    ordenado = sorted(somas.items(), key=lambda kv: kv[1], reverse=True)
    return [{"sector": nome, "count": n} for nome, n in ordenado[:limit] if n > 0]
