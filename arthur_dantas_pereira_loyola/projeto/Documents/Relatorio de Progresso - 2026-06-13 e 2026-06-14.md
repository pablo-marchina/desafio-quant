---
title: "Relatorio de Progresso - NVIDIA Startup AI Radar"
periodo: "2026-06-13 a 2026-06-14"
projeto: "NVIDIA Startup AI Radar"
autor_git: "malafisor-arthurloyola <malafisor.es@gmail.com>"
---

# Relatorio de Progresso - NVIDIA Startup AI Radar

## Resumo executivo

Entre 2026-06-13 e 2026-06-14, o projeto saiu de uma base inicial de organizacao e setup para uma arquitetura funcional de MVP com LangGraph, testes automatizados, ambiente Python validado e um sistema de aprendizado documentado no Obsidian.

O foco nao foi usar APIs externas ainda. A prioridade foi construir uma base confiavel: ambiente reprodutivel, grafo multiagente deterministico, schemas internos, validacao de evidencias e registro didatico do que foi feito.

## 2026-06-13 - O que foi feito

### 1. Organizacao inicial do projeto

Foi estruturado o repositorio principal em:

```text
C:\Users\Inteli\Desktop\Ligas\InteliAcademy\ProjetoNvidia\InteliAcademy-ProjetoNvidia
```

Tambem foi consolidado o documento `AGENTS.md`, que define regras importantes para o projeto, incluindo:

- seguir o documento oficial do case como fonte principal de verdade;
- nao inventar dados sobre startups;
- preservar rastreabilidade de evidencias;
- separar responsabilidades entre scraping, extracao, validacao, RAG, recomendacao e briefing.

### 2. Setup Python e base de ambiente

Foram iniciadas as configuracoes de runtime Python e dependencias do projeto.

Commits relacionados:

```text
f3fee2f chore: bootstrap skills and python environment
9f4eb11 chore: set python 3.12 as project runtime
973582c fix: novas implementacoes relacionadas ao venv, mas ainda nao foram concluidas
```

O objetivo dessa etapa foi evitar que o projeto dependesse do Python global da maquina e preparar uma base mais previsivel para testes e execucao.

### 3. Instalacao e organizacao de skills

Foram adicionadas skills locais e de apoio para orientar o desenvolvimento:

- `multi-agent-orchestration`;
- `frontend-design`;
- `langgraph-nvidia-startup-radar`;
- outras skills auxiliares de criacao e instalacao.

Commits relacionados:

```text
a66906a chore: add multi-agent orchestration skill
9f760a0 chore: add frontend design skill
```

Essas skills ajudam a transformar o trabalho do Codex em procedimentos mais consistentes, em vez de respostas soltas.

### 4. Bootstrap da arquitetura do Radar

Foi criada a primeira arquitetura do sistema multiagente em:

```text
ai-agent-system/src/radar/
```

Principais partes criadas:

- `agents/`: agentes determiniscos iniciais;
- `graph/`: estado, nodes, edges e builder do LangGraph;
- `schemas/`: contratos Pydantic para fontes, claims, startups, recomendacoes e briefing;
- `scraping/`: coletor inicial;
- `api/`: FastAPI minima;
- `tests/`: testes iniciais do MVP.

Commit relacionado:

```text
061a81c chore: bootstrap radar architecture
```

## 2026-06-14 - O que foi feito

### 1. Finalizacao do ambiente Python

O ambiente virtual foi validado em:

```text
C:\Users\Inteli\Desktop\Ligas\InteliAcademy\ProjetoNvidia\InteliAcademy-ProjetoNvidia\venv
```

Python usado:

```text
Python 3.12.10
```

Comando correto para executar tarefas do projeto:

```powershell
& 'C:\Users\Inteli\Desktop\Ligas\InteliAcademy\ProjetoNvidia\InteliAcademy-ProjetoNvidia\venv\Scripts\python.exe'
```

Validacoes feitas:

```text
pip check -> No broken requirements found.
pytest -> passou
```

Restricao mantida: nao usar Python global.

### 2. Configuracao do autor Git correto

O autor local do Git foi ajustado para:

```text
malafisor-arthurloyola <malafisor.es@gmail.com>
```

Isso garante que os commits seguintes fiquem associados ao perfil correto.

### 3. Criacao do MOC de aprendizados no Obsidian

Foi criado um MOC especifico para aprendizado no cofre Obsidian:

```text
C:\Users\Inteli\Desktop\Projeto Nvidia\MOC - Aprendizados NVIDIA Startup AI Radar.md
```

A ideia desse MOC e registrar:

- o que foi feito;
- por que foi feito;
- quais arquivos importam;
- quais trechos de codigo sao importantes;
- como cada parte se conecta no projeto;
- o que estudar depois.

Tambem foram criadas notas como:

- `Aprendizado - Venv Python`;
- `Aprendizado - Setup do Projeto`;
- `Aprendizado - Schemas e Adapters para APIs`;
- `Aprendizado - LangGraph Atual do Projeto`;
- `Aprendizado - Sistema Multiagente com LangGraph`.

### 4. Criacao de adapter/normalizer para fontes

Foi criada a primeira camada de protecao entre dados externos e o LangGraph:

```text
ai-agent-system/src/radar/scraping/normalizers.py
```

Antes, o coletor criava diretamente um `SourceDocument`. Agora, ele simula payloads brutos e passa por um normalizador.

Fluxo desejado:

