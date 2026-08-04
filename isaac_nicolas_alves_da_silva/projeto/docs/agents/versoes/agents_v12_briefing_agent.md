# Agents V12 - Briefing Agent

Esta entrega fecha o ultimo dos 8 agentes LangGraph previstos no brief
original do case. Com ela, **todos os 8 agentes do Entregavel 2 estao
implementados como agentes de fato** (ver
`docs/diagnostico_case_original_e_novas_prioridades.md`, secao 3).

## Objetivo

```txt
startup_id -> briefing deterministico (briefing) -> reescrita de prosa
executiva (LLM, com fallback seguro) -> briefing final
```

## Decisao de design (ja estava no diagnostico, so implementada agora)

```txt
Briefing Agent = grafo LangGraph que chama BriefingGenerator
                  (briefing/application/public/) como tool, e usa LLM so
                  para reescrever a prosa executiva (linguagem de
                  negocio), preservando as citacoes/rastreabilidade que o
                  template determinístico ja garante
```

`build_briefing_markdown()` (`briefing/domain/policies.py`) continua
sendo a unica fonte de verdade para secoes, riscos e proximas acoes — o
LLM nunca decide nada disso, so reescreve a prosa.

## Diferenca para o Recommendation Agent (V11)

O Recommendation Agent so aciona LLM condicionalmente (score ambiguo OU
enriquecimento). O Briefing Agent aciona o LLM **sempre** — reescrever a
prosa e' o proposito inteiro do agente, nao uma excecao. Em troca, nao ha
decisao de manter/descartar nada (toda a logica de risco/proxima acao
continua 100% determinística); a unica preocupacao e' nao perder
citacoes na reescrita, e essa preocupacao foi resolvida com um
**fallback seguro em codigo**, nao um "keep" por item.

## Entregue

- `AgentType.BRIEFING` (`domain/enums.py`)
- `AgentBriefingError` (`domain/exceptions.py`)
- `BriefingAgentInput`/`BriefingAgentResult` (`application/dto.py`) —
  vocabulario simplificado e proprio de `agents`
- `BriefingToolPort` (`application/ports.py`) — porta interna para
  chamar `briefing` como tool (devolve so o Markdown, decoupled do
  `BriefingView` exato)
- `BriefingProseRewriterPort` (`application/ports.py`) — porta interna
  para a reescrita via LLM
- `BriefingAgentService` (`application/public/briefing_agent.py`) —
  contrato publico (`generate()` + `resume()` default
  `NotImplementedError`)
- `BriefingAgentGraph` (`graphs/briefing/`) — 4 nodes:
  `prepare_context -> generate_briefing -> rewrite_prose -> finalize`.
  Diferente do Recommendation Agent, `rewrite_prose` nunca e' pulado
  (sempre ha conteudo: o template determinístico ja preenche placeholders
  como "Nenhuma evidencia aprovada registrada." quando vazio)
- `BriefingGeneratorAdapter` (`infrastructure/briefing_adapters/`) —
  implementa `BriefingToolPort` chamando
  `BriefingFactory.create_briefing_generator()` direto; traduz
  `BriefingError` para `AgentBriefingError`
- `LangChainGeminiBriefingProseRewriter` (`infrastructure/llm/`) —
  implementa `BriefingProseRewriterPort`; chama Gemini uma vez por
  briefing para reescrever a prosa
- `AgentType.BRIEFING` wired em `ExecuteAgentJob`/`ResumeAgentJob`;
  `AgentsFactory.create_briefing_agent_service()` segue a mesma regra dos
  outros agentes (sem `GEMINI_API_KEY`, devolve `None`)
- Import lazy de `BriefingFactory` dentro do metodo da factory (mesmo
  ciclo `agents -> briefing -> startups -> agents` do Recommendation
  Agent, ja esperado e corrigido preventivamente)
- Sem consumidor sincrono dedicado ainda; acionavel pela fila generica
  `agent_runs` com `agent_type=briefing`
- Testes: 10 unit (+2 adapter, +7 reviewer/rewriter, +1 grafo)

## Fallback seguro contra perda de citacoes

```txt
extrai todas as URLs https?://... do Markdown deterministico
chama o LLM para reescrever a prosa
extrai as URLs do resultado do LLM
se alguma URL original nao aparecer na reescrita -> devolve o
  Markdown deterministico original, sem nenhuma alteracao
```

Isso e' aplicado **dentro** de `LangChainGeminiBriefingProseRewriter.rewrite()`,
nao no grafo — mesmo padrao do "code-enforced override" do Recommendation
Agent (a decisao de seguranca vive na implementacao da porta, nao e'
confiada so ao prompt, regra 9 do CLAUDE.md). Testado explicitamente: uma
reescrita que omite uma URL e' descartada e o conteudo original e'
devolvido inalterado; uma reescrita que preserva todas as URLs e' aceita.

## Limites

- Sem interrupt/human-in-the-loop — nao ha decisao de alto custo aqui
- Sem consumidor sincrono dedicado ainda — nenhum outro modulo chama este
  agente em vez de `BriefingGenerator` direto
- A validacao de citacoes e' por presenca de substring de URL, nao por
  diff semantico completo do Markdown — suficiente para o caso de uso
  (garantir que nenhuma evidencia foi silenciosamente descartada), mas
  nao detecta, por exemplo, um numero alterado fora de uma URL
