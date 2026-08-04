# Recommendations V2 — Recomendacao com RAG (Grounding)

Implementado em 24/06/2026. Decisao tomada em 23/06/2026
(`docs/decisoes_pendentes.md`, secao 2 — "vale fazer, junto com a mesma
decisao para `briefing`"), registrada como pendente em
`docs/roadmap_produto_final.md` ("Ordem de implementacao recomendada",
item 3) e so agora fechada.

## 1. Objetivo

```txt
justificativa de recomendacao = template fixo -> justificativa fundamentada
em conteudo NVIDIA real, com citacoes, via RAG
```

Antes desta entrega, `_build_justification()` so concatenava
`matched_keywords` e o primeiro `use_case` do catalogo estatico — nunca
citava nenhum documento real. O objetivo nao era substituir
`match_technologies()` (continua sendo o motor de decisao de **quais**
tecnologias entram na recomendacao), so enriquecer o texto de **por que**
com evidencia real recuperavel.

## 2. Por que nao mudou `match_technologies()`

Regra 6 do checklist do CLAUDE.md: LLM/RAG so entra quando a regra
deterministica nao for suficiente. `match_technologies()` (keyword
matching com word boundary) continua decidindo quais tecnologias batem
com o perfil da startup — isso e' uma decisao estrutural, nao uma
ambiguidade textual. RAG entra depois, so para fundamentar a
justificativa de quem ja passou no match.

## 3. Arquitetura

Porta nova em `application/ports.py`:

```python
class NvidiaKnowledgeGrounder(ABC):
    async def ground(
        self, technology_name: str, use_case: str
    ) -> GroundedJustification | None: ...
```

Best-effort por desenho: nunca levanta excecao. Devolve `None` quando o
RAG falha (`RagError`, sem `GEMINI_API_KEY`) ou quando a resposta nao tem
citacao real (`view.citations` vazio — RAG V2 ja trata "evidencia
insuficiente" como resposta valida, nao erro). Quem chama cai pro
template deterministico de V1 nesse caso.

Implementacao (`infrastructure/rag_adapters/nvidia_knowledge_grounder_adapter.py`):

```python
class RagNvidiaKnowledgeGrounder(NvidiaKnowledgeGrounder):
    def __init__(self, question_answerer: RagQuestionAnswerer) -> None: ...

    async def ground(self, technology_name, use_case) -> GroundedJustification | None:
        view = await self._question_answerer.answer(AnswerQuestionInput(
            query=f"How can NVIDIA {technology_name} help with {use_case}?",
            source_type="nvidia_knowledge",
            limit=5,
        ))
        ...
```

So importa `rag/application/public/question_answerer.py` +
`application/dto.py` — nada de `rag/domain` ou `rag/infrastructure`. Mesmo
contrato que o NVIDIA RAG Agent (Agents V10) ja usa, reaproveitado direto
em vez de duplicar a logica de busca+resposta+citacao.

Wiring (`factories/recommendations_factory.py`):

```python
@staticmethod
def create_nvidia_knowledge_grounder() -> NvidiaKnowledgeGrounder | None:
    if not get_settings().gemini_api_key:
        return None
    return RagNvidiaKnowledgeGrounder(RagFactory.create_question_answerer())
```

Mesma regra de degradacao dos outros 4 agentes/adapters que dependem de
`GEMINI_API_KEY`: sem a chave, `grounder=None` e `GenerateRecommendations`
usa so o template V1, sem erro.

## 4. Fluxo de execucao

```txt
match_technologies(...) decide os candidatos (inalterado)
para cada candidato (em paralelo, asyncio.gather):
    grounder.ground(technology.name, use_case) -> GroundedJustification | None
justificativa final = fundamentada (se grounded) OU template V1 (se None)
```

1 chamada RAG por tecnologia candidata (nao por startup) — diferente do
Briefing V1 (extensao, ver `docs/briefing/roadmap_briefing.md`), que faz 1
chamada agregada para todas as tecnologias de uma vez. A diferenca e' de
forma: recomendacao precisa de uma justificativa por tecnologia, briefing
precisa de uma sintese de setor unica.

Justificativa fundamentada:

```txt
"{texto da resposta do RAG} Fontes: {url1}, {url2}."
```

## 5. Limites conhecidos desta entrega

```txt
ground() recebe so technology_name + use_case (o primeiro use_case do
catalogo) - nao usa o texto especifico de evidencia/setor da startup
como query; duas startups diferentes recomendadas para a mesma
tecnologia recebem a mesma fundamentacao RAG

nao complementa match_technologies() com busca semantica (VectorRepository)
para tecnologias fora do catalogo por keyword - continua sendo trabalho
futuro de V2/V4 (ver "Tecnologias candidatas" em
docs/recommendations/roadmap_recommendations.md)

sem cache - mesma tecnologia+use_case recomendada em chamadas diferentes
repete a chamada RAG (custo de API), diferente dos caches por
content_hash que scraping/embeddings ja tem
```

## 6. Validacao

```txt
test_nvidia_knowledge_grounder_adapter.py   3 testes (citacao real,
                                             erro do RAG, sem citacao)
test_generate_recommendations.py            +2 testes (justificativa
                                             fundamentada quando grounder
                                             disponivel, fallback quando
                                             None)
```

`recommendations`: 26 -> 31 testes unitarios (+5: 3 adapter + 2 caso de
uso).

## 7. Proximo passo

```txt
Calibrar limiar de similaridade do rapidfuzz para dedup de startups
(Startups V4, ver docs/startups/roadmap_startups.md) - proximo item da
"Ordem de implementacao recomendada" em docs/roadmap_produto_final.md
```
