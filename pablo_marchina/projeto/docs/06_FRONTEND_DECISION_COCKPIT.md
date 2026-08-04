# 06 — Frontend: NVIDIA Startup Decision Cockpit

## Responsabilidade deste documento

Este documento descreve apenas o frontend: telas, ordem de informação, contratos consumidos, componentes e como a UI deve mostrar tudo que a pipeline coletou e gerou. Ele não detalha lógica interna de scraping, LangGraph, RAG ou motor de recomendação.

## Objetivo do frontend

O frontend não é apenas um dashboard técnico. Ele é o cockpit de decisão do case. A função principal é mostrar, em ordem de importância para a NVIDIA:

1. qual decisão tomar sobre a startup;
2. por que essa startup importa;
3. qual tecnologia NVIDIA recomendar;
4. qual evidência sustenta a recomendação;
5. quais gaps e riscos existem;
6. o que falta validar;
7. qual foi o caminho completo da pipeline.

## Tecnologias usadas

| Tecnologia | Uso |
|---|---|
| React 19 | UI componentizada |
| TypeScript 6 | tipagem de contratos e componentes |
| Vite 8 | dev/build frontend |
| Playwright | testes E2E |
| CSS próprio | layout e estilos do cockpit |
| Fetch API | chamadas HTTP ao backend |

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `frontend/src/App.tsx` | roteamento local entre views |
| `frontend/src/api/product.ts` | client de API de produto |
| `frontend/src/api/types.ts` | tipos TypeScript dos contratos |
| `frontend/src/components/SetupReadinessView.tsx` | readiness/setup |
| `frontend/src/components/CapabilitiesView.tsx` | capacidades do produto |
| `frontend/src/components/DiscoveryView.tsx` | fontes/candidatos |
| `frontend/src/components/RadarDashboardView.tsx` | dashboard executivo agregado |
| `frontend/src/components/StartupListView.tsx` | lista de startups |
| `frontend/src/components/StartupDetailPanel.tsx` | detalhe e execução da pipeline |
| `frontend/src/components/WorkflowView.tsx` | workflows e status |
| `frontend/src/components/PipelineFinalResultView.tsx` | Decision Cockpit final |
| `frontend/src/components/WorkflowNodeTimeline.tsx` | timeline dos nós |
| `frontend/src/components/HumanReviewView.tsx` | revisão humana |
| `frontend/src/components/DossierView.tsx` | dossier |
| `frontend/src/components/ExportDeliveryView.tsx` | export |
| `frontend/src/components/QualityView.tsx` | quality report |
| `frontend/src/styles.css` | estilos |

## Views principais

| View | Papel |
|---|---|
| Setup | mostra se produto está pronto ou bloqueado |
| Capabilities | mostra capacidades do sistema |
| Discovery | popula/inspeciona fontes e candidatos |
| Radar Dashboard | prioriza empresas e recomendações |
| Startups | lista e permite abrir startup |
| Startup Detail | mostra startup e inicia pipeline principal |
| Workflow | lista workflows e permite abrir resultado final |
| Final Result | tela principal de entrega: Decision Cockpit |
| Export | artefatos exportados |
| Review | human-in-the-loop |

## Entrada principal de uso

Fluxo esperado do usuário avaliador:

```text
Setup → Radar Dashboard → Startup Detail → Run Main Pipeline → Final Result
```

Ao criar uma pipeline, `handlePipelineCreated` leva automaticamente para `finalResult`.

## Ordem correta da tela Final Result

A ordem da UI é parte da lógica do produto. A tela final deve mostrar:

```text
0. Blockers/warnings
1. Decision summary
2. Startup intelligence profile
3. NVIDIA recommendation ranking — all recommendations
4. Evidence matrix — all claims
5. Technical gaps and NVIDIA context
6. Quality gates and runtime trace
7. Executive brief
8. Activation dossier
9. Final export
10. Runtime JSON como auditoria avançada
```

O runtime trace não deve vir antes da decisão. O usuário da NVIDIA precisa primeiro ver a recomendação e a evidência.

## Decision summary

Cards obrigatórios:

- recommended NVIDIA action;
- opportunity score;
- top NVIDIA technology;
- evidence coverage;
- workflow status;
- pipeline progress.

Esses cards respondem rapidamente:

- devo abordar a startup?
- qual tecnologia é a principal?
- a evidência é suficiente?
- o workflow terminou?

## Startup intelligence profile

Deve mostrar como primeira classe:

- startup;
- website;
- sector;
- product;
- AI-native classification;
- AI-native score;
- NVIDIA/Inception fit;
- sources collected;
- distinct sources;
- official sources;
- perfil completo em JSON de auditoria.

Campos desejados quando backend fornece:

- founders;
- customers;
- funding;
- stack;
- technical keywords;
- AI-native signals;
- wrapper risk;
- proprietary data/workflow signals.

## NVIDIA recommendation ranking

A tela deve mostrar **todas as recomendações**, não apenas top 5.

Para cada recomendação:

- rank;
- tecnologia NVIDIA;
- expected utility ou priority score;
- action;
- gap;
- mapping score;
- mapping confidence;
- confidence final;
- uncertainty;
- evidence support;
- RAG support;
- production allowed;
- next-best-action;
- reason;
- why-not/blockers;
- objeto completo para auditoria.

## Evidence matrix

A matriz de evidências é obrigatória e não pode ser substituída por JSON bruto.

Colunas:

- group;
- claim;
- claim type;
- support level;
- confidence;
- used in score;
- used in gap;
- used in mapping;
- used in brief;
- evidence refs count;
- review status.

