# Documentacao do AI Venture Radar

Atualizado em 01/07/2026.

Este diretorio guarda a documentacao tecnica do AI Venture Radar. A regra de
leitura e simples: os arquivos `visao_geral.md` e `roadmap.md` de cada modulo
mostram o estado atual; a pasta `versoes/` preserva o historico de entregas.

## Leitura recomendada

1. [Fluxo total do produto](geral/fluxo_total.md)
2. [Arquitetura: monolito modular + workers](geral/arquitetura_monolito_modular_workers.md)
3. [Estado atual e roadmap futuro](geral/estado_atual_e_roadmap_futuro.md)
4. [Stack e onde cada tecnologia e usada](geral/stack_e_onde_e_usado.md)
5. [Rastreabilidade TAP -> implementacao](geral/rastreabilidade_tap.md)

## Modulos

| Modulo | Visao geral | Roadmap |
|---|---|---|
| Scraping | [visao](scraping/visao_geral.md) | [roadmap](scraping/roadmap.md) |
| Ingestion | [visao](ingestion/visao_geral.md) | [roadmap](ingestion/roadmap.md) |
| Embeddings | [visao](embeddings/visao_geral.md) | [roadmap](embeddings/roadmap.md) |
| Startups | [visao](startups/visao_geral.md) | [roadmap](startups/roadmap.md) |
| Agents | [visao](agents/visao_geral.md) | [roadmap](agents/roadmap.md) |
| RAG | [visao](rag/visao_geral.md) | [roadmap](rag/roadmap.md) |
| NVIDIA Knowledge | [visao](nvidia_knowledge/visao_geral.md) | [roadmap](nvidia_knowledge/roadmap.md) |
| Recommendations | [visao](recommendations/visao_geral.md) | [roadmap](recommendations/roadmap.md) |
| Briefing | [visao](briefing/visao_geral.md) | [roadmap](briefing/roadmap.md) |
| Orchestration | [visao](orchestration/visao_geral.md) | [roadmap](orchestration/roadmap.md) |
| Startup Discovery | [visao](startup_discovery/visao_geral.md) | [roadmap](startup_discovery/roadmap.md) |
| Frontend | [visao](frontend/visao_geral.md) | [roadmap](frontend/roadmap.md) |

## Discovery

O modulo de discovery roda apenas fontes com extrator implementado. O catalogo
com fontes planejadas fica em [startup_discovery/source_catalog.md](startup_discovery/source_catalog.md).

## Observabilidade

O projeto possui logging estruturado e tracing Langfuse opcional. A operacao de
producao completa ainda fica fora do escopo do case/demo: alertas, retencao,
runbooks, auth real, CI/CD e deploy endurecido nao sao objetivos atuais.

## Como manter

- Atualize `visao_geral.md` quando o comportamento atual mudar.
- Atualize `roadmap.md` quando uma decisao de futuro mudar.
- Crie um arquivo em `versoes/` para entregas relevantes e ja concluidas.
- Evite colocar segredo, token, chave ou dado sensivel em qualquer doc.
