# Roteiro de Demo dos Diferenciais

Use este roteiro para mostrar que o projeto nao e apenas "agente + RAG +
dashboard". A demo deve provar que o sistema muda a recomendacao conforme
timing, risco wrapper e qualidade da evidencia.

Atalho: a interface possui uma aba **Demo Mode** com estes tres cenarios. Use
`Run full demo` para executar tudo em sequencia, ou rode cada cenario
individualmente.

## Caso 1 - Startup forte para abordagem tecnica

Objetivo: mostrar oportunidade quente ou morna, recomendacao acionavel e
playbook claro.

Entrada sugerida:

```json
{
  "startup_name": "NeuralMed Brasil Demo",
  "sector": "healthcare",
  "description": "Startup brasileira usa IA generativa, LLM, dados clinicos e workflow medico para automatizar triagem e atendimento em producao no Brasil.",
  "technical_gaps": [
    "latencia de inferencia",
    "governanca de IA",
    "dependencia de API externa"
  ]
}
```

O que mostrar:

- Playbook de abordagem NVIDIA.
- Evidence Quality Gate aceitando ou rebaixando com motivo.
- Recomendacao de NIM, Guardrails, Triton ou tecnologia relacionada.
- Pergunta de descoberta sobre custo, latencia p95 ou fallback.

Mensagem para defender:

> Aqui o sistema nao so recomenda produto. Ele sugere como a NVIDIA abordaria a
> startup, qual gap validar primeiro e qual pergunta tecnica abriria a conversa.

## Caso 2 - Startup com risco wrapper

Objetivo: mostrar o Wrapper Displacement Map.

Entrada sugerida:

```json
{
  "startup_name": "ChatOps Wrapper Demo",
  "sector": "customer service",
  "description": "Startup brasileira oferece chatbot simples com interface sobre API externa de LLM para atendimento. Ainda nao ha sinais claros de dados proprietarios ou workflow profundo.",
  "technical_gaps": [
    "dependencia de API externa",
    "custo de inferencia",
    "governanca de respostas"
  ]
}
```

O que mostrar:

- Wrapper Risk Score alto.
- Mapa de risco explicando dependencia de API, interface facil de copiar e falta
  de dados proprietarios.
- Caminho NVIDIA: medir custo/latencia, testar NIM ou Guardrails e ganhar
  controle de producao.

Mensagem para defender:

> Esse caso conversa diretamente com a pergunta norteadora. O sistema identifica
> startups que podem ser engolidas por features dos grandes labs e sugere como
> evoluir para uma operacao de IA mais defensavel.

## Caso 3 - Evidencia fraca

Objetivo: mostrar que o sistema nao inventa certeza.

Entrada sugerida:

```json
{
  "startup_name": "Empresa Pouco Clara Demo",
  "sector": "unknown",
  "description": "Empresa brasileira com plataforma digital para negocios.",
  "technical_gaps": []
}
```

O que mostrar:

- Classificacao `insufficient_evidence` ou scores baixos.
- Evidence Quality Gate rebaixando ou bloqueando recomendacoes.
- Counterfactual dizendo o que nao recomendar ainda.
- Proxima acao focada em coletar mais contexto.

Mensagem para defender:

> Um bom sistema de inteligencia tambem precisa saber dizer "ainda nao da para
> recomendar". Esse gate evita uma demo bonita, mas tecnicamente fraca.

## Ordem ideal na apresentacao

1. Abrir a aba Demo Mode.
2. Clicar em `Run full demo`.
3. Mostrar o resumo comparativo dos tres cenarios.
4. Abrir a ultima analise renderizada em Manual Analysis e apontar Playbook,
   Evidence Gate, Wrapper Map e Counterfactual.
5. Abrir o Radar e mostrar `approach_timing` nos cards.
6. Encerrar com o briefing Markdown/PDF mostrando as mesmas decisoes com fontes.
