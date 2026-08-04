# Fluxo de Recomendação de Tecnologias NVIDIA

## Pré-requisitos para execução

Antes de rodar o pipeline, a base de conhecimento vetorial precisa estar populada. Setup completo em [README.md](../README.md).

Resumo dos passos:

```bash
# 1. Subir o Qdrant
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# 2. Criar a collection
python -m src.rag.setup_qdrant

# 3. Indexar os JSONs
python -m src.rag.indexador

# 4. Rodar o pipeline
python src/recomendacao/inicia_recomendacao.py
```

---

## Visão geral

O sistema recebe o perfil de uma startup já coletado e explica quais tecnologias NVIDIA são mais adequadas ao seu contexto. A seleção das tecnologias é feita implicitamente pelo pipeline RAG com reranking — não há um agente de recomendação separado. Um agente de explicação recebe os chunks já selecionados e articula o porquê de cada tecnologia para aquela startup específica.

---

## Diagrama do fluxo

```
PERFIL DA STARTUP (já existe no banco)
───────────────────────────────────────
setor: "saude"
produto: "plataforma de diagnóstico por imagem"
ia_tipo: "visão computacional"
nivel_maturidade_ia: "ai-adjacent"
ia_e_core_product: true
        │
        ▼
MONTAGEM DA QUERY SEMÂNTICA
────────────────────────────
"startup de saúde com visão computacional em MVP,
 precisa de inferência de modelos de imagem"
        │
        ▼
BUSCA VETORIAL NO QDRANT (buscador.py)
───────────────────────────────────────
Recupera top_k * 3 candidatos (ex: 15 chunks)
via similaridade de cosseno + filtros por metadata
        │
        ▼
RERANKING (reranker.py)
────────────────────────
Cross-encoder lê query + cada chunk juntos
e pontua relevância semântica real.
Os 15 candidatos são reordenados e truncados para top_k (ex: 5).
→ A seleção das tecnologias acontece aqui.
        │
        ▼
TOP CHUNKS RERANQUEADOS
────────────────────────
chunk 1: "NVIDIA NIM para visão computacional..."   tecnologia: NIM       rerank_score: 0.92
chunk 2: "TensorRT otimiza inferência de CNNs..."   tecnologia: TensorRT  rerank_score: 0.87
chunk 3: "Case: startup de diagnóstico usa RAPIDS"  tecnologia: RAPIDS    rerank_score: 0.71
        │
        ▼
AGENTE DE EXPLICAÇÃO (Gemini com contexto)
───────────────────────────────────────────
Recebe perfil da startup + top chunks.
Não decide quais tecnologias recomendar — isso já foi feito pelo reranking.
Apenas articula por que cada tecnologia é relevante para aquele contexto.
Consolida chunks duplicados da mesma tecnologia em uma única justificativa.
        │
        ▼
SAÍDA GERADA
─────────────
"NIM aparece porque sua startup está em MVP e precisa de deploy rápido
 de modelo de imagem — NIM oferece isso via API em minutos.
 TensorRT aparece porque CNNs de diagnóstico têm requisito de latência
 baixa em produção, que é exatamente o que ele resolve."
```

---

## Etapas detalhadas

### 1. Entrada — perfil da startup

Campos do banco usados para montar a query:

| Campo | Função na recomendação |
|---|---|
| `setor` | filtra chunks com casos de uso relevantes |
| `produto` | ancora a busca semântica no domínio do produto |
| `uso_ia_descricao` | descrição detalhada de como a IA é usada — campo principal para a query |
| `ia_tipo` | direciona para tecnologias do mesmo tipo de IA |
| `nivel_maturidade_ia` | pode priorizar soluções de deploy rápido (ai-adjacent) ou otimização (ai-native) |
| `ia_e_core_product` | se true, prioriza stack técnica; se false, prioriza casos de uso de negócio |

### 2. Montagem da query semântica

O agente combina os campos do perfil em uma frase de busca natural. Exemplo:

```
"startup de saúde com produto de visão computacional em estágio MVP
 buscando solução para inferência de modelos de imagem médica em produção"
```

### 3. Recuperação no Qdrant (`buscador.py`)

Busca híbrida: similaridade vetorial + filtros por metadata. Para acomodar o reranking, a busca recupera `top_k * fator_candidatos` resultados (padrão: `fator_candidatos=3`).

