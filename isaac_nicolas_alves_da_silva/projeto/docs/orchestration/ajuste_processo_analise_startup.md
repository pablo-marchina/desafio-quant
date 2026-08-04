# Ajuste do Processo de Analise de Startup

Data: 2026-06-30

## Objetivo

Reduzir custo, latencia e estados parciais no fluxo de analise de startup.
Hoje o enrichment ja coleta fontes melhores, mas cada fonte enriquecida pode
rodar extraction, classification, recommendations e briefing de novo para a
mesma startup. Isso gera chamadas LLM repetidas, risco de corrida entre jobs e
briefings/recomendacoes sobrescritos varias vezes.

## Diagnostico Atual

Fluxo atual:

1. `url_ingestion_job` inicial raspa a URL principal.
2. Orchestration cria ou liga a startup.
3. Evidence e anexada.
4. Roda extraction best-effort.
5. Roda classification best-effort.
6. Agenda enrichment se faltam sinais.
7. Gera recommendations.
8. Gera briefing.
9. Cada enrichment job repete as etapas 3 a 8.

Exemplo observado com NeuralMind:

- Enrichment funcionou e coletou fontes externas reais:
  - BHTec
  - Revista Pesquisa FAPESP
  - Unicamp
- `ai_profile` foi preenchido corretamente.
- A startup saiu do piso `Inception 21%`.
- Foram geradas recomendacoes como NeMo, TensorRT-LLM, NeMo Guardrails e NIM.
- Ainda assim, houve job em `analyzing` com `recommendations_done=true` e
  `briefing_id=null`, indicando estado parcial/reprocessamento concorrente.

## Problemas a Corrigir

### P0 - Enrichment nao deve reprocessar analise completa

Problema:

Cada fonte enriquecida chama:

- `try_extract`
- `try_classify`
- `recommendations.generate`
- `briefing.generate`

Arquivo principal:

- `apps/api/src/modules/orchestration/application/use_cases/advance_url_ingestion_job.py`

Impacto:

- Custo alto de LLM.
- Varias geracoes concorrentes para a mesma startup.
- Recomendacoes e briefing sao substituidos multiplas vezes.
- Estado parcial quando uma etapa final falha depois de recomendacoes ja terem sido salvas.

Direcao de solucao:

- Enrichment jobs devem anexar evidencia e terminar como coleta.
- A analise consolidada deve rodar uma unica vez apos a coleta inicial e os
  enrichments esperados, ou via job de analise separado por startup.

Opcao recomendada para MVP:

1. Job inicial agenda enrichment quando perfil esta incompleto.
2. Enrichment jobs apenas raspam, ingerem, embedam e anexam evidencia.
3. Quando um enrichment job termina, ele dispara ou marca uma analise pendente
   por startup.
4. Um unico analysis job por startup roda extraction, classification,
   recommendations e briefing usando todas as evidencias disponiveis.

Criterios de aceite:

- Uma URL inicial com 3 fontes enriquecidas gera no maximo 1 rodada final de
  recommendations e briefing por startup.
- Enrichment jobs completam sem sobrescrever briefing individualmente.
- Nao fica job em `analyzing` com `recommendations_done=true` e `briefing_id=null`.
- Logs mostram claramente: `evidence attached`, depois `startup analysis scheduled`
  ou `startup analysis already pending`.

Testes sugeridos:

- Unitario em orchestration: enrichment job com `parent_job_id` anexa evidencia
  mas nao chama recommendations/briefing.
- Unitario: job inicial incompleto agenda enrichments e nao gera briefing final
  antes das evidencias complementares quando houver busca disponivel.
- Unitario: multiplos enrichments para a mesma startup nao disparam multiplas
  analises finais.

## P1 - Reusar limpeza de evidencia na classificacao

Problema:

`ExtractStartupProfile` ja compacta e remove ruido antes do LLM, mas
`ClassifyStartup` ainda envia `title + notes` cru.

Arquivo:

- `apps/api/src/modules/startups/application/use_cases/classify_startup.py`

Direcao de solucao:

- Reusar `_compact_evidence_text` ou mover o helper para um modulo compartilhado
  dentro de `startups/application/`.
- Aplicar a mesma limpeza em `ClassifyStartup`.
- Melhorar log de timeout igual ao extractor.

Criterios de aceite:

- Classificacao nao recebe linhas obvias de menu, newsletter, cookies e rodape.
- Timeout de classificacao, se ocorrer, aparece como `timeout after Ns`, nao
  como `reason=""`.

Testes sugeridos:

- Unitario: classifier recebe evidencia compactada.
- Unitario: conteudo tecnico relevante e preservado.
- Unitario: timeout gera log com motivo explicito.

## P1 - Melhorar inferencia de tipo de evidencia

Problema:

A inferencia atual por substring classifica algumas fontes de forma fraca.
Exemplo observado:

- Terra ficou como `website`.
- FAPESP ficou como `technical`.

Arquivo:

- `apps/api/src/modules/startups/application/use_cases/add_startup_evidence.py`

Direcao de solucao:

- Criar allowlist de hosts de noticia/institucionais igual ou derivada da lista
  de enrichment.
