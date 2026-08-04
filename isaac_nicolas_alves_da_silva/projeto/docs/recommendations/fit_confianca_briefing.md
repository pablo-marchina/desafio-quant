# Fit e confianca no briefing

Atualizado em 29/06/2026.

Este documento registra como melhorar a leitura de `fit` e `confianca` nas
recomendacoes NVIDIA exibidas no briefing. O objetivo e reduzir falsos positivos,
evitar scores baixos demais quando ha evidencia semantica boa e deixar claro para
o usuario o que falta para uma recomendacao ficar mais forte.

## 1. Problema atual

Hoje o motor de recomendacao usa uma politica deterministica em
`apps/api/src/modules/recommendations/domain/policies.py`.

O score de fit combina:

```txt
fit = 0.35 * workload_alignment
    + 0.25 * evidence_signal
    + 0.15 * startup_maturity
    + 0.15 * keyword_prior
    + 0.10 * implementation_viability
```

A confianca combina:

```txt
confidence = source_quality
           + signal_clarity
           + workload_proximity
           + evidence_depth
           + operational_signal
```

Isso e bom como baseline, mas tem tres problemas praticos:

1. A confianca fica baixa quando so existe uma fonte, mesmo que a fonte seja boa.
2. O match por keyword nao entende negacao ou contexto.
3. O briefing mistura duas perguntas diferentes:
   - "essa tecnologia parece fazer sentido?"
   - "temos evidencia suficiente para afirmar isso com seguranca?"

## 2. Definicao correta

### Fit

Fit deve responder:

```txt
Esta tecnologia NVIDIA resolve um problema provavel desta startup?
```

O fit pode ser moderado mesmo com poucas fontes, desde que a evidencia indique um
workload claro. Exemplo: uma startup com agentes de IA e busca semantica pode ter
fit plausivel com NIM, NeMo Guardrails ou RAG, mesmo sem revelar a stack tecnica.

### Confianca

Confianca deve responder:

```txt
Quao bem as fontes sustentam esta recomendacao?
```

Confianca nao e a mesma coisa que fit. Uma recomendacao pode ter:

```txt
fit alto + confianca baixa
```

Isso significa: "parece fazer sentido, mas ainda faltam provas".

## 3. Regra de fontes

Mais fontes ajudam, mas apenas quando trazem informacao nova ou independente.

| Fontes validas | Interpretacao |
|---|---|
| 1 fonte boa | Hipotese exploratoria |
| 2 fontes boas e independentes | Pode virar moderada |
| 3 fontes boas, independentes e consistentes | Pode sustentar confianca alta |
| 4+ fontes | So vale se trouxerem sinal novo |

Tipos de fonte por valor:

| Tipo de fonte | Valor para confianca |
|---|---|
| Site oficial / pagina de produto | Bom para entender proposta |
| Blog tecnico / docs / API / GitHub | Muito bom para fit tecnico |
| Case de cliente / parceria / noticia confiavel | Bom para validacao externa |
| LinkedIn / Crunchbase / base de startups | Bom para dados institucionais |
| Texto duplicado, pagina generica ou marketing vago | Baixo valor |

Regra importante:

```txt
Mais duas fontes ruins nao devem aumentar confianca.
Uma fonte tecnica forte pode valer mais que tres fontes genericas.
```

## 4. Falsos positivos que precisam ser bloqueados

O match atual pode interpretar palavras fora de contexto.

Exemplos:

| Texto encontrado | Risco |
|---|---|
| "no training on your data" | Nao deve contar como sinal positivo de training |
| "we do not train models on customer data" | Nao deve puxar NeMo por fine-tuning |
| "AI agent" em texto generico | Nao deve virar fit forte sozinho |
| "model agnostic" | Nao prova treinamento, serving ou GPU |
| "powered by AI" | Nao prova workload tecnico |

Acao imediata:

```txt
Adicionar negative patterns por keyword.
```

Exemplo:

```txt
keyword: training
negative_patterns:
  - "no training"
  - "do not train"
  - "not train"
  - "without training"
  - "never train"
```

## 5. Melhor desenho para V6

O ideal e manter o motor deterministico como filtro inicial e adicionar uma etapa
semantica com LLM.

Fluxo proposto:

```txt
Evidence raw text
  -> claim extraction
  -> deterministic candidate generation
  -> LLM recommendation judge
  -> calibrated fit/confidence/nivel
  -> briefing explicavel
```

### 5.1 Claim extraction

Antes de recomendar, cada evidencia deveria virar claims estruturadas:

```txt
{
  "type": "ai_product",
  "claim": "A startup oferece assistente de IA para equipes",
  "source_id": "...",
  "confidence": 0.78
}
```

Tipos iniciais:

| Claim type | Uso |
|---|---|
| ai_product | Prova que o produto usa IA |
| ai_agent | Sinal de agentes ou copilotos |
| rag_search | Sinal de busca semantica/RAG |
| workflow_automation | Automacao de processos |
| model_customization | Fine-tuning, custom models, adapters |
| inference_serving | Serving, API, deployment de modelo |
| training | Treino ou retreino real de modelo |
| governance_security | Guardrails, seguranca, compliance |
| customer_signal | Cliente, case, tracao |
| funding_signal | Rodada, aceleradora, investidor |
| brazil_signal | Sinal de startup brasileira |

### 5.2 LLM recommendation judge

Depois do match deterministico, um judge semantico deve revisar cada candidato.

Entrada:

```txt
startup profile
evidence claims
technology candidate
matched keywords
score_breakdown
current fit/confidence
```

Saida estruturada:

```txt
{
  "semantic_fit_score": 0.0,
  "semantic_confidence": 0.0,
  "evidence_strength": "weak | product_clear | technical_clear | validated",
  "technical_specificity": "none | product | workload | infrastructure",
  "recommended_level": "exploratoria | moderada | forte",
  "supporting_claims": [],
  "missing_proofs": [],
  "reason": ""
}
```

## 6. Guardrails para o LLM

O judge semantico precisa de travas para nao alucinar.

Regras:

1. Nao pode recomendar como `forte` com apenas uma fonte institucional.
2. Nao pode inferir GPU, fine-tuning ou treino sem evidencia explicita.
3. Nao pode aumentar confianca acima de 0.70 sem fonte tecnica ou independente.
4. Nao pode usar frase negativa como sinal positivo.
5. Deve separar "usa IA no produto" de "tem workload tecnico NVIDIA".
6. Para startup brasileira, deve priorizar fontes brasileiras quando existirem.

## 7. Calibragem de nivel

Proposta de interpretacao:

| Nivel | Condicao |
|---|---|
| Exploratoria | Fit plausivel, mas pouca evidencia |
| Moderada | Fit claro com 2 fontes ou uma fonte tecnica forte |
| Forte | Fit claro, evidencia independente e sinal tecnico/operacional |

Caps recomendados:

| Evidencia disponivel | Confianca maxima sugerida |
|---|---|
| Apenas marketing generico | 0.45 |
| Uma fonte oficial clara | 0.60 |
| Uma fonte tecnica oficial | 0.68 |
| Duas fontes independentes | 0.75 |
| Fonte tecnica + validacao externa | 0.85 |

## 8. Como explicar no briefing

O briefing nao deve mostrar apenas um numero. Ele deve mostrar o motivo.

Formato sugerido:

```txt
Fit: 62%
Confianca: Moderada

Por que faz sentido:
- A startup possui produto com agentes de IA.
- Ha sinais de workflow automation e governanca.

Por que ainda nao e forte:
- Nao ha evidencia tecnica de deployment ou fine-tuning.
- Falta fonte independente validando uso em producao.

Como elevar:
- Encontrar docs, API, case tecnico ou vaga de engenharia.
- Confirmar se ha RAG, serving de modelo, fine-tuning ou guardrails.
```

## 9. Mudancas recomendadas no codigo

### Curto prazo

1. Criar negative patterns em `recommendations/domain/policies.py`.
2. Separar keywords fortes e fracas por tecnologia.
3. Ajustar confianca para reconhecer uma fonte tecnica forte.
4. Melhorar `faltando` para explicar "por que a confianca nao subiu".
5. No frontend, renomear visualmente para:
   - `Fit tecnico`
   - `Confianca da evidencia`

### Medio prazo

1. Criar claim extraction em cima das evidencias.
2. Persistir claims em JSONB ou campo equivalente.
3. Criar LLM recommendation judge.
4. Salvar `semantic_fit_score` e `semantic_confidence`.
5. Versionar geracoes de recomendacao.

### Longo prazo

1. Criar golden dataset de startups brasileiras.
2. Medir precision@3, recall@5 e taxa de falso positivo forte.
3. Calibrar thresholds por feedback humano.
4. Separar modelos de avaliacao para:
   - AI-native
   - AI-enabled
   - non-AI

## 10. Golden dataset necessario

Para calibrar de verdade, o projeto precisa de um conjunto rotulado.