```python
buscador.buscar(
    query="...",
    filtros={
        "setor": {"$in": ["saude", "geral"]},
        # "categoria" não precisa ser passado: o buscador aplica o default
        # ["produto", "caso_de_uso", "stack", "inception"] automaticamente.
        # "inception" é sempre incluído — o Inception é um habilitador universal
        # e o reranker decide se ele fica nos top_k ou não.
    },
    top_k=5,
    reranking=True,        # ativa o reranking
    fator_candidatos=3,    # busca 15 candidatos antes de reranquear para 5
)
```

### 4. Reranking (`reranker.py`)

Módulo separado em `src/rag/reranker.py`. Recebe a query e os 15 candidatos do Qdrant, devolve os 5 mais relevantes segundo o cross-encoder.

**Modelo:** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (via `sentence_transformers`, já dependência do projeto)  
**Execução:** local, sem API externa  
**Latência estimada:** 200–500ms para 15 pares (CPU) — modelo multilingual com 12 camadas

> **Por que não usar Cohere Rerank?**
> O Cohere Rerank é uma API paga de reranking com modelos maiores e qualidade superior. Foi descartado por três motivos: (1) introduz custo por requisição em um pipeline que já tem Gemini como dependência paga; (2) adiciona latência de rede e uma dependência externa extra; (3) o cross-encoder local `mmarco-mMiniLMv2-L12-H384-v1` já é uma dependência transitiva do projeto via `sentence_transformers`, suporta português nativamente e entrega qualidade suficiente para o volume de candidatos deste pipeline (~15 chunks). Se a qualidade do reranking se mostrar limitante em produção, o Cohere Rerank é um substituto direto — basta trocar a implementação de `reranquear()` em `reranker.py`.

O cross-encoder lê query e chunk juntos com atenção cruzada token a token — é muito mais preciso que similaridade de cosseno porque não comprime o significado em um vetor único. A seleção final das tecnologias a apresentar é determinada pela ordem de saída do reranker.

```python
# funcionamento interno do reranker
pares = [(query, chunk["texto"]) for chunk in candidatos]
scores = cross_encoder.predict(pares)   # um float por par
# ordena por score decrescente, devolve top_k
```

### 5. Plataforma multi-agente (`src/agents/extras/`)

O pipeline RAG com reranking foi evoluído para uma plataforma multi-agente orquestrada com LangGraph. Os chunks selecionados pelo reranking alimentam quatro agentes LLM sequenciais, cada um com audiência e responsabilidade distintas.

| Agente | Arquivo | Pergunta respondida | Audiência |
|---|---|---|---|
| LLM 1 — Explicação técnica ou de negócio | `nodes.py:explicar_tecnico` / `explicar_negocio` | Por que essas tecnologias para esta startup? | CTO / founder |
| LLM 2 — Síntese executiva | `nodes.py:sintese_executiva_node` | O que o CEO precisa saber, sem jargão? | CEO + account manager NVIDIA |
| LLM 3 — Roadmap de adoção | `nodes.py:roadmap_adocao_node` | Por onde começo e em que ordem? | Tech lead |
| LLM 4 — Kit de início | `nodes.py:kit_inicio_node` | Qual container NGC, tutorial e crédito Inception usar agora? | Dev / ML engineer |

O LLM 1 tem dois prompts distintos roteados pelo campo `ia_e_core_product`: `explicar_tecnico` (foco em stack, benchmarks e arquitetura) e `explicar_negocio` (foco em casos de uso e impacto operacional). A escolha entre eles é feita pelo grafo, não pelo agente.

Cada item retornado pelo LLM 1 é classificado em `tipo`: `"tecnologia"` (produto técnico que resolve o problema diretamente — SDK, biblioteca, plataforma, modelo) ou `"programa_suporte"` (programa de apoio a startups, como o NVIDIA Inception, que oferece créditos/treinamento mas não processa dado nem resolve o problema técnico por si só). Essa distinção existe porque o LLM 3 (Roadmap) usa os dois tipos para decidir a `tecnologia_prioritaria` com mais contexto — evitando que um programa de suporte seja escolhido só por aparecer primeiro na lista, quando na verdade uma tecnologia técnica é o passo mais urgente. Um programa_suporte ainda pode ser eleito prioritário legitimamente (ex: startup sem acesso a GPU/créditos para nem começar a testar a tecnologia) — a classificação só dá ao modelo o contexto para decidir com intenção, não impede a escolha.

