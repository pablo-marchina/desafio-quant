# Plataforma Multi-Agente de Recomendação NVIDIA

## Visão geral

Esta parte do projeto é responsável por receber o perfil de uma startup e produzir uma recomendação completa de tecnologias NVIDIA — não apenas uma lista de nomes, mas uma explicação contextualizada, uma síntese para o CEO, um roadmap de adoção em 30/60/90 dias e um kit de início prático.

O pipeline é implementado como um **grafo de estados** com LangGraph. O grafo executa quatro LLMs em sequência, cada um com audiência e responsabilidade distintas, sobre uma base de conhecimento NVIDIA indexada no Qdrant.

O ponto de entrada é `src/recomendacao/inicia_recomendacao.py`, que verifica quais empresas são elegíveis e invoca o grafo para cada uma.

---

## Arquivos

```
src/recomendacao/
├── inicia_recomendacao.py        — entry point; itera sobre empresas elegíveis e invoca o grafo
└── verifica_situacao_coleta.py   — filtra empresas com perfil completo e situação adequada

src/agents/extras/
├── graph.py      — monta, conecta e compila o grafo
├── nodes.py      — implementação de todos os nós e funções de roteamento
├── state.py      — TypedDict EstadoRecomendacao (contrato do estado compartilhado)
├── prompts.py    — prompts dos 4 agentes LLM
└── gemini.py     — wrapper do Gemini com retry exponencial e singleton thread-safe

src/rag/
├── buscador.py   — busca vetorial no Qdrant com filtros de metadata
├── reranker.py   — cross-encoder multilingual que reordena os candidatos da busca
├── embedding.py  — geração de embeddings via Gemini gemini-embedding-001
└── indexador.py  — chunking e indexação de documentos JSON no Qdrant
```

---

## Como executar

> **Primeira execução:** o Qdrant precisa estar rodando e a base de conhecimento indexada antes de rodar o pipeline. Siga o setup completo em [README.md](../README.md).

```bash
# Todas as empresas elegíveis
python src/recomendacao/inicia_recomendacao.py

# Uma empresa específica
python src/recomendacao/inicia_recomendacao.py --empresa-id 42

# Reprocessar mesmo que já exista resultado
python src/recomendacao/inicia_recomendacao.py --empresa-id 42 --forcar
```

O script verifica quais empresas já têm `explicacao` preenchida no banco e pula as que já foram processadas, a menos que `--forcar` seja passado.

---

## Estado compartilhado

O grafo usa um `TypedDict` chamado `EstadoRecomendacao` (definido em `state.py`) que trafega entre todos os nós. Cada nó retorna apenas as chaves que alterou — o LangGraph faz merge no estado existente.

```
EstadoRecomendacao
│
├── empresa_id          int          — entrada; identificador da startup
├── perfil              dict         — dados carregados do Supabase (setor, produto, ia_tipo, etc.)
├── query               str          — frase de busca semântica gerada a partir do perfil
│
├── chunks              List[dict]   — chunks completos (texto + metadata) retornados pelo Qdrant
├── chunks_refs         List[dict]   — referências leves sem texto (tecnologia, url, rerank_score)
├── iteracao_busca      int          — quantas vezes buscar_e_reranquear já executou (máx 3)
│
├── resposta_bruta      str          — resposta raw do LLM 1 antes do parse JSON
├── erro_json           str          — mensagem de erro do último parse (injetada no retry)
├── iteracao_json       int          — quantas vezes o LLM 1 já foi chamado (máx 3)
├── explicacao          dict|None    — output estruturado do LLM 1 após parse bem-sucedido
│
├── sintese_executiva   dict|None    — output do LLM 2
├── roadmap             dict|None    — output do LLM 3
├── kit_inicio          List|None    — output do LLM 4
│
└── output_final        dict|None    — resultado final consolidado (ou dict com chave "erro")
```

**chunks vs chunks_refs:** `chunks` carrega os textos completos (até 400 tokens cada) e é lido pelos LLMs de explicação. Ele é esvaziado em `validar_json` apenas quando o parse JSON tem sucesso — isso garante que retries por JSON inválido ainda tenham acesso ao conteúdo original. `chunks_refs` (sem texto) persiste até o final e serve para debugging: permite distinguir se um problema foi de retrieval ruim ou de LLM ruim.

