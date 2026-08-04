# Arquitetura do Projeto

## Visão Geral

O NVIDIA Startup AI Radar é uma aplicação web para descobrir, ranquear e analisar startups brasileiras com sinais de IA-native. O objetivo é apoiar priorização de outreach, qualificação técnica e geração de briefings executivos para oportunidades relacionadas à NVIDIA.

## Fluxo Principal

1. O usuário informa uma busca de mercado, por exemplo `IA generativa para saúde`.
2. A API consulta fontes recentes via Google News RSS.
3. O motor de descoberta envia as notícias recentes para o LLM, quando configurado, para extrair empresas reais e descartar termos genéricos ou veículos de mídia.
4. As candidatas são rankeadas por sinais de IA-native, fit NVIDIA, recência, risco de wrapper, urgência e quantidade de evidências. Sem LLM, o sistema usa fallback local.
5. O usuário escolhe uma candidata ou informa uma startup manualmente.
6. O sistema gera perfil, maturidade de IA, gaps técnicos, recomendações NVIDIA, radar de ameaça/oportunidade e briefing.
7. O briefing pode ser copiado, baixado, impresso ou enviado por e-mail quando SMTP estiver configurado.

## Componentes

```text
Frontend estático
  -> FastAPI
      -> Descoberta e crawling de mercado
      -> Extração de perfil de startup
      -> Classificação de maturidade de IA
      -> Diagnóstico de gaps
      -> Recomendações NVIDIA
      -> Radar de ameaça/oportunidade
      -> Geração e envio de briefing
  -> PostgreSQL
  -> Qdrant
```

## Backend

O backend usa FastAPI e expõe endpoints para descoberta, análise, recomendações, radar e relatórios.

Principais módulos:

- `app/discovery`: crawling via Google News RSS, extração e ranking de candidatas via LLM, com fallback local.
- `app/llm`: camada de integração OpenAI para respostas JSON estruturadas.
- `app/extraction`: extração de perfil e evidências via LLM, com fallback heurístico.
- `app/classification`: classificação AI-native, AI-enabled ou non-AI via LLM, com fallback heurístico.
- `app/diagnostics`: diagnóstico de gaps de stack de IA via LLM, com fallback local.
- `app/recommendations`: recomendação de tecnologias NVIDIA via LLM limitada ao catálogo interno, com fallback local.
- `app/radar`: score de risco de wrapper, defensibilidade, fit NVIDIA e urgência via LLM, com fallback local.
- `app/briefings`: geração de Markdown e envio por SMTP.

## Frontend

O frontend fica em `web/` e é servido como site estático. Ele oferece:

- Busca de mercado.
- Lista de empresas candidatas rankeadas.
- Carregamento de uma candidata no fluxo de análise.
- Análise de startup específica.
- Prévia do briefing.
- Download, impressão e envio por e-mail.
- Tema claro/escuro com base na preferência do dispositivo.

## Dados e Infraestrutura

- PostgreSQL: persistência estruturada de startups, fontes, evidências e briefings.
- Qdrant: preparado para busca vetorial de conhecimento NVIDIA.
- Docker Compose: sobe PostgreSQL e Qdrant localmente.

## Integrações Externas

- Google News RSS: usado para crawling de notícias recentes.
- SMTP: usado para envio de relatórios por e-mail, quando configurado.
- OpenAI: usado para descoberta/rankeamento, extração, classificação, diagnóstico, recomendações e radar quando `OPENAI_API_KEY` está configurada.
- Cohere: variável reservada para evolução futura de reranking.

## Limitações Técnicas

- Sem `OPENAI_API_KEY`, descoberta, extração, classificação, diagnóstico, recomendações e radar usam fallback local.
- A extração de nomes a partir de títulos de notícias pode exigir validação humana.
- Links do Google News podem apontar para URLs intermediárias.
- Envio de e-mail depende de servidor SMTP válido.
- Persistência depende de Docker/PostgreSQL rodando.
