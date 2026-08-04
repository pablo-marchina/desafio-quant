# Módulo Startups — Visão Geral

## 1. Importância

O `startups` consolida a entidade central do produto: a startup, suas evidências
e seu perfil de IA. É aqui que o conteúdo coletado vira um registro estruturado
(setor, fundadores, funding, clientes), recebe uma classificação de maturidade de
IA (AI-native / AI-enabled / Non-AI) e um `StartupAIProfile` detalhado que
alimenta o motor de recomendações. Faz dedup por nome/domínio para não duplicar
empresas.

## 2. Fluxo

```txt
create/reuse startup (dedup por domínio normalizado, fallback por nome via rapidfuzz)
  -> attach evidence (FK para scraping_results)
  -> extract profile (Extraction Agent, best-effort)
  -> classify maturity (Startup Classifier Agent, best-effort)
  -> expõe portfolio paginado, stats de maturidade e evidências
```

## 3. Estrutura de pastas

```txt
startups/
  presentation/     POST/GET/PATCH startups, /extract, /classify, /evidences, /stats
  application/      use_cases, ports; public/ (StartupProfileReader, StartupCreator,
                    EvidenceAttacher, ExtractionTrigger, ClassificationTrigger, ListStartups)
  domain/           Startup, StartupEvidence, StartupAIProfile, enums, policies (dedup)
  infrastructure/   database/, agent_adapters/ (chama agents)
  factories/        importa AgentsFactory
  tests/
```

## 4. Stack

```txt
rapidfuzz       dedup por nome (WRatio, limiar 92 calibrado com 17 pares reais)
JSONB           ai_profile, founders, customers
SQLAlchemy      persistência relacional
```

## 5. Comunicação

```txt
startups -> agents (ExtractionService, StartupClassifierService)
recommendations/briefing -> startups (StartupProfileReader)
orchestration -> startups (StartupCreator, EvidenceAttacher, ExtractionTrigger, ClassificationTrigger)
```

## 6. Histórico de versões

| Versão | Status | Entrega |
|---|---|---|
| V1 | Entregue | Modelo relacional (Startup, StartupEvidence) |
| V2 | Entregue | Campos estruturados (founders/funding/customers) |
| V3 | Entregue | Classificação de maturidade de IA |
| V4 | Entregue | Dedup por nome/domínio com rapidfuzz |
| V5 | Entregue | StartupAIProfile estruturado (7 dimensões + confiança/evidência por campo) |

**Versão atual: V4.1 / V5** (perfil de IA). Detalhes em `versoes/`; evolução em
`roadmap.md`.