```text
API ou scraper bruto
 -> adapter/normalizer
 -> schema interno
 -> LangGraph
```

Isso reduz o risco de o projeto depender diretamente do formato de uma API externa.

Commit relacionado:

```text
a71b842 feat: normalize source payloads for radar pipeline
```

### 5. Fortalecimento da extracao e validacao de evidencias

O `Extractor Agent` foi melhorado para diferenciar tipos de claims:

```text
ai_usage
technology_signal
public_signal
```

Arquivo:

```text
ai-agent-system/src/radar/agents/extractor.py
```

O `Evidence Validator Agent` tambem foi fortalecido.

Regras atuais:

```python
MINIMUM_CLAIMS = 2
MINIMUM_AI_CLAIMS = 1
MINIMUM_CONFIDENCE = 0.5
```

Isso significa que o sistema exige:

- pelo menos duas evidencias publicas independentes;
- pelo menos uma claim validada de uso de IA;
- confianca minima antes de liberar recomendacoes.

Arquivo:

```text
ai-agent-system/src/radar/agents/validator.py
```

Commit relacionado:

```text
971d88a feat: strengthen evidence extraction gates
```

### 6. Criacao de testes novos

Foram adicionados testes para validar os novos contratos:

```text
ai-agent-system/tests/test_source_normalizers.py
ai-agent-system/tests/test_evidence_pipeline.py
```

Cobertura atual:

- payload sem URL rastreavel e rejeitado;
- payloads com formatos diferentes viram `SourceDocument`;
- evidencia fraca gera briefing limitado;
- recomendacao so aparece depois de evidencia minima validada;
- extractor cria claims de uso de IA;
- validator exige evidencias independentes.

Resultado atual:

```text
7 passed
```

### 7. Criacao da skill de aprendizado no Obsidian

Foi criada uma skill local para orientar futuras anotacoes de aprendizado:

```text
ai-agent-system/skills/obsidian-learning-notes/SKILL.md
```

Essa skill estabelece que as notas devem conter:

- explicacao leiga;
- analogias;
- trechos curtos de codigo;
- arquivos importantes;
- fluxos em formato de esteira;
- loops de retorno do LangGraph;
- atualizacao do handoff unico.

Commit relacionado:

```text
c4b5d9d chore: add obsidian learning notes skill
```

### 8. Atualizacao do handoff unico

Foi definido que o projeto deve manter apenas um handoff vivo:

```text
C:\Users\Inteli\Desktop\Projeto Nvidia\Sessao 2026-06-14 - Handoff para Proximo Agente.md
```

Esse arquivo deve ser atualizado ao final de etapas importantes e serve como prompt para outro agente continuar o projeto.

## Estado atual do LangGraph

Fluxo atual:

```text
query
 -> search_planner
 -> scraper
 -> extractor
 -> validator
 -> se evidencia fraca: scraper de novo ou briefing limitado
 -> se evidencia suficiente: classifier
 -> se Non-AI: briefing
 -> se AI-Enabled/AI-Native: nvidia_rag
 -> recommendation
 -> briefing
```

Em analogia: o LangGraph funciona como uma esteira de investigacao. Cada agente pega a pasta compartilhada (`RadarState`), adiciona sua parte e passa para o proximo. Quando a evidencia e fraca, a esteira pode voltar para coletar mais informacao ou encerrar com briefing limitado.

## Principais arquivos atuais

```text
ai-agent-system/src/radar/graph/state.py
ai-agent-system/src/radar/graph/builder.py
ai-agent-system/src/radar/graph/nodes.py
ai-agent-system/src/radar/graph/edges.py
ai-agent-system/src/radar/agents/extractor.py
ai-agent-system/src/radar/agents/validator.py
ai-agent-system/src/radar/agents/nvidia_rag.py
ai-agent-system/src/radar/agents/recommendation.py
ai-agent-system/src/radar/scraping/normalizers.py
```

## Decisoes importantes

1. Ainda nao usar APIs externas.
2. Construir primeiro a arquitetura deterministica e testavel.
3. Manter schemas internos estaveis.
4. Usar adapters para traduzir dados externos para os schemas do projeto.
5. Bloquear recomendacoes quando nao houver evidencia suficiente.
6. Manter Obsidian como caderno de aprendizado.
7. Manter apenas um handoff atualizado.
8. Comitar direto na `main` enquanto o projeto for individual e os commits forem pequenos.

## Proximo passo recomendado

Melhorar o `Recommendation Agent` para recomendar tecnologias NVIDIA de forma menos generica.

Exemplos de mapeamento esperado:

```text
LLM/agentes
 -> NVIDIA NIM
 -> NeMo Guardrails
 -> Triton

dados tabulares/pipelines
 -> RAPIDS
 -> cuDF
 -> cuML

voz/transcricao/call center
 -> NVIDIA Riva

saude/life sciences
 -> NVIDIA Clara

robotics/simulacao
 -> Isaac
 -> Omniverse

latencia/inferencia
 -> Triton
 -> TensorRT-LLM
```

Esse passo ainda pode ser feito sem APIs, usando regras deterministicas e testes.

## Conclusao

O projeto terminou este ciclo com uma base mais solida: ambiente validado, grafo funcional, evidencias mais bem tratadas, testes verdes, aprendizado documentado e handoff pronto para continuidade.

O principal ganho foi sair de uma configuracao inicial para uma arquitetura que ja evita uma falha comum em projetos de IA: recomendar ou concluir coisas sem prova rastreavel.
