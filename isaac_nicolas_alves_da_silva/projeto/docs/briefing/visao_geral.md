# Módulo Briefing — Visão Geral

## 1. Importância

O `briefing` formata o resultado final para humanos: um briefing executivo em
Markdown que reúne perfil, evidências, recomendações, riscos e próximas ações,
com contexto NVIDIA fundamentado por RAG. É a "saída apresentável" do produto —
o que um gerente de Startups ou VC realmente lê. Também exporta o briefing em PDF
preservando as citações.

## 2. Fluxo

```txt
POST /briefings
  -> lê StartupProfile + recommendations
  -> monta StartupAIProfileItem
  -> busca contexto NVIDIA via RAG (best-effort, 1 chamada agregada)
  -> build_briefing_markdown() (função pura, sem I/O)
  -> salva Briefing (substitui o anterior da mesma startup)
  -> opcionalmente o Briefing Agent reescreve a prosa preservando citações
GET /briefings/{id}/export   -> PDF via Playwright + Jinja2
```

Estrutura do briefing: Resumo Executivo, Tese de Fit NVIDIA, Nível de Confiança,
O Que Foi/Não Foi Encontrado, Evidências, Matriz de Recomendações, Recomendações
Fortes, Hipóteses Exploratórias, Contexto NVIDIA, Riscos, Perguntas de
Qualificação, Próximas Ações.

## 3. Estrutura de pastas

```txt
briefing/
  presentation/     POST, GET, GET /{id}/export, PATCH /{id}/review
  application/      use_cases, ports; public/ (BriefingGenerator, BriefingContentUpdater)
  domain/           Briefing, policies (assess_risks, suggest_next_actions, build_briefing_markdown), exceções
  infrastructure/   startups_adapters/, recommendations_adapters/, rag_adapters/, rendering/ (PDF)
  factories/        importa StartupsFactory, RecommendationsFactory, RagFactory
  tests/
```

## 4. Stack

```txt
string/Markdown puro            saída determinística
Playwright + Jinja2 + markdown  export PDF (trocou weasyprint p/ evitar deps nativas)
(reuso) rag.public              contexto NVIDIA com citações
```

## 5. Histórico de versões

| Versão | Status | Entrega |
|---|---|---|
| V1 | Entregue | Template executivo em Markdown (5 seções) + RAG grounding (extensão) |
| V2 | (agente) | Briefing gerado por agente — entregue como Agents V12 |
| V3 | Entregue | Exportação em PDF preservando citações (Playwright/Jinja2) |
| V4 | Entregue | Briefing analítico: tese de fit, matriz, fortes vs exploratórias, perguntas + review humano |

**Versão atual: V4.** Detalhes em `versoes/`; futuro (V5 ranking de
oportunidades) em `roadmap.md`.
