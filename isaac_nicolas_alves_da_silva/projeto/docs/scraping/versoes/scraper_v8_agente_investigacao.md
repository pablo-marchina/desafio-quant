# Scraper V8 - Integracao Inicial com Agents

## 1. Objetivo

A V8 conecta o modulo `scraping` ao novo modulo `agents`.

Ela cobre o caso em que a validacao deterministica e a revisao semantica
simples com Gemini nao sao suficientes para aceitar o conteudo com seguranca.

```txt
conteudo claramente bom
-> aceita sem Gemini

conteudo ruim de coleta
-> fallback ou rejeita sem Gemini

conteudo ambiguo
-> Gemini simples avalia

Gemini simples fica incerto
-> scraping chama modulo agents
```

Regra conceitual:

```txt
fallback corrige problema de coleta
LLM simples interpreta um conteudo isolado
agente investiga quando um conteudo isolado nao basta
```

---

## 2. Escopo real da V8

A V8 e uma integracao inicial com agents.

Ela entrega:

```txt
modulo agents criado
contrato publico de Evidence Validation Agent
adaptador scraping -> agents
pipeline escalona baixa confianca para agents
Gemini usado como primeira implementacao do agente
auditoria do agente em ScrapingAttempt
persistencia PostgreSQL dos campos de agente
migration aplicada
testes unitarios e integrados
```

Ela ainda nao entrega:

```txt
LangGraph real
LangChain
grafo com nodes e routers
checkpoint de agent runs
agent_worker
human-in-the-loop
tools chamando scraping, RAG ou recommendations
busca real de fontes adicionais
```

Nome recomendado:

```txt
V8 - Integracao inicial com modulo agents e Evidence Validation Agent
```

---

## 3. Fluxo atual

```txt
Scraper coleta conteudo
-> validadores deterministicos calculam scores
-> LLMReviewPolicy decide se chama Gemini simples
-> GeminiSemanticValidator devolve fatores
-> SemanticConfidenceService calcula semantic_confidence
```

Se:

```txt
decision = accepted
e
semantic_confidence >= 0.80
```

o conteudo e aceito.

Se:

```txt
decision = needs_agent_review
ou
semantic_confidence < 0.80
```

e existir `semantic_investigator`, a pipeline chama o modulo `agents`.

---

## 4. Contrato scraping -> agents

O scraping define uma porta:

```txt
application/ports.py
-> SemanticInvestigator
```

Entrada:

```txt
InvestigationInput
```

Saida:

```txt
InvestigationResult
```

O scraping nao importa grafo, node, prompt ou implementacao interna de agents.

---

## 5. Adaptador

Arquivo:

```txt
scraping/infrastructure/agent_adapters/agents_semantic_investigator.py
```

Responsabilidade:

```txt
traduz InvestigationInput do scraping
-> EvidenceValidationInput publico do agents

chama EvidenceValidationService

traduz EvidenceValidationResult do agents
-> InvestigationResult do scraping
```

Esse e o unico ponto em que scraping conhece o modulo `agents`, e ainda assim
conhece apenas o contrato publico.

---

## 6. Modulo agents V1

O primeiro contrato publico do modulo agents fica em:

```txt
agents/application/public/semantic_investigator.py
```

Ele expoe:

```txt
EvidenceValidationService
```

Implementacao atual:

```txt
agents/infrastructure/llm/gemini_evidence_validator.py
```

Essa implementacao faz uma chamada estruturada ao Gemini e decide:

```txt
accepted
rejected
needs_more_sources
```

Ela e uma ponte funcional antes do LangGraph completo.

---

## 7. Decisoes do agente

### accepted

```txt
pipeline muda decision para ACCEPT
ScrapingResult e produzido
metadata recebe agent_reviewed=true
attempt registra agent_reviewed=true
```

### rejected

```txt
attempt recebe status rejected
agent_reason guarda o motivo
pipeline levanta ContentRejectedError
job termina failed
```

### needs_more_sources

```txt
attempt recebe status needs_more_sources
agent_reason guarda o motivo
pipeline levanta MoreSourcesRequiredError
job termina failed nesta versao
```

