# `agents/` — Orquestração multi-agente (LangGraph)

Cada agente do NVISION vive aqui, um conceito por arquivo. A orquestração
usa **LangGraph** (Entregável 2).

## Arquivos atuais

| Arquivo | O quê | Tipo | Guia |
|---|---|---|---|
| `state.py` | `RadarState` — o estado tipado que trafega entre os nós. | — | — |
| `search_planner.py` | Nó 1: LLM com saída estruturada (`SearchPlan`), escolhe termos de busca e fontes dentre o catálogo fixo. | LLM | — |
| `scraper.py` | Nó 2: lê `sources` e descobre startups via adapters por fonte (em `scraping/`). Agnóstico de fonte, erro por fonte. | regra | [scraper.md](../artefatos/scraper.md) |
| `enricher.py` | Nó 3: para quem tem `detail_url`, coleta o texto principal da página (trafilatura). Erro por item. | regra | — |
| `extractor.py` | Nó 4: texto bruto → `StructuredStartup` (produto, setor, stack, `ai_signals`). Dois schemas; pula o LLM sem conteúdo. | LLM | [extractor.md](../artefatos/extractor.md) |
| `classifier.py` | Nó 5: `StructuredStartup` → rótulo AI-native / AI-enabled / Non-AI + justificativa e confiança. | LLM | [classifier.md](../artefatos/classifier.md) |
| `evidence_validator.py` | Nó 6: valida a confiança por **regras** e roteia o **ciclo** (recoleta ou END). | regra | [evidence_validator.md](../artefatos/evidence_validator.md) |
| `graph.py` | Monta o grafo de **6 nós** com a **aresta condicional** (`add_conditional_edges`) no `evidence_validator`. | — | — |

## Pipeline atual (com o primeiro ciclo)

```
START → search_planner → scraper → enricher → extractor → classifier
      → evidence_validator ──(confiança baixa, com orçamento)──> scraper  (recoleta)
                           \──(ok / sem orçamento)──> END
```

## Próximos agentes (roadmap)

`... → evidence_validator → nvidia_rag → recommendation → briefing`
(Entregáveis 3–4: RAG NVIDIA com reranking e motor de recomendação).

## O que aprendi

- `with_structured_output` força o LLM a devolver algo compatível com um
  schema Pydantic, eliminando parsing manual de texto livre.
- Testar código que chama LLM sem gastar dinheiro/rede: o nó recebe o LLM
  via uma referência de módulo (`get_llm`) que pode ser trocada por um
  `FakeLLM` nos testes via `monkeypatch` — sem mudar a assinatura da função
  nem arriscar conflito com a injeção automática de `config` do LangGraph.
- **Separar o que o LLM infere do que o sistema já sabe** (dois schemas no
  Extractor: `name`/`extraction_basis` são do nó, não do modelo) é uma defesa
  barata contra alucinação.
- **Pular o LLM quando não há evidência** (Extractor/Classifier no caminho
  `metadata`) é o jeito mais honesto de "não inventar dados".
- **Nem todo agente precisa de LLM**: o Evidence Validator valida por regras
  explícitas — transparente, determinístico e testável sem `FakeLLM`.
- **Todo ciclo no grafo precisa de uma guarda de terminação** no estado
  (`validation_attempts < MAX_ATTEMPTS`), senão o loop roda para sempre. A
  função de roteamento (`add_conditional_edges`) só *lê* o estado e decide o
  caminho; quem *escreve* é o nó.
