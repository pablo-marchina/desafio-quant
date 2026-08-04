# Roadmap de evolução — NVIDIA Startup AI Radar

Ideias para elevar o projeto além dos 6 entregáveis. Ordenadas por **impacto no
currículo / na qualidade do resultado** vs. esforço. Não é TAPI — é evolução livre.

## A. Qualidade dos agentes e do fluxo (maior ganho de RESULTADO)

Ordem recomendada: 1 → 2 são mais simples E cobrem a maior fração do problema
(validam a ENTRADA). Só depois medir quanta alucinação sobra no briefing (5) para
decidir se a reflection vale — ela pega só o resíduo de SÍNTESE. Ver nota abaixo.

Melhorias nos nós atuais (em ordem de prioridade):

- [x] **1. Evidence Validator vira grounding real** — ✅ FEITO. Faithfulness check por
      LLM (`verificar_afirmacoes`): cada campo do `DadosEmpresa` × trechos coletados →
      veredito + fonte, registrado em `state.afirmacoes_verificadas`. Campos de alto
      risco sem lastro (`funding`/`founders`/`clientes`) são removidos. Gate agora exige
      `setor`/`descricao` ancorados, não só preenchidos. Pré-gate mecânico mantido;
      fallback via `grounding_habilitado`/sem chave. (Chain-of-Verification.) — `app/evidence_validator.py`
      → **Falta:** estender o grounding ao `contexto_rag` (specs NVIDIA), que só existe
      pós-`nvidia_rag` — vira nó novo pós-RAG (fecha o buraco #1 da reflection do briefing).
- [x] **1b. Reordenar o grafo: Classifier DEPOIS do Evidence Validator** — ✅ FEITO
      (destravado pelo item 1). Antes o Classifier decidia sobre dados não-verificados
      (e no loop nunca via a versão saneada). Agora: `extractor → evidence_validator →
      [loop] → classifier → [non-ai? END] → nvidia_rag`. O desvio `non-ai` segue antes
      do RAG (poupa o caro); Classifier saiu do loop (roda 1×, sobre dados limpos). — `app/graph.py`
- [x] **2. Loop dirigido ao gap** — ✅ FEITO. No retry, `campos_em_falta(state)` acha os
      campos vazios em `dados_estruturados` OU não-sustentados no grounding, e o Search
      Planner monta queries específicas (`funding → "investimento rodada aporte"`) via
      `queries_extra`. **+ Acúmulo:** o Scraper passou a somar `conteudo_bruto` entre as
      voltas (dedup por fonte), então a busca dirigida ENRIQUECE a evidência em vez de
      substituí-la (sem isso, o retry poderia perder campos já achados). — `app/search_planner.py`, `app/scraper.py`
- [x] **3. Classifier few-shot + self-consistency** — ✅ FEITO. Few-shot: âncoras no prompt
      (Tractian=ai-native, um ai-enabled, um non-ai) calibram a fronteira. Self-consistency:
      `classificar_consistente` classifica `classifier_n_votos` (=3) vezes com temperatura
      >0 e devolve o rótulo majoritário (detalhe vem de um voto vencedor). Estabiliza a
      decisão que controla o desvio `non-ai`. — `app/classifier.py`, `app/config.py`
- [x] **4. Separar recomendação de pontuação** — ✅ FEITO. `recomendar` (7 campos) e
      `pontuar` (4 notas com rubrica ancorada 0-3/4-6/7-10 por eixo) viraram chamadas
      separadas. `pontuar_em_painel` roda `score_n_juizes` (=3) juízes e faz a MÉDIA das
      notas (análogo numérico do self-consistency do A.3 — média em vez de moda). Reduz a
      variância do score que ordena o ranking. — `app/recommendation.py`, `app/config.py`
- [x] **5. Briefing com reflection** — ✅ FEITO (justificado por evidência: o teste ao vivo
      deixou passar um "10×" e uma citação trocada). `redigir` → `revisar` (passada única de
      LLM que remove número sem lastro e citação incoerente, preservando o resto). Toggle
      `briefing_reflection` + fallback. `numeros_sem_fonte` (detector determinístico de
      métrica `%`/`×` sem fonte) vira teste + aviso de observabilidade. — `app/briefing.py`, `app/config.py`
      → **Falta:** *fornecer* a citação certa (o revisor só remove a errada) → depende de
      cobertura do RAG / grounding pós-RAG. E, se ainda vazar número, quebrar em crítico
      separado + reescrita (2 chamadas).

> **Nota — por que a reflection do briefing vem por último:** grounding valida a
> ENTRADA (fatos atômicos); reflection valida a SAÍDA (o texto gerado). Há
> sobreposição parcial. Se o grounding (item 1) cobrir também o `contexto_rag`,
> sobra só o resíduo de SÍNTESE que a reflection pega: fatos verdadeiros
> recombinados numa conclusão não sustentada ("tem latência ruim" ✓ + "NIM serve
> modelos" ✓ → "logo NIM resolve a latência dela" ✗ — ninguém mediu). Por isso:
> fazer 1+2, medir a alucinação restante (seção E), e só então decidir se 5 vale.

Nós novos:

- [ ] **Entity Resolution / desambiguação** (após o Scraper) — garantir que raspou a
      empresa certa (nomes colidem).
- [ ] **Competitive / positioning agent** — posiciona vs. concorrentes; enriquece o briefing.
- [ ] **Confidence scoring por campo** — baixa confiança dispara o loop de forma dirigida.
- [ ] **RAG multi-query / HyDE** — N sub-perguntas a partir dos gaps, fundir resultados. — `app/nvidia_rag.py`
- [ ] **Human-in-the-loop checkpoint** — LangGraph interrupt antes do Briefing (aprovação).

## B. Usar a stack da própria NVIDIA (maior diferencial narrativo)

- [ ] **NVIDIA NIM** (build.nvidia.com, grátis) no lugar do Groq — OpenAI-compatible,
      troca fácil em `app/llm.py`.
- [ ] **NeMo Retriever** — embeddings + rerank da NVIDIA (substitui Gemini + Cohere em `app/rag.py`).
- [ ] **NeMo Guardrails** — guardrail anti-alucinação de specs no Briefing.
- Motivo: hoje recomendamos tech NVIDIA sem usar nenhuma. Fechar esse loop é a melhor história de entrevista.

## C. Frontend React (skill nova pedida)

- [ ] **Next.js (React) + FastAPI** (já temos uvicorn) expondo `app/batch.py:analisar`.
- [ ] **Streaming ao vivo do pipeline** — SSE/WebSocket + LangGraph `.astream_events`;
      cada nó "acende" em tempo real, loop do Validator visível.
- [ ] Visualizar o `RadarState` sendo preenchido campo a campo.

## D. Observabilidade (parece produção)

- [ ] **Langfuse** ou **LangSmith** — tracing por nó: latência, tokens, custo, prompts.

## E. Rigor de avaliação (já começou com hit@k)

- [ ] **RAGAS** — faithfulness, context precision/recall, answer relevancy.
- [ ] **LLM-as-judge** da qualidade do Briefing (rubrica: cita fonte? linguagem de negócio?).
- [ ] Dashboard de eval no front.

## F. Deploy & engenharia

- [ ] **Docker Compose** real (Postgres + Qdrant-servidor + API + front) — o `docker-compose.yml` está vazio.
- [ ] **pgvector** ou Qdrant-servidor (sair do modo local).
- [ ] **CI/CD (GitHub Actions)** — rodar os 29 testes + `ruff` em cada push (não há linter hoje).
- [ ] Deploy público (Render/Fly/Railway) com URL pro currículo.

## G. Avançado / dados

- [ ] **Knowledge graph** (Neo4j) startups × investidores × techs → GraphRAG.
- [ ] **Discovery agendado** (cron) alimentando o banco — radar "vivo".