---

## Fluxo do grafo

```
[ENTRADA: empresa_id]
        │
        ▼
carregar_perfil
  Lê o perfil completo da startup no Supabase (empresas_uso_ia).
  Inicializa todo o estado com valores padrão.
  Em falha de conexão: seta perfil={} — os nós seguintes detectam isso
  e encerram via sem_resultado sem acionar serviços externos.
        │
        ▼
montar_query
  Se perfil={}: retorna query="" sem chamar o LLM.
  Caso contrário: chama gerar_query() (OpenRouter) para transformar
  os campos do perfil (setor, produto, uso_ia_descricao, ia_tipo, nivel_maturidade_ia,
  ia_e_core_product) em uma frase de busca semântica.
  Em falha do LLM: fallback local concatenando setor + uso_ia_descricao + ia_tipo.
        │
        ▼
buscar_e_reranquear  ◄──────────────────────────────────────────────────┐
  Se perfil={} ou query="": aborta com chunks=[] sem acionar o Qdrant.  │
  Caso contrário:                                                        │
    1. Gera embedding da query via Gemini gemini-embedding-001             │
    2. Busca top_k × fator candidatos no Qdrant com filtros de setor    │
    3. Cross-encoder reordena e retorna os top_k mais relevantes         │
  Em falha de Qdrant ou embedding: devolve chunks=[] (sem crash).       │
  Relaxamento progressivo por iteração:                                  │
    iter 0: fator×3, filtro setor+"geral", threshold 0.3                 │
    iter 1: fator×5, sem filtro de setor                                 │
    iter 2: fator×7, sem filtro de setor                                 │
        │                                                                │
        ▼ rotear_apos_busca()                                            │
        ├── chunks vazio  E  iteracao_busca < 3  ────────────────────────┘  [re_buscar]
        ├── chunks vazio  E  iteracao_busca >= 3 ──► sem_resultado
        ├── rerank_score[0] < 0.3  E  iteracao < 3 ─────────────────────── [re_buscar]
        ├── rerank_score[0] < 0.3  E  iteracao >= 3 ──► sem_resultado
        ├── ia_e_core_product = True  ──► explicar_tecnico   [LLM 1]
        └── ia_e_core_product = False ──► explicar_negocio   [LLM 1]
                │                               │
                └───────────────┬───────────────┘
                                ▼
                          validar_json
                    Extrai JSON da resposta (inclusive de dentro de
                    blocos markdown com texto antes da fence).
                    Em sucesso: esvazia chunks=[] e avança.
                    Em falha: preserva chunks, incrementa iteracao_json.
                                │
                                ▼ checar_json_valido()
                                ├── JSON válido ──► sintese_executiva    [LLM 2]
                                ├── iteracao_json < 3 ──► retry LLM 1
                                └── iteracao_json >= 3 ──► sem_resultado
                                        │
                                        ▼
                               sintese_executiva                         [LLM 2]
                                        │
                                        ▼
                                roadmap_adocao                           [LLM 3]
                                        │
                                        ▼
                                   kit_inicio                            [LLM 4]
                                        │
                                        ▼
                               salvar_resultado
                    Upsert no Supabase com on_conflict="empresa_id".
                    Salva: query, chunks_reranqueados, explicacao,
                    sintese_executiva, roadmap, kit_inicio.
                    Falha de DB não interrompe — resultado preservado
                    no checkpointer para reconciliação posterior.
                                        │
                                       END

sem_resultado ──► registra motivo exato em output_final["erro"] ──► END
```

---

## Os 4 agentes LLM

### LLM 1 — Explicação (`explicar_tecnico` / `explicar_negocio`)

**Audiência:** CTO ou founder, dependendo do perfil da startup.

O grafo roteia para dois nós com prompts distintos baseado em `ia_e_core_product`:

| Nó | Foco | Quando |
|---|---|---|
| `explicar_tecnico` | Stack, arquitetura, benchmarks | `ia_e_core_product = True` |
| `explicar_negocio` | Casos de uso, impacto operacional | `ia_e_core_product = False` ou nulo |

