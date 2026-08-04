# Scraper V7 - Base da Validacao Semantica

## 1. Objetivo

A primeira parte da V7 prepara a pipeline para usar uma LLM somente quando o
conteudo e semanticamente ambiguo.

```txt
conteudo claramente bom
-> aceita sem LLM

conteudo tecnicamente ou textualmente ruim
-> fallback ou rejeita sem LLM

conteudo utilizavel, mas ambiguo
-> chama SemanticValidator
```

Esta etapa cria o nucleo independente de fornecedor. A implementacao concreta
atual usa Gemini e esta descrita em `scraper_v7_gemini.md`.

---

## 2. Por que existe uma porta

Contrato:

```txt
application/ports.py
-> SemanticValidator
```

A pipeline conhece somente essa porta.

Implementacoes futuras podem usar:

```txt
Gemini, implementacao atual
OpenAI
modelo local
outro provedor
servico interno
```

Trocar a tecnologia nao altera dominio, politica ou pipeline.

---

## 3. Politica de acionamento

`LLMReviewPolicy` seleciona apenas conteudo no intervalo ambiguo:

```txt
0.45 <= quality_score < 0.75
technical_score >= 0.70
text_score >= 0.60
sem problemas bloqueadores
```

Assim, a LLM nao e chamada para verificar:

```txt
captcha
HTML vazio
texto insuficiente
boilerplate critico
pagina dependente de JavaScript
conteudo claramente bom
```

Isso reduz custo e latencia.

---

## 4. Entrada semantica

`SemanticValidationInput` entrega somente o contexto atual:

```txt
URL final
titulo
texto bruto extraido
resultado da validacao deterministica
```

A validacao simples nao navega pela web, nao busca outras fontes e nao escolhe
tecnologias de scraping.

---

## 5. Saida estruturada

A LLM deve produzir um `SemanticAssessment` com fatores separados:

```txt
startup_match_score
evidence_clarity_score
source_reliability_score
statement_specificity_score
context_completeness_score
contradiction_detected
decision
reason
```

Decisoes permitidas:

```txt
accepted
rejected
needs_agent_review
```

A LLM nao fornece o `semantic_confidence` final.

---

## 6. Calculo da confianca

`SemanticConfidenceService` calcula:

```txt
semantic_confidence =
    startup_match_score * 0.25
    + evidence_clarity_score * 0.25
    + source_reliability_score * 0.20
    + statement_specificity_score * 0.15
    + context_completeness_score * 0.15
    - contradiction_penalty
```

Penalidade atual por contradicao:

```txt
0.30
```

Os fatores sao limitados entre `0` e `1`.

---

## 7. Regra conservadora

Uma revisao semantica somente aceita o conteudo quando:

```txt
decision = accepted
e
semantic_confidence >= 0.80
```

Abaixo de `0.80`, o conteudo continua rejeitado nesta etapa.

No futuro:

```txt
confidence < 0.80
ou contradiction_detected
ou needs_agent_review
-> encaminhar para agentes
```

---

## 8. Auditoria atual

Resultados aceitos semanticamente recebem metadados:

```txt
semantic_reviewed
semantic_decision
semantic_confidence
semantic_reason
semantic_contradiction_detected
```

A tentativa recebe warnings:

```txt
semantic_reviewed
semantic_decision_<decision>
```

Persistir esses valores em colunas dedicadas pode ser feito quando as regras
semanticas estiverem mais estaveis.

---

## 9. Estado atual

Implementado:

```txt
LLMReviewPolicy
SemanticValidator port
DTOs estruturados
SemanticConfidenceService
integracao opcional com a pipeline
aceitacao conservadora por confianca
testes sem depender de API externa
adaptador Gemini conectado pela factory
teste controlado com Gemini real
```

Ainda falta:

```txt
criar prompt versionado
registrar tokens, latencia e custo
adicionar retries para falhas transitorias
persistir campos semanticos em colunas dedicadas
integrar investigacao com agentes
```

---

## 10. Implementacao concreta

O adaptador concreto atual esta em:

```txt
infrastructure/semantic_validators/gemini_semantic_validator.py
```

Ele:

```txt
monta o prompt
chama Gemini por REST
valida JSON estruturado com Pydantic
converte a resposta para SemanticAssessment
traduz timeout, falhas HTTP e respostas invalidas
limita o texto enviado
```

Detalhes, configuracao e resultado do teste real ficam em
`scraper_v7_gemini.md`.