Ela deve mostrar todos os claims:

```typescript
Object.entries(bundle.claims).flatMap(...)
```

Não deve usar `slice()` para ocultar claims. Se houver muitos dados, usar scroll, paginação ou busca.

## Missing evidence e contradictions

Devem aparecer quando existirem:

- `missing_evidence`;
- `contradictions`;
- degraded checks;
- unsupported claims.

Esses itens devem ser visíveis porque guiam a decisão `validate_manually` ou `request_more_evidence`.

## Technical gaps and NVIDIA context

A tela mostra:

### Gap diagnosis

- gap;
- severity;
- confidence;
- status;
- evidence count.

### NVIDIA RAG contexts — all contexts

- technology/product;
- source;
- score;
- gap;
- snippet.

Requisito:

- mostrar todos os contextos persistidos;
- não esconder contextos em JSON;
- JSON fica como auditoria avançada.

## Quality gates and runtime trace

Campos:

- overall quality;
- passed metrics;
- export readiness;
- review readiness;
- RAG retrieval mode;
- GraphRAG status;
- Triton rerank status;
- progress bar;
- workflow node timeline;
- workflow state JSON.

Essa seção serve a avaliadores técnicos e debugging, mas vem depois da decisão/recomendação/evidência.

## Executive brief, dossier e export

A tela final deve permitir:

- gerar artefatos finais;
- copiar markdown;
- ler briefing executivo;
- ler activation dossier;
- ler export final;
- ver hash do export.

Botões:

- Refresh;
- Generate Final Deliverables;
- Copy Final Output.

## Radar Dashboard

O Radar Dashboard é a visão agregada para priorização.

Deve mostrar:

- total de empresas;
- empresas analisadas;
- recomendações prontas;
- runtime blockers;
- empresa;
- status;
- score;
- evidência;
- NVIDIA fit;
- recomendações;
- informação coletada.

O dashboard guia a escolha de qual startup abrir no Decision Cockpit.

## API consumida pelo frontend

Principais chamadas:

| Função | Endpoint |
|---|---|
| `getProductReadiness` | `/product/readiness` |
| `runMainProductPipelineForStartup` | `/workflows/product-runs` |
| `getWorkflowRun` | `/workflows/{id}` |
| `getAnalysisRun` | `/analysis-runs/{id}` |
| `getAnalysisEvidenceBundle` | `/analysis-runs/{id}/evidence-bundle` |
| `getQualitySummary` | quality summary endpoint |
| `getDossier` | dossier endpoint |
| `getDossierMarkdown` | dossier markdown endpoint |
| `getAnalysisRunBrief` | brief endpoint |
| `getExport` | `/exports/{id}` |
| `getRadarDashboard` | `/radar/dashboard` |
| `populateRadarDashboard` | `/radar/dashboard/populate` |

## Tratamento de blockers

A UI agrega blockers de:

- `workflow.error_message`;
- `workflow.degraded_reason`;
- `quality.degraded_reason`;
- warnings de carregamento;
- degraded checks do evidence bundle;
- blockers do recommendation output.

Esses blockers aparecem no topo, antes do usuário interpretar recomendações.

## Regra “mostrar tudo”

Não ocultar dados críticos por `slice()`.

Permitido:

- scroll;
- paginação;
- filtros;
- collapse/expand;
- export;
- busca.

Não permitido:

- top 5 fixo sem “view all”;
- claims só em JSON;
- RAG contexts só em JSON;
- missing evidence escondido;
- blockers escondidos;
- runtime failures tratados como `null` silencioso.

## JSON bruto

`RuntimeJson` é permitido apenas como auditoria avançada. A informação principal deve estar renderizada em cards/tabelas.

Uso correto:

- complete startup profile state;
- complete recommendation object;
- recommendation runtime output;
- all missing evidence;
- all contradictions;
- RAG runtime metrics;
- advanced techniques output;
- workflow state.

## Estado atual e limitações de arquitetura frontend

O frontend usa `useState` para navegação local. Isso funciona para entrega, mas URLs por entidade seriam melhores:

```text
/radar
/startups/:id
/workflows/:id
/workflows/:id/final
/analysis-runs/:id/evidence
/analysis-runs/:id/dossier
/review/:workflowId
```

Também seria desejável adicionar no futuro:

- TanStack Query para server-state/cache;
- React Router;
- Zod/Valibot para validação de API;
- data grid com virtualização;
- testes de acessibilidade;
- visual regression.

## Testes frontend

```bash
npm --prefix frontend ci
npm --prefix frontend run typecheck
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend run test:e2e:product
```

Testes E2E desejados para o case:

- setup mostra readiness;
- pipeline principal é criada;
- Final Result abre automaticamente;
- decision summary aparece;
- todas recomendações aparecem;
- evidence matrix aparece;
- RAG contexts aparecem;
- quality gates aparecem;
- export pode ser gerado;
- blockers aparecem quando existem;
- review flow funciona.

## Critérios de aceite

| Critério | Aceite |
|---|---|
| Decisão no topo | action, score e tecnologia principal visíveis |
| Tudo visível | recomendações, claims, gaps e RAG contexts sem truncamento rígido |
| Evidência | Evidence matrix em tabela |
| Recomendação | action, confidence, uncertainty, evidence/RAG support visíveis |
| Blockers | warnings no topo |
| Runtime | node timeline e progress visíveis |
| Export | brief, dossier e export acessíveis |
| Auditoria | JSON bruto disponível, mas secundário |
| Case fit | UI guia abordagem da NVIDIA, não só debugging |