Ambos recebem o perfil da startup e os chunks selecionados pelo reranking. A seleção de quais tecnologias recomendar já aconteceu no reranking — o LLM 1 articula o porquê.

Cada item também recebe `tipo`: `"tecnologia"` (produto técnico — SDK, biblioteca, plataforma, modelo) ou `"programa_suporte"` (programa de apoio a startups, como o NVIDIA Inception, que não resolve o problema técnico por si só). O LLM 3 usa esse campo para não confundir um programa de suporte com a prioridade técnica ao montar o roadmap (ver seção abaixo).

Saída esperada:
```json
{
  "tecnologias": [
    {"tecnologia": "NIM", "tipo": "tecnologia", "justificativa": "..."},
    {"tecnologia": "TensorRT", "tipo": "tecnologia", "justificativa": "..."}
  ],
  "fontes": ["https://developer.nvidia.com/nim", "..."]
}
```

O ciclo de retry de JSON (até 3 tentativas) injeta o erro de parse no prompt e mantém os chunks disponíveis em todas as tentativas.

---

### LLM 2 — Síntese executiva (`sintese_executiva`)

**Audiência:** CEO da startup e account manager NVIDIA.

Recebe o output do LLM 1 e o perfil. Não acessa os chunks — traduz a recomendação técnica para linguagem de negócio.

```json
{
  "resumo": "...",
  "impacto_principal": "...",
  "diferencial_competitivo": "...",
  "investimento_estimado": "...",
  "proximo_passo": "..."
}
```

---

### LLM 3 — Roadmap de adoção (`roadmap_adocao`)

**Audiência:** tech lead / CTO.

Usa `nivel_maturidade_ia` e `score_maturidade_ia` para calibrar o plano — uma startup `ai-adjacent` (score 2) recebe ações diferentes de uma `ai-native` (score 9).

`tecnologia_prioritaria` pode ser um item `tipo: "tecnologia"` ou `tipo: "programa_suporte"` — a escolha é livre, mas o prompt orienta o LLM a só eleger um programa de suporte (ex: NVIDIA Inception) como prioridade quando ele for de fato o passo mais urgente (ex: startup sem acesso a GPU/créditos para começar a testar a tecnologia). Não há guard-rail em código forçando essa regra — é orientação de prompt, então vale conferir o campo `justificativa_prioridade` para entender o raciocínio do modelo.

```json
{
  "tecnologia_prioritaria": "NIM",
  "justificativa_prioridade": "...",
  "plano": {
    "30_dias": ["..."],
    "60_dias": ["..."],
    "90_dias": ["..."]
  },
  "dependencias": ["..."],
  "metrica_de_sucesso": "..."
}
```

---

### LLM 4 — Kit de início (`kit_inicio`)

**Audiência:** dev / ML engineer.

Recebe a lista de tecnologias do LLM 1 e os campos de maturidade. Retorna o container NGC específico, tutorial de entrada e créditos Inception aplicáveis para cada tecnologia — não é uma lista estática porque o container correto depende do tipo de IA e do estágio da startup.

```json
{
  "kit": [
    {
      "tecnologia": "NIM",
      "container_ngc": "nvcr.io/nim/...",
      "tutorial_entrada": "https://...",
      "creditos_inception": "...",
      "tempo_primeiro_resultado": "4 horas"
    }
  ]
}
```

---

## Saída final

Ao final de um run bem-sucedido, `output_final` consolida os quatro outputs:

```json
{
  "explicacao":        { "tecnologias": [...], "fontes": [...] },
  "sintese_executiva": { "resumo": "...", "impacto_principal": "...", ... },
  "roadmap":           { "tecnologia_prioritaria": "...", "plano": { ... }, ... },
  "kit_inicio":        [{ "tecnologia": "...", "container_ngc": "...", ... }]
}
```