Dataset inicial criado:

```txt
docs/recommendations/datasets/golden_startups_br20.json
```

Script para submeter no backend local:

```txt
docs/recommendations/scripts/submit_golden_startups_br20.ps1
```

Tamanho inicial recomendado:

```txt
30 a 50 startups brasileiras
```

Distribuicao:

```txt
10 AI-native
15 AI-enabled
10 non-AI
5 casos ambiguos
```

Para cada startup:

```txt
nome
website
pais
fontes usadas
ai_maturity esperado
tecnologias NVIDIA esperadas
nivel esperado
confianca esperada
justificativa humana
evidencias que faltam
```

Metricas:

```txt
precision@3 de tecnologias recomendadas
recall@5 de tecnologias esperadas
false strong recommendation rate
confidence calibration error
taxa de evidencias insuficientes
```

## 11. Criterios de aceite

A melhoria deve ser considerada pronta quando:

1. Frases negativas de training nao gerarem recomendacao indevida de NeMo.
2. Uma startup AI-enabled nao virar AI-native por marketing generico.
3. O briefing explicar por que a confianca esta baixa.
4. Mais fontes so elevarem confianca quando forem independentes ou tecnicas.
5. Recomendacoes fortes exigirem evidencia operacional ou tecnica.
6. O golden dataset manter precision@3 acima de 0.75.

## 12. Decisao de produto

Nao devemos tentar transformar o score em uma verdade absoluta.

O briefing deve comunicar:

```txt
Esta e a melhor hipotese com as evidencias atuais.
```

E deve deixar claro:

```txt
O que sabemos.
O que inferimos.
O que ainda falta provar.
```

## 13. Solucao definitiva proposta

A solucao mais robusta nao e apenas "buscar mais fontes" nem apenas "usar LLM".
O desenho correto e uma decisao em camadas:

```txt
1. Coletar fontes
2. Remover duplicatas e classificar qualidade da fonte
3. Extrair claims estruturadas
4. Gerar candidatos NVIDIA por regra deterministica
5. Julgar semanticamente cada candidato com LLM
6. Aplicar caps e guardrails
7. Mostrar no briefing fit, confianca e lacunas
```

Com isso, o sistema deixa de perguntar somente:

```txt
Quantas keywords bateram?
```

E passa a perguntar:

```txt
Qual claim esta sendo sustentada, por qual fonte, e com que especificidade?
```

## 14. Modelo mental de dados

Para resolver de vez, precisamos separar quatro entidades conceituais.

### Source

A fonte original.

```txt
url
title
publisher/domain
source_type
is_first_party
is_independent
is_technical
is_duplicate
retrieved_at
```

### Claim

Uma afirmacao extraida da fonte.

```txt
claim_type
claim_text
source_id
claim_confidence
positive_or_negative
```

### Candidate

Uma tecnologia NVIDIA possivelmente relevante.

```txt
technology_slug
deterministic_score
matched_keywords
matched_claims
missing_signals
```

### Judgment

A decisao final calibrada.

```txt
semantic_fit_score
semantic_confidence
recommended_level
evidence_strength
technical_specificity
supporting_claims
missing_proofs
```

Essa separacao evita que `confidence_score` de scraping seja usado como se fosse
confianca da recomendacao. Uma coisa e a qualidade da fonte; outra e o quanto a
fonte prova fit com NVIDIA.

## 15. Score de fonte

Cada fonte deve receber um valor de utilidade para recomendacao.

| Tipo de fonte | Base |
|---|---:|
| Docs, API, changelog, blog tecnico, GitHub | 0.90 |
| Case de cliente, parceria, noticia confiavel | 0.80 |
| Site oficial ou pagina de produto | 0.65 |
| LinkedIn, Crunchbase, Distrito, Latitud, Abstartups | 0.55 |
| Landing page generica | 0.40 |
| Texto duplicado ou sem claim novo | 0.10 |

Ajustes:

| Condicao | Ajuste |
|---|---:|
| Fonte independente | +0.10 |
| Fonte brasileira confiavel para startup BR | +0.05 |
| Fonte tecnica com detalhe de workload | +0.10 |
| Fonte so repete outra | -0.30 |
| Fonte muito antiga sem contexto atual | -0.10 |
| Conteudo vago de marketing | -0.15 |

Cap:

```txt
source_quality = min(1.0, max(0.0, base + ajustes))
```

## 16. Score de claim

Claims devem ter pesos diferentes. Dizer "usa IA" nao tem o mesmo valor que
dizer "faz fine-tuning de LLMs proprietarios".

