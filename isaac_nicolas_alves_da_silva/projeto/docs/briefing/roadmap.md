# Roadmap do Modulo Briefing

Atualizado em 27/06/2026.

O modulo `briefing` transforma analises tecnicas em uma saida executiva clara.
Ele e a camada final do produto: o lugar onde uma pessoa de negocio entende o
que foi encontrado, com que grau de certeza, e o que fazer a seguir.

Este documento e a **visao ponta a ponta** do briefing robusto. Como o briefing
so e tao bom quanto o fit que o alimenta, ele consolida aqui tambem o redesign
de fit/confianca do modulo `recommendations` — os dois sao tratados como um
unico problema de produto, nao dois roadmaps soltos. O diagnostico detalhado
de origem esta em `docs/briefing/plano_fit_confiabilidade_briefing.md`; este
documento e a versao consolidada e priorizada.

---

## Objetivo do Modulo

```txt
startup + evidencias + recomendacoes -> briefing executivo acionavel
```

O briefing nao e uma lista de tecnologias. E uma **analise**: uma tese de
encaixe entre a startup e o portfolio NVIDIA, com incertezas explicitas,
evidencias rastreaveis e perguntas de qualificacao quando faltar informacao.

---

## Principio de arquitetura (le antes de qualquer mudanca)

A maior fraqueza atual do produto e o **fit baixo e a confianca baixa** das
recomendacoes que entram no briefing. A causa raiz nao e falta de dados: e que
o fit hoje vem de sobreposicao de palavras-chave (`match_technologies` em
`recommendations/domain/policies.py`), com `score = keywords_batidas / total`.
Isso casa termo, nao significado, e tem teto realista em torno de 0.5.

A direcao deste roadmap inverte a divisao de trabalho **sem violar** as regras
do `CLAUDE.md`:

```txt
ANTES:  codigo decide o fit (keyword)        -> IA so reescreve a prosa
DEPOIS: tools entregam evidencia + candidatos -> IA raciocina o fit
        -> codigo poe guarda determinística por cima
```

Isso e coerente com a **regra 6 do PRE-DECISION CHECKLIST**: "chame LLM so
quando a validacao determinística for insuficiente". Para mapear
"assistente de voz para clinicas" -> Riva + Clara + NIM, a validacao
determinística por keyword **e** insuficiente. O problema e semantico, e o
LLM e a ferramenta certa — desde que cercado.

Tres papeis, nunca confundidos:

- **Tools = grounding + evidencia.** Retrieval semantico (embeddings/Qdrant)
  restringe o catalogo NVIDIA aos candidatos plausiveis e traz docs reais. O
  keyword matcher vira um *sinal/prior*, nao o veredito. RAG traz contexto
  NVIDIA citavel.
- **IA = analista.** Raciocina sobre o perfil da startup + docs recuperados e
  produz fit graduado, nivel (forte/moderada/exploratoria/sem fit) e
  justificativa estruturada. Saida sempre validada por Pydantic/enum.
- **Codigo = guarda.** Piso/teto de score, regra de elegibilidade por
  tecnologia, "uma tech so entra com evidencia recuperada", override
  determinístico (regra 9). Nada de loop aberto controlado so pelo LLM.

Esse padrao **ja existe parcialmente no codigo** e deve ser reaproveitado, nao
reescrito:

- `Recommendation Agent` (Agents V11,
  `agents/infrastructure/llm/langchain_gemini_recommendation_reviewer.py`): o
  LLM julga so candidatos ambiguos (`score < AMBIGUOUS_SCORE_THRESHOLD = 0.5`);
  candidato com `score >= 0.5` e **sempre mantido**, o LLM nao pode descartar.
  Guarda em codigo por cima do LLM — exatamente o padrao desejado.
- `Briefing Agent` (Agents V12): orquestra `BriefingGenerator` como tool e usa
  LLM so para reescrever prosa, com fallback que descarta a reescrita se ela
  perder qualquer citacao/URL do template determinístico.

O gargalo nao e falta de IA: e que o V11 **nao esta no caminho sincrono que
produz o score**, e a tool que ele embrulha e o motor de keyword fraco.

---

## Versoes