Em falha, `output_final` tem apenas `{"erro": "<motivo>", "empresa_id": <id>}`. Os motivos possíveis são:
- `"falha ao carregar perfil do Supabase"` — Supabase offline ou empresa_id inválido
- `"falha ao gerar query semântica"` — OpenRouter offline e campos do perfil insuficientes para fallback
- `"nenhum chunk encontrado após 3 tentativas de busca"` — Qdrant sem resultados
- `"qualidade insuficiente após 3 buscas (melhor rerank_score=0.XX)"` — chunks encontrados mas abaixo do limiar
- `"JSON inválido após 3 tentativas"` — LLM 1 não produziu JSON parseável em nenhuma das tentativas

---

## Ciclos de retry

### Ciclo de qualidade dos chunks

`buscar_e_reranquear` pode executar até 3 vezes. A cada iteração os parâmetros relaxam:

| Iteração | Candidatos | Filtro de setor | Objetivo |
|---|---|---|---|
| 0 | top_k × 3 = 15 | setor + "geral" | busca padrão |
| 1 | top_k × 5 = 25 | nenhum | amplia para outros setores |
| 2 | top_k × 7 = 35 | nenhum | maximiza cobertura |

Dispara quando `chunks` está vazio **ou** o `rerank_score` do chunk #1 é menor que 0.3. Após 3 tentativas sem qualidade suficiente, o grafo encerra via `sem_resultado`.

### Ciclo de JSON inválido

`explicar_tecnico` / `explicar_negocio` podem ser chamados até 3 vezes. A cada falha de parse, o erro é injetado no prompt e os chunks permanecem disponíveis no estado para que o modelo tenha os dados-fonte em cada tentativa.

---

## Persistência com checkpointer

O grafo é compilado com `MemorySaver` por padrão. Em produção, passar um `SqliteSaver` ou `PostgresSaver`:

```python
from agents.extras.graph import criar_grafo
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
grafo = criar_grafo(checkpointer=checkpointer)
```

O checkpointer salva o estado após cada nó. Se o processo cair no meio do run (ex: após LLM 2), retomar com o mesmo `thread_id` continua de onde parou sem refazer chamadas já concluídas:

```python
grafo.invoke(
    {"empresa_id": 42},
    config={"configurable": {"thread_id": "empresa-42"}},
)
```

O `thread_id` padrão usado por `inicia_recomendacao.py` é `"empresa-{empresa_id}"`.

A persistência no Supabase está em `try/except` sem re-raise. Se a escrita falhar, os resultados estão preservados no checkpointer e podem ser recuperados sem refazer as chamadas LLM.

---

## Tratamento de falhas de infraestrutura

| Componente | Falha | O que acontece |
|---|---|---|
| Supabase (leitura) | `carregar_perfil` | `perfil={}` → `montar_query` e `buscar_e_reranquear` abortam → `sem_resultado` |
| OpenRouter | `montar_query` | Fallback local com campos do perfil concatenados |
| Qdrant | `buscar_e_reranquear` | `chunks=[]` → ciclo de retry ativo até 3 tentativas |
| Gemini (embedding) | `buscar_e_reranquear` | `chunks=[]` → mesmo ciclo de retry |
| Gemini (chat) | qualquer LLM | Retry exponencial interno (3×, 5s/10s/20s); após esgotar, exceção encerra o run |
| Supabase (escrita) | `salvar_resultado` | Log de erro; resultado preservado no checkpointer |

---

## Dependências externas

| Serviço | Variável de ambiente | Usado em |
|---|---|---|
| Supabase | `SUPABASE_URL`, `SUPABASE_KEY` | Leitura de perfil, escrita de resultado |
| Gemini 2.5 Flash | `GEMINI_API_KEY` | Chamadas dos 4 LLMs |
| Gemini | `GEMINI_API_KEY2` | Geração de embeddings para busca |
| OpenRouter | `OPENROUTER_API_KEY` | Geração da query semântica |
| Qdrant | configurado em `src/rag/client.py` | Busca vetorial da base de conhecimento NVIDIA |

A base de conhecimento precisa estar indexada antes de rodar o pipeline:
```bash
# Indexar todos os JSONs
cd src && python -m rag.indexador

# Indexar um arquivo específico
cd src && python -m rag.indexador --arquivo ../data/nvidia_knowledge/rapids.json
```