| Claim | Forca |
|---|---:|
| Produto usa IA de forma clara | 0.55 |
| Agente/copiloto/automacao com IA | 0.65 |
| RAG, busca semantica, embeddings ou retrieval | 0.75 |
| Serving, inference API, deployment de modelo | 0.80 |
| Fine-tuning, training, custom model explicito | 0.85 |
| GPU, CUDA, NVIDIA, Triton, NIM, NeMo explicito | 0.95 |
| Cliente/case validando uso em producao | 0.80 |
| Funding/aceleracao sem prova tecnica | 0.45 |

Claims negativas precisam bloquear ou reduzir score.

Exemplos:

```txt
"no training on your data" -> negative claim para training
"powered by third-party AI" -> reduz fit com treinamento proprio
"AI-ready" sem produto -> marketing fraco
```

## 17. Nova formula de fit

O fit deve ficar mais semantico e menos dependente de keyword.

Formula proposta:

```txt
semantic_fit =
    0.40 * workload_match
  + 0.25 * problem_solution_match
  + 0.15 * maturity_readiness
  + 0.10 * nvidia_specificity
  + 0.10 * implementation_viability
```

Definicoes:

| Campo | Significado |
|---|---|
| workload_match | O workload da startup combina com a tecnologia NVIDIA? |
| problem_solution_match | A tecnologia resolve uma dor real descrita nas evidencias? |
| maturity_readiness | A startup parece pronta para usar a tecnologia? |
| nvidia_specificity | Ha motivo para NVIDIA, nao apenas "qualquer IA"? |
| implementation_viability | Complexidade da tecnologia faz sentido para o estagio da startup? |

Interpretacao:

| Fit | Leitura |
|---|---|
| 0.00 - 0.34 | Fraco |
| 0.35 - 0.54 | Exploratorio |
| 0.55 - 0.74 | Bom |
| 0.75 - 1.00 | Forte |

## 18. Nova formula de confianca

A confianca deve medir sustentacao das evidencias.

Formula proposta:

```txt
semantic_confidence =
    0.30 * source_quality
  + 0.25 * claim_strength
  + 0.20 * technical_specificity
  + 0.15 * independent_confirmation
  + 0.10 * operational_signal
```

Definicoes:

| Campo | Significado |
|---|---|
| source_quality | Qualidade media das fontes usadas |
| claim_strength | Forca das claims que sustentam a recomendacao |
| technical_specificity | Nivel de detalhe tecnico |
| independent_confirmation | Confirmacao por fonte nao controlada pela startup |
| operational_signal | Sinal de producao, clientes, escala ou case |

Caps obrigatorios:

| Evidencia disponivel | Cap de confianca |
|---|---:|
| So marketing generico | 0.45 |
| Uma fonte oficial clara | 0.60 |
| Uma fonte tecnica oficial | 0.68 |
| Duas fontes independentes sem detalhe tecnico | 0.72 |
| Fonte tecnica + fonte independente | 0.82 |
| Fonte tecnica + case/cliente/producao | 0.90 |

Regra essencial:

```txt
A formula calcula a confianca, mas o cap impede excesso de certeza.
```

## 19. Politica de busca extra

O sistema deve buscar mais fontes apenas quando isso pode mudar a decisao.

Buscar mais fontes quando:

```txt
confidence < 0.65
ou nivel != forte
ou falta claim tecnica
ou falta validacao independente
ou ha conflito AI-native vs AI-enabled
ou ha recomendacao NVIDIA complexa com pouca evidencia
```

Nao buscar mais fontes quando:

```txt
ja existem 3 fontes boas e diferentes
ou a ultima rodada nao adicionou claim novo
ou a recomendacao ja bateu o cap permitido
ou a startup nao tem sinais minimos de IA
ou duas rodadas falharam em achar fonte melhor
```

Ordem de busca:

1. Fonte tecnica.
2. Fonte independente.
3. Fonte institucional complementar.

Queries sugeridas por lacuna:

| Lacuna | Query |
|---|---|
| Falta workload tecnico | `{startup} AI API docs engineering blog architecture` |
| Falta fine-tuning/training | `{startup} fine tuning custom model LLM training` |
| Falta inference/deployment | `{startup} inference API model deployment production` |
| Falta RAG/embeddings | `{startup} retrieval augmented generation embeddings semantic search` |
| Falta validacao externa | `{startup} funding customers case study interview Brazil` |
| Falta sinal BR | `{startup} startup brasileira fundadores CNPJ LinkedIn` |