| Versao | Status | Objetivo |
|---|---|---|
| Briefing V1 | Implementado | Template executivo em Markdown |
| Briefing V2 | Implementado (Agents V12) | Briefing gerado por agente (reescrita de prosa) |
| Briefing V3 | Implementado (24/06/2026) | Exportacao em PDF preservando citacoes |
| Briefing V4 | **Implementado (27/06/2026)** | Briefing como analise: tese de fit, confianca geral, fortes vs. exploratorias, perguntas de qualificacao |
| Briefing V5 | **Implementado (27/06/2026)** | Golden set de 6 arquetipos de referencia; test_golden_set.py em recommendations/tests/unit/; media p@3 = 0.78 (piso 0.50); 10/10 testes passando |
| Briefing V6 | Planejado | Robustez operacional: versionamento, auditoria, reprocessamento por etapa |

As prioridades transversais de produto estao em `docs/roadmap_produto_final.md`.

---

## Briefing V1 — Template Executivo (implementado)

Entregue:

- entidade `Briefing`;
- regras deterministicas (`domain/policies.py`) para riscos e proximas acoes;
- estrutura padrao (Resumo, Evidencias Principais, Recomendacoes NVIDIA,
  Riscos, Proximas Acoes);
- contrato publico `RecommendationsReader` em `recommendations`;
- `POST /briefings`, `GET /briefings/{id}`, `GET /briefings?startup_id=`;
- saida em Markdown; testes de regra, caso de uso e persistencia.

Extensao de 24/06/2026 — RAG grounding: `RagNvidiaContextGrounder` chama o
contrato publico de RAG filtrado por `source_type=nvidia_knowledge` e adiciona
a secao "Contexto NVIDIA" com citacoes em Markdown (`[Fonte N](url)`), com
fallback determinístico quando nao ha contexto.

Documento: `docs/briefing/briefing_v1_template_executivo.md`.

---

## Briefing V2 — Agente de Briefing (implementado, Agents V12)

O `BriefingAgentGraph` (4 nodes) orquestra `BriefingGenerator` como tool e usa
`LangChainGeminiBriefingProseRewriter` para reescrever a prosa em linguagem de
negocio, com fallback de controle de citacoes (extrai URLs, compara
original vs. reescrita, descarta a reescrita se faltar alguma). A reescrita e
persistida de volta em `briefing` (consumidor sincrono ligado em 23/06/2026).

**Limite que a V4 resolve:** o agente hoje so embrulha em texto melhor o que a
V1 ja entrega. Ele nao muda o fit, a confianca, nem quais tecnologias entram —
esses numeros vem do motor de keyword. Melhorar o agente de briefing **nao**
resolve o fit baixo; isso e trabalho da V4 (no `recommendations` e na estrutura
do briefing), nao da reescrita de prosa.

Documento: `docs/agents/agents_v12_briefing_agent.md`.

---

## Briefing V3 — Exportacao (implementado, 24/06/2026)

PDF real via Chromium headless (Playwright + Jinja2 + `markdown`), preservando
citacoes (links Markdown viram `<a href>` na conversao). `weasyprint` do plano
original foi trocado por Playwright (ja dependencia desde Scraping V4, sem risco
de bibliotecas nativas no Windows). Detalhe: `docs/briefing/briefing_v3_export_pdf.md`.

---

## Briefing V4 - Briefing como Analise (implementado, 27/06/2026)

Esta entrega resolve o problema central. Ela tem tres frentes que precisaram
andar juntas, porque o briefing so melhora se o fit melhorar primeiro.

Status em 27/06/2026:

```txt
StartupAIProfile estruturado                         ENTREGUE
score composto + nova confianca em recommendations   ENTREGUE
signal_origins / missing_signals                     ENTREGUE
nivel / faltando                                     ENTREGUE
prefiltro semantico de candidatos NVIDIA             ENTREGUE (best-effort)
briefing analitico com matriz/perguntas/lacunas      ENTREGUE
golden set e metricas                                V5
```

### 4.1 Perfil estruturado da startup — `StartupAIProfile`

Hoje o motor compara keyword contra texto cru. Falta um artefato intermediario
que transforme evidencia coletada em campos comparaveis com o catalogo NVIDIA.

