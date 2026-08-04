# Briefing V4 — Briefing analítico

## Objetivo

Transformar o template executivo em um briefing analítico e acionável, com tese
de fit, matriz e perguntas de qualificação.

## O que entregou (27/06/2026)

Nova estrutura do briefing:

```txt
Resumo Executivo
Tese de Fit NVIDIA
Nível de Confiança Geral
O Que Foi Encontrado
O Que Não Foi Encontrado
Evidências Principais
Matriz de Recomendações
Recomendações Fortes
Hipóteses Exploratórias
Contexto NVIDIA
Riscos
Perguntas de Qualificação
Próximas Ações
```

Esta entrega foi feita em passos coordenados com outros módulos:

- passo 1 → Recommendations V4 (signal_origins / missing_signals);
- passo 2 → Startups V5 (StartupAIProfile);
- passos 3+4 → Recommendations V5 (score composto + prefiltro semântico).

Também entregue: revisão humana
(`review_status`/`review_comment`/`reviewed_by`/`reviewed_at`) e fallback contra
perda de citações na reescrita por LLM (extrai URLs do Markdown determinístico;
se a reescrita perder alguma, devolve o original).

Versão atual do módulo: **Briefing V4** (ver `../visao_geral.md`).