Para startups brasileiras, adicionar sempre uma rodada com:

```txt
Brasil OR brasileira OR founders OR fundadores OR Startups.com.br OR Distrito OR Latitud
```

## 20. Politica de decisao final

O nivel final deve depender de fit e confianca juntos.

| Fit | Confianca | Nivel |
|---|---|---|
| Alto | Alta | Forte |
| Alto | Media | Moderada |
| Medio | Media | Moderada |
| Alto | Baixa | Exploratoria com prioridade de pesquisa |
| Baixo | Alta | Nao recomendar ou listar como nao-fit |
| Baixo | Baixa | Nao recomendar |

Regras duras:

1. `forte` exige fit >= 0.65 e confianca >= 0.65.
2. `forte` exige fonte tecnica ou fonte independente com validacao operacional.
3. `moderada` exige fit >= 0.50 e confianca >= 0.45.
4. `exploratoria` pode existir com fit >= 0.35, mas deve mostrar lacunas.
5. Se houver claim negativa direta, a tecnologia afetada deve cair ou sumir.

## 21. Como lidar com AI-native, AI-enabled e non-AI

A classificacao de maturidade deve influenciar a recomendacao, mas nao dominar.

| Maturidade | Efeito no motor |
|---|---|
| AI-native | Pode abrir tecnologias mais profundas, como NeMo, NIM, Triton, RAPIDS |
| AI-enabled | Priorizar tecnologias de integracao, agentes, guardrails, RAG, serving leve |
| non-AI | Nao recomendar stack NVIDIA pesada sem evidencia tecnica nova |

Regra importante:

```txt
AI-enabled nao deve virar NeMo training so porque aparece "AI assistant".
AI-native nao deve receber fit forte sem workload ou problema tecnico claro.
```

## 22. Mudanca minima para implementar primeiro

Para melhorar rapido sem criar migration, a primeira entrega deve ser:

```txt
1. Negative patterns no matcher deterministico.
2. Source quality calculado em memoria a partir da URL/tipo da evidencia.
3. Caps de confianca aplicados antes de salvar Recommendation.
4. Faltando mais explicativo:
   - falta fonte tecnica
   - falta fonte independente
   - falta workload explicito
   - frase negativa bloqueou keyword
5. Frontend trocar "conf." por "confianca da evidencia".
```

Isso ja resolve grande parte da confusao sem depender do LLM judge.

## 23. Entrega ideal de V6

Depois da mudanca minima, a V6 completa deve entregar:

```txt
RecommendationEvidenceClaim
RecommendationSemanticJudge
semantic_fit_score
semantic_confidence
evidence_strength
technical_specificity
supporting_claims
missing_proofs
source_quality_breakdown
```

Possivel migration:

```txt
recommendations.semantic_fit_score float nullable
recommendations.semantic_confidence float nullable
recommendations.evidence_strength text nullable
recommendations.technical_specificity text nullable
recommendations.supporting_claims jsonb not null default []
recommendations.missing_proofs jsonb not null default []
recommendations.source_quality_breakdown jsonb not null default {}
```

O campo antigo `score` pode continuar existindo como fit deterministico, mas o
briefing deve preferir `semantic_fit_score` quando disponivel.

## 24. Exemplo pratico: Notion

Se a evidencia diz:

```txt
Meet your AI team
Enterprise search
AI agents
No training on your data
```

Claims corretas:

```txt
ai_product: positivo
ai_agent: positivo
rag_search: possivel
governance_security: positivo
training: negativo
```

Resultado esperado:

```txt
NeMo training: nao deve subir por "no training"
NeMo Guardrails: fit plausivel
NIM: fit exploratorio/moderado se houver sinal de serving ou LLM app
RAPIDS/Triton: nao recomendar sem workload tecnico
```

Briefing esperado:

```txt
Fit bom para governanca/agentes.
Confianca moderada se houver fonte oficial clara.
Nao ha prova suficiente para recomendar treinamento/fine-tuning.
Buscar docs, blog tecnico ou case para elevar.
```

## 25. Resultado esperado no produto

Depois dessas mudancas, o briefing deve parar de parecer arbitrario.

O usuario deve conseguir entender:

```txt
Por que essa tecnologia apareceu.
Por que o fit esta nesse nivel.
Por que a confianca nao subiu.
Que fonte precisa ser encontrada para mudar a decisao.
Qual parte foi evidencia e qual parte foi inferencia.
```

Esse e o ponto em que o sistema passa de "classificador com score" para
"analista assistido por IA".