Artefato `StartupAIProfile`, extraido das evidencias (via Extraction Agent ja
existente, Agents V8), com origem registrada por campo:

```txt
ai_workload_type      NLP | visao | recomendacao | simulacao | analytics | MLOps | fala
model_type            treina proprio | fine-tuning | usa via API | classico (ML)
data_modality         texto | imagem | audio | tabular | 3D | log/rede
deployment_stage      pesquisa | MVP | piloto | producao | escala
infra_environment     cloud | on-premise | edge | hibrido
gpu_need              alta | media | baixa | desconhecida
latency_requirement   tempo-real | batch | desconhecida
scale_signal          volume/throughput observado (se houver)
current_tools         frameworks/stack mencionados
business_goal         objetivo de negocio declarado
evidence_ids          rastreabilidade por campo
field_confidence      confianca por campo (0-1)
```

Regra de arquitetura: `StartupAIProfile` e um perfil de dominio em `startups`
(ou um DTO publico exposto por `startups/application/public/`). `recommendations`
e `briefing` o consomem so via contrato publico — nunca tocam internals.
Campos sem evidencia ficam `desconhecida`, e isso e informacao util no briefing
("o que nao foi encontrado"), nao um buraco a ser preenchido com chute (regra 9:
o LLM nunca infere/inventa campo sem evidencia).

### 4.2 Fit como score composto, nao proporcao de keyword

`score = keywords_batidas / total` foi substituido por um **score composto**
com rubrica explicita e auditavel:

```txt
fit = 0.35 * alinhamento_de_workload      (StartupAIProfile x criterio da tech)
    + 0.25 * evidencia_concreta           (ha sinal real, nao termo solto)
    + 0.15 * maturidade_da_startup        (stage compativel com a tech)
    + 0.15 * valor_nvidia_especifico      (a tech resolve uma dor declarada)
    + 0.10 * viabilidade_de_implementacao (complexidade x maturidade tecnica)
```

Onde o alinhamento de workload e o valor especifico saem do **raciocinio da IA
sobre os candidatos recuperados por retrieval semantico**, e os demais saem de
sinais determinísticos (stage, evidencia, complexidade). O fit final e:

```txt
fit_final = blend(score_semantico_IA, score_deterministico)
```

Guardas em codigo (regra 9), nao confiadas ao prompt:

- termos genericos sozinhos (`platform`, `data`, `ai`, `machine learning`,
  `cloud`) nao sustentam recomendacao tecnica — exigem um segundo sinal;
- tecnologia tecnica so entra com **evidencia recuperada** associada;
- piso/teto no fit; o LLM nunca devolve um numero fora do intervalo permitido;
- candidato com sinal determinístico forte e sempre mantido (mesmo padrao do
  `AMBIGUOUS_SCORE_THRESHOLD` do Recommendation Agent V11).

### 4.3 Confianca que mede encaixe, nao so a fonte

Hoje a confianca vem quase so da qualidade da evidencia (`confidence_score`
default 0.5), com teto `min(0.5, score*0.5)` para match de perfil. Resultado:
confianca estruturalmente baixa.

Nova confianca combina cinco fatores:

```txt
confianca = qualidade_da_fonte
          + clareza_do_sinal
          + proximidade_problema_x_tecnologia   (semantica, via retrieval)
          + numero_de_evidencias_independentes
          + existencia_de_dado_operacional_concreto
```

Decisao: confianca e fit sao **eixos separados**. Uma tech pode ter fit alto e
confianca baixa (faz sentido, mas falta evidencia) — e isso vira uma *hipotese
exploratoria* com perguntas de qualificacao, nao uma recomendacao forte.

### 4.4 Matriz de decisao por tecnologia

Cada tecnologia NVIDIA ganha criterios de entrada explicitos (em
`recommendations/domain/`), em vez de so uma lista de keywords. Exemplos:

```txt
NVIDIA Inception      startup ativa + sinal de uso/construcao de IA
                      -> beneficio em credito/networking/go-to-market/suporte
cuML / RAPIDS         workload ML classico + dataset tabular/analytics
                      + gargalo de treino/inferencia em CPU + maturidade p/ adotar
NVIDIA AI Enterprise  IA corporativa em producao + necessidade de governanca/
                      suporte/padronizacao + ambiente enterprise/regulado
Riva                  workload de fala (ASR/TTS/voz) declarado
NIM / Triton          inferencia em producao + necessidade de serving/escala
TensorRT-LLM          gargalo de latencia/custo por token em LLM em producao
```