No futuro, o fluxo global podera criar novos jobs de scraping para buscar mais
fontes e retomar a investigacao.

---

## 8. Mudancas no dominio scraping

### AttemptStatus

Novo status:

```txt
needs_more_sources
```

### AgentInvestigationDecision

Novo enum:

```txt
accepted
rejected
needs_more_sources
```

### ScrapingAttempt

Novos campos:

```txt
semantic_confidence
agent_reviewed
agent_reason
```

Novo metodo:

```txt
finish_needs_more_sources(reason)
```

`finish_validation` tambem passou a aceitar os campos de auditoria de agente.

### Exceptions

```txt
ContentRejectedError
MoreSourcesRequiredError
```

Ambas herdam de `ScrapingFailedError`, pois a tentativa nao produz
`ScrapingResult`.

---

## 9. Persistencia PostgreSQL

Tabela alterada:

```txt
scraping_attempts
```

Novas colunas:

```txt
semantic_confidence float nullable
agent_reviewed boolean not null default false
agent_reason text nullable
```

Migration:

```txt
d8e4a9c1b672_add_agent_fields_to_attempts
```

Estado aplicado:

```txt
Alembic head = d8e4a9c1b672
```

---

## 10. Factory

A `ScrapingFactory` agora:

```txt
cria GeminiSemanticValidator quando GEMINI_API_KEY existe
cria EvidenceValidationService pelo AgentsFactory
embrulha o servico com AgentsSemanticInvestigator
injeta semantic_investigator na ScrapingPipeline
```

Sem chave Gemini:

```txt
semantic_validator = None
semantic_investigator = None
```

O sistema continua funcionando sem custo de IA.

---

## 11. Auditoria

Tentativas podem registrar:

```txt
warnings:
  semantic_reviewed
  semantic_decision_<decision>
  agent_reviewed
  agent_decision_<decision>

campos:
  semantic_confidence
  agent_reviewed
  agent_reason
```

Resultados aceitos apos agente recebem metadata:

```txt
semantic_reviewed
semantic_decision
semantic_confidence
semantic_reason
semantic_contradiction_detected
agent_reviewed
agent_decision
agent_reason
```

---

## 12. Testes

Cobertura adicionada:

```txt
factory injeta semantic_investigator
factory desliga agent sem chave Gemini
adapter scraping -> agents traduz entrada e saida
GeminiEvidenceValidator valida resposta estruturada
pipeline aceita quando agente retorna accepted
pipeline rejeita quando agente retorna rejected
pipeline marca needs_more_sources
mapper preserva campos de agente
PostgreSQL persiste campos de agente
```

Estado da suite:

```txt
136 testes passando
```

---

## 13. Relacao com docs/agents

Documentos complementares:

```txt
docs/agents/modulo_agents_arquitetura.md
-> arquitetura completa desejada para o modulo agents

docs/agents/roadmap_agentes.md
-> estado atual e proximas versoes do modulo agents
```

Esta V8 implementa a primeira integracao funcional.

O LangGraph completo evoluiu nas versoes posteriores do modulo agents.

---

## 14. Limitacoes conhecidas

```txt
Evidence Validation Agent V1 ainda e uma chamada Gemini simples
nao ha LangGraph real
nao ha LangChain
nao ha busca de novas fontes
needs_more_sources ainda falha o job atual
nao ha checkpoint de agents
nao ha agent_worker
nao ha human-in-the-loop
```

---

## 15. Proximos passos

```txt
instalar LangGraph e LangChain
criar grafo evidence_validation
definir estado serializavel do grafo
criar nodes e routers pequenos
transformar contratos publicos em tools
adicionar checkpoint PostgreSQL
criar agent_worker
retomar needs_more_sources com novas fontes
```

---

## 16. Criterio de conclusao da V8

A V8 esta concluida porque:

```txt
scraping escala casos incertos para agents
agents possui contrato publico funcional
adapter preserva fronteira entre modulos
Gemini atua como primeira implementacao do agente
auditoria e persistencia foram atualizadas
migration foi aplicada
testes unitarios e integrados passam
```