O grafo inclui dois ciclos de retry automático: um para qualidade dos chunks (até 3 buscas com parâmetros progressivamente relaxados) e um para JSON inválido na resposta do LLM 1 (até 3 tentativas com o erro de parse injetado no prompt). O estado completo é persistido por um checkpointer a cada nó — se o processo cair após o LLM 2, o run retoma do LLM 3 sem refazer chamadas já concluídas.

Documentação completa do grafo: `documentacao/langgraph.md`

### 6. Saída — output estruturado em quatro camadas

```json
{
  "explicacao": {
    "tecnologias": [
      {
        "tecnologia": "NIM",
        "tipo": "tecnologia",
        "justificativa": "Permite deploy rápido de modelos de visão em produção via API, adequado ao estágio MVP da startup"
      },
      {
        "tecnologia": "TensorRT",
        "tipo": "tecnologia",
        "justificativa": "Otimiza latência de inferência em CNNs para diagnóstico por imagem, crítico para uso clínico em tempo real"
      }
    ],
    "fontes": ["https://developer.nvidia.com/nim", "https://developer.nvidia.com/tensorrt"]
  },
  "sintese_executiva": {
    "resumo": "...",
    "impacto_principal": "...",
    "diferencial_competitivo": "...",
    "investimento_estimado": "...",
    "proximo_passo": "..."
  },
  "roadmap": {
    "tecnologia_prioritaria": "NIM",
    "plano": {
      "30_dias": ["..."],
      "60_dias": ["..."],
      "90_dias": ["..."]
    },
    "metrica_de_sucesso": "..."
  },
  "kit_inicio": [
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

## Chunking — implementação atual

O chunking é feito em `src/rag/indexador.py`, na função `chunkar_texto()`. Não usa LangChain — é uma implementação própria baseada em `tiktoken`.

### Parâmetros

| Parâmetro | Valor | Descrição |
|---|---|---|
| `_CHUNK_SIZE` | 400 tokens | Tamanho máximo de cada chunk |
| `_CHUNK_OVERLAP` | 50 tokens | Tokens reutilizados do chunk anterior |
| Encoding | `cl100k_base` | Usado pelo tiktoken para contagem de tokens no chunking |

### Algoritmo

1. **Tokenização por frases** — o texto é dividido por pontuação final (`.`, `!`, `?`, `…`) via `re.split(r"(?<=[.!?…])\s+", texto)`. Nunca corta no meio de uma frase.
2. **Acúmulo até o limite** — frases são acumuladas em `current_sentences` enquanto o total de tokens não ultrapassar `_CHUNK_SIZE`.
3. **Criação do chunk** — ao ultrapassar o limite, as frases acumuladas formam um chunk (`" ".join(current_sentences)`).
4. **Overlap** — antes de iniciar o próximo chunk, as últimas frases do chunk anterior são reaproveitadas (retroativamente, em ordem reversa) até preencher `_CHUNK_OVERLAP` tokens. Isso preserva contexto entre chunks adjacentes.
5. **Chunk final** — as frases restantes sempre formam o último chunk, mesmo abaixo do limite.

```python
# trecho simplificado de chunkar_texto()
sentences = re.split(r"(?<=[.!?…])\s+", texto.strip())

for sentence in sentences:
    if current_token_count + sentence_tokens > _CHUNK_SIZE:
        chunks.append(" ".join(current_sentences))   # fecha chunk atual
        # monta overlap retroativo com frases do chunk fechado
        current_sentences = overlap_sentences
        current_token_count = overlap_tokens

    current_sentences.append(sentence)
    current_token_count += sentence_tokens

chunks.append(" ".join(current_sentences))           # último chunk
```

### Onde é chamado

`indexar_json()` (mesma arquivo) chama `chunkar_texto()` no campo `texto` de cada documento JSON, gera um `doc_id` UUID compartilhado entre todos os chunks do documento, e adiciona `chunk_index` / `chunk_total` ao metadata de cada chunk antes de enviar ao Qdrant via `indexar_documento()`.

### Enriquecimento contextual dos chunks

Antes de gerar o embedding, cada chunk recebe um prefixo com a tecnologia e o título do documento:

```
Tecnologia: NIM. NVIDIA NIM — Microservices de Inferência para Deploy de Modelos em Produção.