Saida estruturada por recomendacao (alem de fit/confianca/complexity):

```txt
nivel              forte | moderada | exploratoria | sem fit
sinais_usados      quais sinais sustentaram (do StartupAIProfile + evidencias)
evidencias_usadas  evidence_ids rastreaveis
faltando           que informacao falta para subir de exploratoria a forte
motivo_rejeicao    quando NAO recomendar, por que (sem fit nao some, e explicado)
```

### 4.5 Nova estrutura de saida do briefing

A estrutura V1 (Resumo, Evidencias, Recomendacoes, Contexto NVIDIA, Riscos,
Proximas Acoes) foi substituida por uma que separa indicacao forte de hipotese
e expoe a incerteza:

```txt
1.  Resumo executivo            o que e a startup, em 2-3 linhas
2.  Tese de fit NVIDIA          a hipotese central de encaixe, em linguagem de negocio
3.  Nivel de confianca geral    alto | medio | baixo, com o porque
4.  O que foi encontrado        sinais concretos do StartupAIProfile + evidencias
5.  O que NAO foi encontrado    campos desconhecidos que mudariam a conclusao
6.  Matriz de recomendacoes     tabela: tecnologia x fit x confianca x nivel
7.  Recomendacoes fortes        acionaveis agora, com evidencia
8.  Hipoteses exploratorias     plausiveis, mas dependem de validacao
9.  Perguntas de qualificacao   o que perguntar ao fundador/time tecnico
10. Proximas acoes sugeridas    passo concreto por nivel de recomendacao
```

O briefing sempre deixa explicito: se a recomendacao e acionavel agora ou e
hipotese; quais evidencias a sustentam; o que falta; e qual pergunta fazer.

`build_briefing_markdown()` (`domain/policies.py`) continua puro (sem I/O); o
`GenerateBriefing` busca perfil/recomendacoes/contexto antes e passa tudo
montado para a policy. O Briefing Agent V12 reescreve a prosa por cima dessa
estrutura nova, com o mesmo fallback de citacoes de hoje.

### 4.6 Fluxo alvo da V4 (ponta a ponta)

```txt
evidencias coletadas
  -> Extraction Agent monta StartupAIProfile (campos + origem + field_confidence)
  -> retrieval semantico (embeddings/Qdrant) seleciona candidatos NVIDIA plausiveis
  -> Recommendation Agent (V11) raciocina fit/confianca/nivel sobre os candidatos
       . tools entregam docs NVIDIA citaveis (RAG)
       . codigo aplica matriz de decisao + guardas (piso/teto, elegibilidade)
  -> recomendacoes persistidas com nivel, sinais, faltando, motivo_rejeicao
  -> Briefing Agent (V12) monta a estrutura nova e reescreve a prosa executiva
  -> PDF (V3) preserva citacoes
```

---

## Briefing V5 — Golden Set e Metricas (implementado, 27/06/2026)

Entregue:

```txt
test_golden_set.py (recommendations/tests/unit/)
6 arquetipos de startups de referencia com perfil completo e assercoes de qualidade
media p@3 = 0.78 (piso assertado: 0.50)
10/10 testes passando
nenhum falso positivo para tecnologias claramente fora do perfil
helpers _precision_at_k(), _false_positive_slugs(), _slug_rank() para regressao futura
teste consolidado test_golden_set_overall_metrics com relatorio completo via capsys
```

Arquetipos cobertos:

```txt
LLM inference (AI-native, nlp, production)         -> NIM/Triton/TensorRT-LLM
API-only SaaS (AI-enabled, mvp)                    -> nenhuma recomendacao forte
SaaS sem IA (non_ai)                               -> nenhuma tech NVIDIA
Computer vision (AI-native, vision, pilot)         -> TensorRT/Triton
Tabular analytics (AI-enabled, analytics)          -> RAPIDS/cuDF/cuML
Enterprise MLOps (AI-native, mlops, scale)         -> AI Enterprise/Triton/NeMo
```

