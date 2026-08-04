# Agents V1 - Integracao Inicial

## 1. Objetivo

Agents V1 cria a primeira versao funcional do modulo `agents`.

Ela nao e ainda o sistema multiagente completo com LangGraph.

Ela entrega uma base real para o primeiro caso de uso:

```txt
investigar evidencias quando a validacao semantica simples do scraper fica incerta
```

Nome recomendado:

```txt
Agents V1 - Evidence Validation Agent inicial
```

---

## 2. Escopo entregue

Implementado:

```txt
modulo agents criado
domain/enums.py
domain/exceptions.py
application/dto.py
application/public/semantic_investigator.py
infrastructure/llm/gemini_evidence_validator.py
factories/agents_factory.py
testes unitarios
```

O modulo ja possui um contrato publico consumido pelo scraping.

---

## 3. Contrato publico

Arquivo:

```txt
apps/api/src/modules/agents/application/public/semantic_investigator.py
```

Contrato:

```txt
EvidenceValidationService
  investigate(EvidenceValidationInput) -> EvidenceValidationResult
```

Outros modulos devem importar somente esse contrato publico.

Eles nao devem importar:

```txt
infrastructure/llm
graphs
prompts internos
factories internas
enums internos quando houver adaptador proprio
```

---

## 4. DTOs publicos

Entrada:

```txt
EvidenceValidationInput
```

Contem:

```txt
url
title
raw_text
scores deterministicos
problems e warnings deterministicos
fatores da revisao semantica simples
semantic_confidence
startup_id opcional
```

Saida:

```txt
EvidenceValidationResult
```

Contem:

```txt
decision
reason
```

---

## 5. Decisoes

Enum interno:

```txt
AgentDecision
```

Valores:

```txt
accepted
rejected
needs_more_sources
```

Significados:

```txt
accepted
-> evidencia suficiente para aceitar

rejected
-> conteudo nao deve ser aproveitado

needs_more_sources
-> uma pagina nao basta; faltam fontes adicionais
```

---

## 6. Implementacao atual

Arquivo:

```txt
infrastructure/llm/gemini_evidence_validator.py
```

Classe:

```txt
GeminiEvidenceValidator
```

Ela:

```txt
recebe EvidenceValidationInput
monta prompt de investigacao
chama Gemini generateContent por REST
exige JSON estruturado
valida resposta com Pydantic
devolve EvidenceValidationResult
```

Configuracao:

```txt
GEMINI_API_KEY
GEMINI_MODEL
```

---

## 7. Por que ainda nao e LangGraph

Esta V1 e uma ponte funcional.

Ela permite:

```txt
validar o contrato entre scraping e agents
testar o ponto de escalonamento
registrar auditoria
persistir efeitos no banco
evoluir sem quebrar scraping
```

LangGraph entra quando precisarmos de:

```txt
varios nodes
busca de fontes adicionais
loops controlados
checkpoint
human-in-the-loop
agent_worker
tools chamando outros modulos
```

---

## 8. Relacao com LangChain

Agents V1 ainda usa `httpx` no adaptador Gemini, assim como a V7 do scraper.

LangChain sera introduzido no proximo passo para:

```txt
ChatGoogleGenerativeAI
structured output
tools
mensagens
tracing
integracao com LangGraph
```

Isso evita adicionar LangChain antes de existir um grafo real.

---

## 9. Factory

Arquivo:

```txt
agents/factories/agents_factory.py
```

Responsabilidade:

```txt
ler settings
criar GeminiEvidenceValidator quando ha GEMINI_API_KEY
devolver None quando nao ha chave
```

Esse comportamento preserva execucao local sem custo de IA.

---

## 10. Integracao com scraping

O scraping usa:

```txt
AgentsSemanticInvestigator
```

Esse adapter traduz:

```txt
scraping InvestigationInput
-> agents EvidenceValidationInput

agents EvidenceValidationResult
-> scraping InvestigationResult
```

Assim, os dois modulos mantem vocabularios proprios.

---

## 11. Testes

Cobertura:

```txt
GeminiEvidenceValidator exige API key
GeminiEvidenceValidator exige model
resposta accepted e mapeada
resposta needs_more_sources e mapeada
resposta malformada gera AgentInvestigationError
decision invalida gera AgentInvestigationError
adapter scraping -> agents traduz campos corretamente
factory injeta agent no scraping quando ha chave
```

---

## 12. Estado validado

Depois da V8 scraping + Agents V1:

```txt
136 testes passando
Alembic head = d8e4a9c1b672
```

---

## 13. Limitacoes conhecidas

```txt
sem LangGraph real
sem LangChain
sem checkpoint
sem agent_worker
sem busca real de fontes
sem tools
sem human-in-the-loop
sem persistencia propria de agent_runs
```

---

## 14. Proximos passos

```txt
instalar LangGraph e LangChain
criar graphs/evidence_validation
criar EvidenceValidationState
criar nodes e routers deterministas
trocar GeminiEvidenceValidator simples por grafo compilado
adicionar tools publicas do scraping
adicionar checkpoint PostgreSQL
criar agent_worker
```

---

## 15. Criterio de conclusao da Agents V1

Agents V1 esta concluida porque:

```txt
existe modulo agents
existe contrato publico
existe implementacao funcional inicial
scraping consome o contrato por adapter
decisoes sao estruturadas
erros sao controlados
testes cobrem o contrato
```