<texto do chunk>
```

**Por que isso é necessário:** documentos com mais de 400 tokens são divididos em múltiplos chunks. Chunks intermediários frequentemente não repetem o nome da tecnologia — um trecho como *"o container já vem com as otimizações de inferência aplicadas..."* não contém "NIM" em lugar nenhum. Sem o prefixo, o embedding desse chunk não captura a que tecnologia ele pertence, e a busca semântica perde precisão.

O prefixo só afeta o texto enviado ao modelo de embedding. O payload armazenado no Qdrant (metadata + texto original do chunk, sem prefixo) não é alterado.

Essa técnica é conhecida como **Contextual Retrieval** e é especialmente relevante quando os documentos são longos o suficiente para gerar mais de um chunk.

### Decisão de design

A granularidade por frase foi escolhida para evitar que frases semanticamente densas sejam cortadas ao meio, o que degradaria a qualidade dos embeddings. O overlap de 50 tokens garante que o reranker tenha contexto suficiente nos chunks limítrofes.

---

## Por que não usar busca híbrida com BM25

BM25 faz matching lexical no conteúdo textual dos chunks — é útil quando a query contém termos técnicos exatos que aparecem literalmente nos documentos. Neste pipeline, isso não ocorre por dois motivos:

**1. A query é semântica, não lexical.**
Ela é montada a partir dos campos do perfil da startup (`setor`, `produto`, `ia_tipo`, `nivel_maturidade_ia`), resultando em frases como `"startup de saúde com visão computacional em MVP"`. Nenhum campo do perfil contém nomes de tecnologias NVIDIA como "TensorRT" ou "NIM" — portanto BM25 não teria termos para fazer matching no texto dos chunks.

**2. Os filtros de metadata já fazem o trabalho de segmentação.**
O que este pipeline precisa de "lexical" é segmentação categórica: só chunks do setor relevante, só chunks de categorias úteis (produto, stack, caso_de_uso). Isso é resolvido pelos filtros estruturados (`setor`, `categoria`) antes mesmo da busca vetorial, sem custo adicional.

**Quando BM25 passaria a fazer sentido:** se o sistema evoluir para uma interface onde o usuário digita livremente (ex: `"quero usar TensorRT para otimizar CNN de diagnóstico"`), o matching lexical sobre o texto dos chunks adicionaria precisão real. Nesse cenário, a busca híbrida (dense + sparse vectors com fusão RRF) no Qdrant seria a abordagem correta.

---

## Arquitetura de arquivos

| Arquivo | Responsabilidade | Status |
|---|---|---|
| `src/rag/buscador.py` | Busca vetorial no Qdrant; orquestra o reranking quando `reranking=True` | existente |
| `src/rag/reranker.py` | Cross-encoder multilingual; reordena candidatos por relevância semântica real | existente |
| `src/rag/indexador.py` | Chunking, validação e indexação de JSONs no Qdrant | existente |
| `src/rag/embedding.py` | Geração de embeddings via Gemini `gemini-embedding-001` | existente |
| `src/agents/extras/state.py` | TypedDict `EstadoRecomendacao` — contrato do estado compartilhado do grafo | existente |
| `src/agents/extras/nodes.py` | Todos os nós e funções de roteamento do grafo LangGraph | existente |
| `src/agents/extras/prompts.py` | Prompts dos 4 agentes LLM | existente |
| `src/agents/extras/gemini.py` | Wrapper de chamada ao Gemini com retry exponencial | existente |
| `src/agents/extras/graph.py` | Montagem, arestas e compilação do grafo com checkpointer | existente |

---

## Dependências

| Componente | Localização |
|---|---|
| Perfil da startup | banco de dados existente |
| Base de conhecimento NVIDIA | Qdrant, collection `nvidia_knowledge` |
| Scraping e indexação | `src/scraping_nvidia/` |
| Embedding | `src/rag/embedding.py` — Gemini `gemini-embedding-001` |
| Busca vetorial | `src/rag/buscador.py` |
| Reranking | `src/rag/reranker.py` — `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` |
| Plataforma multi-agente (LLMs 1-4) | `src/agents/extras/` — grafo LangGraph com 4 agentes sequenciais |

---

## Metadata dos chunks (campos usados nos filtros)

| Campo | Valores possíveis |
|---|---|
| `tecnologia` | NIM, NeMo, RAPIDS, CUDA, Triton, TensorRT, cuDF... |
| `categoria` | produto, conceito, caso_de_uso, inception, stack — o buscador inclui produto, caso_de_uso, stack e inception por padrão; conceito é excluído do filtro default |
| `setor` | saude, financas, agro, varejo, industria, logistica, educacao, energia, geral |
| `url` | origem do conteúdo (rastreabilidade) |
| `data_coleta` | controle de atualização do conhecimento |
