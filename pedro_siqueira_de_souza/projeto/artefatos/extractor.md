# Extractor Agent — guia didático

> Como o NVISION transforma texto bruto de uma startup em dados estruturados,
> por que foi construído assim e o que cada decisão ensina. Documento de
> aprendizado: o foco é **expor a mecânica**, não escondê-la.

---

## 1. Onde o Extractor entra no pipeline

O Extractor é a **quarta estação** do grafo, logo depois do Enricher:

```
query → search_planner → scraper → enricher → extractor → (classifier → ...)
```

- **Recebe** do estado (`RadarState`): `raw_startups` — startups cruas, cada uma
  um `RawStartup` com `name`, `sector?`, `detail_url?` e, quando o Enricher
  conseguiu, `content` (o texto principal da página, já limpo pelo trafilatura).
- **Entrega** ao estado: `extracted_startups` — uma lista de `StructuredStartup`,
  com produto, setor, estágio, funding, stack e — o mais importante — os
  **sinais de IA** (`ai_signals`) que o Classifier vai usar para rotular.

O Extractor é a primeira estação que **lê o texto e o interpreta**. Scraper e
Enricher só coletam; aqui começa o entendimento.

---

## 2. A ferramenta: LLM com saída estruturada

O Extractor usa um LLM via `with_structured_output(schema)` — o **mesmo padrão**
do Search Planner. Em vez de pedir texto livre e fazer parsing manual (frágil),
forçamos o modelo a devolver algo que já bate com um schema Pydantic.

```python
structured_llm = get_llm().with_structured_output(_ExtractedFields)
fields = structured_llm.invoke(prompt)   # já é um _ExtractedFields validado
```

> **Por que `get_llm()` em runtime, e não no import?** Para os testes poderem
> trocar essa "costura" por um `FakeLLM` via `monkeypatch` — sem rede, sem
> chave de API. Mesma ideia do Search Planner.

---

## 3. A decisão central: **dois schemas**

O detalhe de design mais importante do Extractor é separar o que o LLM produz
do que o nó armazena.

```python
class _ExtractedFields(BaseModel):   # ← o LLM preenche
    description: str | None = None
    sector: str | None = None
    stage: str | None = None
    funding: str | None = None
    tech_stack: list[str] = []
    ai_signals: list[str] = []

class StructuredStartup(BaseModel):  # ← o nó armazena
    name: str                        #   identidade — vem do RawStartup
    description: str | None = None
    ...
    ai_signals: list[str] = []
    extraction_basis: Literal["content", "metadata"]  # de onde veio a extração
```

**Por quê:** `name` e `extraction_basis` são **fatos que o nó conhece**, não
opiniões do LLM. O nome vem do RawStartup (não se inventa o nome de uma
empresa); a base de extração é algo que o código sabe (havia `content` ou não).
Tirá-los do schema do LLM elimina uma classe inteira de alucinação.

> **Lição:** separar "o que o modelo infere" de "o que o sistema já sabe" é uma
> das defesas mais baratas contra alucinação. O nó costura os dois.

---

## 4. `content=None`: **pular o LLM** (honestidade > completude)

Nem toda startup chega com `content`: quem não tinha `detail_url`, ou cuja
página falhou, chega só com `name` (e talvez `sector`). O que fazer?

A decisão: **não chamar o LLM**. Montamos um `StructuredStartup` mínimo a partir
do que sabemos, com `extraction_basis="metadata"`.

```python
def _so_metadata(name, sector):
    return StructuredStartup(name=name, sector=sector, extraction_basis="metadata")
```

**Por quê:** sem texto, perguntar ao LLM "o que essa empresa faz?" só com o nome
**convida alucinação**. O jeito mais honesto de cumprir o "não inventar dados"
é **não perguntar**. Bônus: é mais barato e trivial de testar
(esse caminho nem toca a costura `get_llm`).

> Contraste com o caminho normal: quem tem `content` vai ao LLM e volta com
> `extraction_basis="content"`. Esse campo vira um **sinal de confiança** que o
> Evidence Validator usa depois.

---

## 5. Disciplina de erro: por-startup, nunca em lote

O Extractor faz **uma chamada de LLM por startup**, dentro de um `try/except`:

```python
for rs in raw_startups:
    if not content:
        ... _so_metadata(); continue
    try:
        fields = _extrair_campos(structured_llm, name, content)
        ... StructuredStartup(extraction_basis="content")
    except Exception:
        logger.exception(...)
        ... _so_metadata()   # fallback: não perde a startup
```

Duas decisões herdadas do Scraper/Enricher ("tratamento de erro
explícito"):

- **Erro isolado por item.** Uma startup que estoura o LLM vira fallback
  metadata + log; as demais seguem. Em lote, um erro perderia tudo.
- **Contexto focado.** Uma startup por chamada = sem contaminação de contexto
  entre empresas, prompt menor, mais barato de depurar.

O custo (mais chamadas) é o trade-off consciente; **batching** fica anotado como
otimização futura. Detalhe: o `structured_llm` é instanciado
**preguiçosamente** — startups só-metadata nunca pagam o custo de criar o LLM.

---

## 6. O coração: `ai_signals`

De todos os campos, `ai_signals` é o que justifica o agente existir. São
**evidências textuais** de que a startup usa ou desenvolve IA — trechos como
"modelos próprios de ML", "assistente com LLM", "visão computacional".

O prompt é explícito: cada item deve estar **ancorado no texto**; se não houver
menção a IA, a lista volta vazia. Isso porque o Classifier (próximo da fila)
decide AI-native / AI-enabled / Non-AI **olhando esses sinais** — e o Evidence
Validator depois trata "rótulo de IA com `ai_signals` vazio" como inconsistência.

> A qualidade do `ai_signals` define a qualidade de tudo que vem depois. Por isso
> a regra anti-alucinação é tão dura aqui.

---

## 7. Como testar

```bash
uv run pytest tests/test_extractor.py -v
```

Os testes são **100% offline**, espelhando o padrão do Search Planner: um
`FakeLLM` cujo `with_structured_output` devolve sempre um `_ExtractedFields`
fixo, plugado via `monkeypatch.setattr("agents.extractor.get_llm", ...)`.

Casos cobertos:

| Teste | O que prova |
|---|---|
| conteúdo → estruturado | campos do LLM aparecem; `name` vem do RawStartup; `extraction_basis="content"` |
| `content=None` → metadata | **não chama o LLM**; `ai_signals=[]`; `extraction_basis="metadata"` |
| falha isolada por item | startup que estoura vira fallback; as demais sobrevivem |
| não-mutação | o dict original do estado não ganha chaves novas |

---

## 8. Limitações conhecidas do v1 (trabalho futuro)

- **Uma chamada por startup.** Simples e robusto, mas custa mais. Batching com um
  schema-wrapper de lista é a evolução natural quando o volume crescer.
- **Recall depende do `content`.** Se o Enricher não coletou a página, a startup
  fica só-metadata e quase tudo vem vazio — coberto de propósito, mas é um teto.
- **Sem persistência.** `extracted_startups` vive no `RadarState` (memória);
  gravar no PostgreSQL é passo das próximas semanas.
- **`sector` normalizado é livre.** O LLM normaliza ("fintech", "healthtech"),
  mas sem um vocabulário fechado — taxonomia controlada fica para depois.

---

## 9. Resumo de uma frase

> O Extractor transforma texto bruto em `StructuredStartup` via LLM com saída
> estruturada, separando o que o modelo infere do que o sistema já sabe
> (dois schemas), pulando o LLM quando não há texto para não inventar, e
> isolando erro por startup — tudo a serviço de extrair bons `ai_signals`.
