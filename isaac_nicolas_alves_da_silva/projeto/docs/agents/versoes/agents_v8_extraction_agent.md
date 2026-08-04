# Agents V8 — Extraction Agent

Esta versao cria o Extraction Agent: extrai dados estruturados
(founders, estagio de funding, valor de funding, customers) das
evidencias de uma startup. Desbloqueado pelo Startups V2 (que deu ao
`Startup` os campos de destino) — segunda peca da sequencia acordada
apos o diagnostico do case original (Startups V2 → **Extraction Agent**
→ NVIDIA Knowledge V2 → NVIDIA RAG Agent → Recommendation Agent →
Briefing Agent).

## 1. Objetivo

```txt
perfil + evidencias da startup -> founders, funding_stage,
funding_amount_usd, customers (melhor esforco, nunca inventado)
```

## 2. Copia estrutural do Startup Classifier Agent

Mesma forma exata da entrega anterior (Agents V9), sem decisao nova de
arquitetura: grafo de 3 nodes (`prepare_context`, `extract_data`,
`finalize`), sem interrupt; contrato publico `ExtractionService`
(`application/public/extractor.py`); `LangChainGeminiExtractor`
(`infrastructure/llm/`) com `ChatGoogleGenerativeAI` +
`with_structured_output`; dois pontos de entrada (síncrono via
`startups`, mais o branch em `ExecuteAgentJob`/`ResumeAgentJob` por
consistência interna do modulo `agents`).

## 3. Anti-alucinacao no prompt, nao em codigo

Diferente da classificacao (que sempre produz uma resposta, mesmo que
"non_ai"), extracao deve devolver "nao sei" quando a evidencia nao
menciona o dado. Isso e tratado inteiramente via instrucao de prompt
("nunca infira, deduza ou invente... devolva lista vazia/'unknown'/null
quando nao mencionado") + schema Pydantic permissivo
(`founders`/`customers` com `default_factory=list`,
`funding_amount_usd: float | None = None`). O codigo nao tenta validar
"isso parece plausivel" — confia que o LLM, instruido corretamente,
devolve vazio em vez de inventar.

## 4. `ExtractedFundingStage` duplicado em `agents`

Mesmos valores de string que `startups.FundingStage` — mesmo padrao de
`StartupMaturityLevel`/`AiMaturityLevel` (Agents V9) e
`AgentDecision`/`AgentInvestigationDecision` (V1). Traducao por valor no
adapter `startups/infrastructure/agent_adapters/agents_extractor.py`.

## 5. Regenerar substitui o perfil extraido anterior

Mesma semantica de `Startup.classify()`: `POST
/startups/{id}/extract` repassa *todas* as evidencias atuais a cada
chamada e sobrescreve founders/funding/customers — sem merge
incremental. Ver limites.

## 6. Fluxo de ponta a ponta

```txt
POST /startups/{startup_id}/extract
  -> ExtractStartupProfile:
       busca startup + evidencias (uow propria)
       chama ExtractionPort.extract() (-> agents, via adapter)
       startup.update(founders=, funding_stage=, funding_amount_usd=,
                       customers=)
       persiste
  -> 200, StartupResponse com os 4 campos preenchidos
```

## 7. Validacao

Testes novos:

```txt
test_extraction_graph.py                2 testes (grafo com fake)
test_execute_agent_job.py (+2 casos)    sucesso + servico ausente
test_resume_agent_job.py (+1 caso)      servico ausente no resume
test_extract_startup_profile.py         3 testes (sucesso, startup
                                         ausente, extractor ausente)
```

Total apos esta entrega: `agents` 67 unit + 1 integracao; `startups` 27
unit + 1 integracao.

## 8. Limites conhecidos

```txt
sem merge incremental - reextrair sobrescreve founders/customers
  anteriores (mesmo limite documentado para classify())

sem interrupt()/revisao humana para extracoes incertas

funding_amount_usd e um unico valor em USD - mesmo limite ja registrado
  em Startups V2
```

## 9. Proximo passo

```txt
NVIDIA Knowledge V2 - ingestao real de documentacao NVIDIA (scraping ->
ingestion -> embeddings), proxima peca da sequencia acordada
```