Ranking de oportunidades (comparacao em lote entre startups) continua planejado para V6.

---

## Briefing V6 — Robustez operacional (planejado)

```txt
versionar briefing e recomendacoes (hoje so substitui o anterior)
registrar modelo, prompt, fontes, custo e tempo por geracao
reprocessar por etapa (sem refazer a pipeline inteira)
expor no frontend o motivo de baixa confianca
separar erro tecnico de resultado inconclusivo
manter historico de aprovacoes/rejeicoes para calibrar o motor
```

---

## Criterios de aceite (do briefing robusto)

O briefing e considerado robusto quando:

- uma startup com evidencias fracas nao gera varias recomendacoes tecnicas rasas;
- toda recomendacao tecnica tem pelo menos dois sinais relevantes ou uma regra
  de elegibilidade explicita;
- toda recomendacao mostra evidencias ou declara que faltam;
- recomendacoes de baixa confianca aparecem como exploratorias, separadas das fortes;
- o usuario entende por que cada tecnologia foi (ou nao) recomendada;
- o sistema sugere perguntas objetivas quando falta informacao;
- testes unitarios cobrem falso positivo por palavra generica;
- existe golden set com startups de referencia e metricas rodando.

---

## Ordem pratica de implementacao

```txt
1. Breakdown de fit nas recomendacoes (expor sinais por recomendacao)         [ENTREGUE]
2. StartupAIProfile estruturado, com origem e field_confidence por campo       [ENTREGUE]
3. Score composto (4.2) + nova confianca (4.3), substituindo keyword puro      [ENTREGUE]
4. Retrieval semantico de candidatos NVIDIA                                   [ENTREGUE best-effort]
5. Matriz de decisao por tecnologia (4.4)                                      [ENTREGUE base]
6. Nova estrutura de saida do briefing (4.5) em build_briefing_markdown()      [ENTREGUE]
7. Golden set + metricas (V5)                                                  [ENTREGUE]
8. Frontend: separar fortes de exploratorias, expor motivo de baixa confianca  [ENTREGUE]
```

Os passos 1-3 e 6 sao puros em `domain/policies.py` dos dois modulos — sem rede,
sem migration nova alem de colunas, cobertos pela suite existente. Os passos 4-5
reaproveitam agentes e infra (Qdrant, embeddings, RAG) que ja existem. Nenhum
deles viola boundary: todo acesso cross-module continua via
`application/public/`.

---

## Como cada parte conversa com a arquitetura do projeto

| Decisao | Onde mora | Regra do CLAUDE.md respeitada |
|---|---|---|
| StartupAIProfile | dominio de `startups`, exposto via `application/public/` | 1 (boundary), 5 (dominio puro) |
| Score composto / confianca | `recommendations/domain/policies.py` (funcao pura) | 5 (dominio puro), 8 (so o necessario) |
| Raciocinio de fit por LLM | Recommendation Agent V11 (`agents`) | 6 (LLM so quando determinístico e insuficiente) |
| Guardas (piso/teto, elegibilidade, override) | codigo em `recommendations`/`agents` | 9 (saida do LLM validada por codigo) |
| Retrieval de candidatos | `rag`/`embeddings` via contrato publico | 1, 7 (Postgres fonte de verdade, Qdrant so similaridade) |
| Nova estrutura do briefing | `briefing/domain/policies.py` (puro) + Agent V12 reescreve prosa | 5, 6 |
| Rastreabilidade (sinais, evidence_ids, citacoes) | persistido em Postgres | 7, 10 (correlacao por IDs) |

---

## Documentos relacionados

```txt
docs/briefing/plano_fit_confiabilidade_briefing.md   diagnostico detalhado de origem
docs/briefing/briefing_v1_template_executivo.md      V1 entregue
docs/briefing/briefing_v3_export_pdf.md              V3 entregue
docs/recommendations/roadmap_recommendations.md      lado do fit (espelho deste doc)
docs/agents/agents_v11_recommendation_agent.md       agente de recomendacao (analista)
docs/agents/agents_v12_briefing_agent.md             agente de briefing (prosa)
docs/roadmap_produto_final.md                        prioridades transversais
```