- Checar host da URL antes do texto completo.
- Classificar como:
  - `NEWS`: imprensa, hubs de inovacao, governo/universidade com noticia/release.
  - `TECHNICAL`: GitHub, docs, jobs, careers, engineering, API, stack.
  - `BLOG`: blog proprio ou engenharia editorial.
  - `WEBSITE`: dominio da propria startup sem sinal tecnico/noticia.

Criterios de aceite:

- `terra.com.br`, `revistapesquisa.fapesp.br`, `bhtec.org.br`,
  `parque.inova.unicamp.br` nao caem como `website` quando forem releases/noticias.
- GitHub/vagas continuam como `technical`.

Testes sugeridos:

- Unitarios em `test_startup_use_cases.py` ou arquivo dedicado para
  `_infer_evidence_type`.

## P1 - Recuperacao de estado parcial

Problema:

Pode haver job em `analyzing` com:

- evidence anexada
- recommendations geradas
- briefing ausente

Direcao de solucao:

- Tornar `_run_analysis` mais granular/idempotente:
  - se `recommendations_done=true`, nao gerar de novo.
  - se `briefing_id` esta ausente, tentar apenas briefing.
  - se briefing existe para startup mas job nao registrou, registrar no job.
- Melhorar `reason` em falhas de analise com `str(error) or repr(error)`.

Arquivo:

- `apps/api/src/modules/orchestration/application/use_cases/advance_url_ingestion_job.py`

Criterios de aceite:

- Reentregar um job `analyzing` parcial conclui sem duplicar recomendacoes.
- Se briefing ja existe para a startup, o job consegue registrar ou regenerar
  deterministicamente.

Testes sugeridos:

- Unitario: job com `recommendations_done=true` e `briefing_id=None` chama apenas
  briefing.
- Unitario: excecao com `str(error)==""` fica logada com `repr(error)`.

## P2 - Descobrir links internos reais

Problema:

O enrichment same-domain ainda usa paths fixos (`/sobre`, `/about`, `/blog`).
Isso melhorou com limite de 1 slot, mas ainda causa 404/rejeicoes.

Direcao de solucao:

- Expor links internos extraidos da home pelo scraping/ingestion.
- Orchestration prioriza links reais antes de paths fixos.
- Heuristica de relevancia:
  - about/sobre
  - produto/solucoes/platform
  - blog/cases/clientes
  - carreiras/jobs/engineering

Criterios de aceite:

- Quando a home contem link real para pagina de produto/case, o enrichment usa
  esse link.
- Reduzir jobs same-domain rejeitados por URL inexistente.

## P2 - Extrair corpo principal no scraping

Problema:

A limpeza antes do LLM reduz ruido, mas o scrape ainda salva texto bruto com
menu/rodape em alguns casos.

Direcao de solucao:

- Melhorar uso de Trafilatura para fontes de noticia/artigo.
- Para paginas com muito boilerplate, preferir `main_content_extracted=true`
  quando houver extração bem-sucedida.
- Preservar raw original para auditoria se necessario, mas expor texto limpo
  para extraction/classification.

Criterios de aceite:

- Conteudos como newsletter, menu, politica de privacidade e publicidade nao
  dominam `notes` usados em startup evidence.
- Word count util melhora sem rejeitar fontes validas.

## Plano de Implementacao Sugerido

### Passo 1 - Separar coleta enriquecida de analise final

Arquivos:

- `advance_url_ingestion_job.py`
- testes unitarios de orchestration

Implementar:

- Detectar `job.parent_job_id is not None` ou `job.enrichment_round > 0`.
- Para enrichment job:
  - anexar evidencia
  - salvar job
  - nao chamar recommendations/briefing
  - agendar analise consolidada ou marcar pendencia.

### Passo 2 - Compactar classificacao

Arquivos:

- `classify_startup.py`
- helper compartilhado de limpeza em startups

Implementar:

- Mover helper de compactacao para arquivo reutilizavel.
- Aplicar em extraction e classification.

### Passo 3 - Corrigir tipos de evidencia

Arquivos:

- `add_startup_evidence.py`
- testes de startups

Implementar:

- Host-based classification para NEWS/TECHNICAL.

### Passo 4 - Recovery de jobs parciais

Arquivos:

- `advance_url_ingestion_job.py`
- repository de briefings se precisar lookup por startup

Implementar:

- Reentrada idempotente em `ANALYZING`.

## Queries de Auditoria Operacional

```sql
select status, count(*)
from url_ingestion_jobs
group by status
order by status;
```

```sql
select id, url, status, enrichment_round, evidence_attached,
       recommendations_done, recommendation_count, briefing_id, error_message
from url_ingestion_jobs
order by created_at desc
limit 20;
```

```sql
select s.name, s.ai_maturity_level, s.field_confidence, s.ai_profile
from startups s
order by s.created_at desc
limit 10;
```

```sql
select startup_id, technology_slug, nivel, score, confidence
from recommendations
order by created_at desc
limit 20;
```

## Resultado Esperado

Depois dos ajustes:

- Coleta fica multi-fonte, mas analise fica consolidada.
- Custo de LLM cai.
- Recomendacoes e briefing deixam de oscilar entre enrichment jobs.
- `ai_profile` e `field_confidence` continuam preenchidos.
- Casos como NeuralMind mantem recomendacoes fortes/moderadas em vez de voltar
  para Inception exploratorio.
