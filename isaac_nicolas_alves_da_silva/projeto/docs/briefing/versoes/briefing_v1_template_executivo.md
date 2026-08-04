# Briefing V1 — Template Executivo

Esta versao cria o modulo `briefing`: monta um documento executivo em
Markdown a partir do perfil da startup (`startups`), suas evidencias
aprovadas e as recomendacoes NVIDIA mais recentes (`recommendations`). E a
ultima camada de conteudo antes de Orchestration V1 (pipeline end-to-end).

## 1. Objetivo

```txt
startup + evidencias + recomendacoes -> briefing executivo em Markdown
```

Sem LLM, sem agente — riscos e proximas acoes sao inferidos por regra de
codigo, mesmo principio aplicado em Recommendations V1. Briefing V2
("gerado por agente") e o lugar certo para linguagem natural livre — nao
esta versao.

## 2. Por que nao tem worker/fila

Mesma categoria de `nvidia_knowledge` e `recommendations`: so le dados ja
persistidos (Postgres) e monta uma string. Sem chamada de rede lenta que
justifique fila assincrona. `POST /briefings` calcula e persiste de forma
sincrona.

## 3. Descoberta que mudou o escopo: recommendations nao tinha `application/public/`

Mesma situacao que `startups` tinha antes da entrega de Recommendations V1.
Para `briefing` ler as recomendacoes sem importar `application/use_cases/`
internos de `recommendations`:

```python
# recommendations/application/public/recommendations_reader.py
class RecommendationsReader(ABC):
    async def list_by_startup_id(self, startup_id: UUID) -> list[RecommendationView]: ...
```

`ListRecommendations` (use case que ja existia para `GET
/recommendations?startup_id=`) passou a herdar de `RecommendationsReader` e
implementar `list_by_startup_id` direto — mesmo padrao de
`ListNvidiaTechnologies(NvidiaTechnologyCatalog)`. O `execute(*,
startup_id)` que a rota HTTP chama virou um alias fino que delega para
`list_by_startup_id`, sem quebrar a rota existente.
`RecommendationsFactory.create_recommendations_reader()` expoe a
implementacao. `recommendations` continua "V1" — extensao de superficie
publica, nao nova versao (mesmo espirito da extensao de `startups` na
entrega anterior).

`startups` nao precisou de nenhuma mudanca nesta versao — `briefing` reusa
o `StartupProfileReader` que ja existia.

## 4. Wiring entre modulos

Quinta instancia confirmada do mesmo padrao (scraping→agents,
embeddings→ingestion, recommendations→startups,
recommendations→nvidia_knowledge, agora briefing→startups e
briefing→recommendations):

```python
# briefing/factories/briefing_factory.py
from apps.api.src.modules.startups.factories.startups_factory import StartupsFactory
from apps.api.src.modules.recommendations.factories.recommendations_factory import (
    RecommendationsFactory,
)

profile_source = StartupsModuleProfileSource(StartupsFactory.create_startup_profile_reader())
recommendations_source = RecommendationsModuleSource(
    RecommendationsFactory.create_recommendations_reader()
)
```

`briefing` define seu proprio vocabulario (`application/dto.py`:
`StartupSnapshot`, `EvidenceSnapshot`, `RecommendationSnapshot`); os dois
adapters (`infrastructure/startups_adapters/`,
`infrastructure/recommendations_adapters/`) sao as unicas pecas que
conhecem o vocabulario de outro modulo.

## 5. Regras deterministicas (`domain/policies.py`)

```txt
assess_risks(evidencias, recomendacoes):
    sem evidencia          -> risco "perfil pouco fundamentado"
    evidencia com confidence_score < 0.5  -> risco "confiabilidade baixa"
    sem recomendacao       -> risco "sem aderencia clara"
    melhor recomendacao com score < 0.5   -> risco "aderencia moderada"

suggest_next_actions(recomendacoes):
    sem recomendacao  -> "coletar evidencias adicionais"
    com recomendacao  -> "agendar conversa tecnica sobre {melhor tecnologia}"

build_briefing_markdown(...):
    monta as secoes Resumo, Evidencias Principais, Recomendacoes NVIDIA,
    Riscos, Proximas Acoes
```

Tres funcoes puras, sem import de framework, testadas isoladamente.

## 6. Persistencia: regenerar substitui o briefing anterior

Mesma decisao de `GenerateRecommendations`: `GenerateBriefing` faz
`delete_by_startup_id` seguido de `save` dentro da mesma Unit of Work, antes
do commit. `POST /briefings` chamado de novo para a mesma startup nao
acumula linhas.

Tabela `briefings`: `id, startup_id (FK startups.id), content (Text),
generated_at`.

## 7. Fluxo de ponta a ponta

```txt
POST /startups + POST /startups/{id}/evidences   -> perfil + evidencias
POST /recommendations {"startup_id": "..."}        -> recomendacoes

POST /briefings {"startup_id": "..."}
  -> GenerateBriefing:
       le perfil (-> startups)
       le recomendacoes (-> recommendations)
       assess_risks + suggest_next_actions + build_briefing_markdown
       persiste (substitui briefing anterior da mesma startup)
  -> 201, BriefingResponse{content: "# Briefing Executivo — ..."}

GET /briefings/{briefing_id}        -> um briefing
GET /briefings?startup_id=...       -> lista (0 ou 1 item na V1)
```

### Exemplo de saida

```markdown
# Briefing Executivo — Acme AI

## Resumo
LLM customer service | BR
Plataforma de atendimento ao cliente usando LLM.
Site: https://acme.example.com

## Evidencias Principais
- [Acme launches LLM chatbot](https://example.com/news) — news

## Recomendacoes NVIDIA
- **NVIDIA NIM** (model_serving, score 1.0) — Evidencias e perfil mencionam:
  llm, generative ai, inference, api, deployment, microservice. NVIDIA NIM
  e indicada para: servir LLMs e modelos generativos em producao.

## Riscos
- Nenhum risco identificado.

## Proximas Acoes
- Agendar conversa tecnica sobre NVIDIA NIM (model_serving).
```

## 8. Validacao

Testes novos:

```txt
test_briefing_policies.py              8 testes (riscos, proximas acoes,
                                        markdown builder)
test_briefing_entities.py              2 testes (invariantes)
test_generate_briefing.py              3 testes (geracao, substituicao,
                                        erro de perfil)
recommendations/test_recommendations_reader.py   2 testes (contrato publico
                                        novo)
tests/integration/test_postgres_briefing_repository.py   1 teste
```

Total apos esta entrega:

```txt
330 passed, 11 failed (falhas - todas de integracao, exigem Postgres/Redis/
Qdrant locais; a nova falha de briefing e a mesma categoria das 10 que ja
existiam, nenhuma regressao)
```

## 9. Limites conhecidos da V1

```txt
saida e um unico campo Markdown - sem estrutura JSON por secao (riscos,
proximas acoes) para consumo programatico; fica para quando alguma versao
futura precisar disso

regenerar substitui o briefing anterior - sem historico, sem diff

sem exportacao PDF/HTML (Briefing V3) e sem revisao humana (Briefing V4)

sem autenticacao na rota nova (nenhum modulo tem ainda)
```

## 10. Proximo passo

```txt
Orchestration V1 — analysis_jobs, endpoint unico para rodar o pipeline
completo (scraping -> ingestion -> embeddings -> startups -> rag ->
recommendations -> briefing)
```
