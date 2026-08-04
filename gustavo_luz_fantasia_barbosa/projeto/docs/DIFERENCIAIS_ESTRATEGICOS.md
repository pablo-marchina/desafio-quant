# Diferenciais Estrategicos - Seraphim Scout

Este documento existe para separar o projeto do caminho obvio do case. Se todo
mundo entrega scraping, agentes, RAG e dashboard, o diferencial precisa estar em
qualidade de decisao, utilidade comercial, rastreabilidade e descoberta ativa de
oportunidades.

## Tese de diferenciacao

O Seraphim Scout nao deve ser defendido como "um chatbot com RAG sobre
NVIDIA". A melhor defesa e:

> Uma plataforma de inteligencia de mercado e prospeccao tecnica que ajuda a
> NVIDIA a descobrir startups brasileiras, estimar timing de abordagem, explicar
> o risco de commoditizacao por wrappers de IA e sugerir uma primeira conversa
> tecnica com evidencias rastreaveis.

## Diferenciais ja fortes no projeto

1. **Rastreabilidade real de evidencias**

   O projeto ja liga recomendacoes a fontes da startup, fontes NVIDIA, checks de
   evidencia, IDs de chunks e historico da pipeline. Isso e mais defensavel que
   apenas gerar uma resposta bonita.

2. **Freshness da base NVIDIA**

   A checagem de atualizacao antes da analise mostra preocupacao com informacao
   tecnica recente. Poucos projetos vao alem de uma base RAG estatica.

3. **Radar de oportunidade, nao apenas analise individual**

   O radar prioriza startups candidatas e transforma o sistema em ferramenta de
   prospeccao. Isso aproxima o projeto de uso real por NVIDIA Inception, vendas,
   developer relations e parcerias.

4. **Scores com leitura de negocio**

   AI-Native Score, Wrapper Risk Score e NVIDIA Fit Score tornam o resultado
   comparavel entre startups. O clique explicativo do percentual na interface
   ajuda a defender a formula sem parecer caixa-preta.

5. **Briefing acionavel**

   O briefing agora inclui um playbook de abordagem NVIDIA com timing sugerido,
   hipotese de valor, risco competitivo e pergunta de descoberta. Isso reduz a
   distancia entre "analise" e "proxima acao".

6. **Angel Thesis**

   A interface agora resume a leitura do scout em uma tese curta: por que a
   startup merece atencao, quais sinais sustentam essa leitura e qual primeira
   validacao precisa acontecer antes da abordagem. Esse bloco conecta o conceito
   de investidor-anjo ao uso pratico do produto.

## Diferenciais que mais podem ajudar antes da entrega

### 1. Opportunity Timing Score

Criar um score ou faixa simples: `quente`, `morno`, `exploratorio`.

Por que diferencia:

- Ajuda a NVIDIA a decidir quem abordar agora.
- Junta fit tecnico, evidencia publica, maturidade e risco wrapper.
- Parece produto de prospeccao, nao apenas avaliador tecnico.

Implementacao MVP:

- Ja existe no briefing como timing sugerido.
- Tambem aparece no Radar como `quente`, `morno` ou `exploratorio`.

### 2. Playbook de abordagem por startup

Para cada startup, gerar:

- mensagem curta de abertura;
- pergunta tecnica principal;
- piloto NVIDIA sugerido;
- metrica de sucesso do piloto;
- risco que precisa ser validado.

Por que diferencia:

- Entrega valor direto para uma pessoa de BD, Inception ou DevRel.
- Mostra que o sistema entende acao comercial e tecnica juntas.

Implementacao MVP:

- O briefing ja gera timing, hipotese de valor, risco competitivo e pergunta de
  descoberta.
- A interface tambem exibe o playbook na analise manual e no detalhe da startup.

### 3. Wrapper Displacement Map

Mapear se a startup corre risco de ser substituida por funcionalidades nativas
de grandes labs.

Sinais uteis:

- produto descrito como chatbot generico;
- pouca evidencia de dados proprietarios;
- ausencia de workflow setorial profundo;
- dependencia de API externa;
- baixa barreira de entrada;
- sem sinais de avaliacao, governanca, latencia ou producao.

Por que diferencia:

- Conecta diretamente com a pergunta norteadora do projeto.
- Ajuda a NVIDIA a identificar startups que precisam evoluir de wrapper para
  infraestrutura propria, performance e governanca.

Implementacao MVP:

- Usar `wrapper_risk_score` atual.
- A interface mostra o Wrapper Displacement Map com sinais de risco e caminho
  NVIDIA.

### 4. NVIDIA Adoption Path

Em vez de recomendar ferramentas soltas, sugerir uma trilha:

1. Diagnostico: medir latencia, custo, dependencia e uso atual de IA.
2. Piloto: testar NIM, Triton, RAPIDS, cuOpt, Riva ou Guardrails em um caso
   pequeno.
3. Escala: avaliar operacao, observabilidade, seguranca e custo.
4. Comunidade: encaminhar para NVIDIA Inception, creditos, suporte ou GTM.

Por que diferencia:

- Faz a recomendacao parecer jornada de adocao, nao lista de produtos.
- Ajuda a banca a enxergar maturidade de produto.

Implementacao MVP:

- Derivar a trilha da categoria da tecnologia recomendada e do gap principal.

### 5. Evidence Quality Gate

Antes de mostrar recomendacao forte, exigir:

- pelo menos uma fonte publica da startup ou descricao manual robusta;
- fonte NVIDIA recuperada;
- score minimo de recuperacao;
- trecho tecnico com tamanho minimo;
- motivo explicito quando a recomendacao for bloqueada.

Por que diferencia:

- Ataca alucinacao, um problema comum em projetos com LLM.
- Mostra engenharia responsavel.

Implementacao MVP:

- Ja implementado no Evidence Validator.
- O gate tambem aparece visualmente na analise manual, com status aceita,
  rebaixada ou bloqueada.

### 6. Angel Thesis

Transformar scores e evidencias em uma tese de oportunidade:

- tese exploratoria quando falta lastro;
- tese de transformacao quando ha risco wrapper alto;
- tese angel-ready quando ha bom fit, sinais de IA e timing favoravel;
- primeira validacao tecnica/comercial recomendada.

Por que diferencia:

- Conecta a marca Seraphim Scout ao conceito de investidor-anjo.
- Ajuda a banca a entender o "por que agora" em linguagem de decisao.
- Evita que os scores fiquem soltos sem uma tese de abordagem.

Implementacao MVP:

- Ja aparece na analise manual e no detalhe da startup.
- Usa scores, timing, risco wrapper, sinais e recomendacao NVIDIA principal.

### 7. Startup Source Quality Dashboard

Medir a qualidade das fontes de descoberta:

- quantidade de startups encontradas;
- duplicacao;
- setor desconhecido;
- confianca media;
- exemplos bons e ruins;
- status `pass`, `warn` ou `fail`.

Por que diferencia:

- A maioria dos projetos ignora qualidade da fonte.
- Isso transforma scraping em pipeline auditavel.

Implementacao MVP:

- Ja existe `scripts/check_startup_sources.py`.
- Proximo passo: criar uma aba pequena no dashboard com o resumo.

### 8. Similar Startup Memory

Quando uma startup for analisada, comparar com outras ja vistas:

- "parecida com X por setor/gap";
- "tem maior NVIDIA fit que Y";
- "risco wrapper maior que startups similares";
- "tecnologia recomendada tambem apareceu em N casos".

Por que diferencia:

- Cria inteligencia acumulada.
- Mostra que o produto melhora com uso.

Implementacao MVP:

- Usar historico do Postgres e embeddings de `startup_evidence`.
- Comecar com comparacao simples por setor, scores e tecnologias.

### 9. Counterfactual Recommendation

Mostrar nao apenas o que recomendar, mas o que nao recomendar ainda.

Exemplo:

- "Nao priorizar Omniverse agora: nao ha evidencia de digital twin ou 3D."
- "Nao priorizar RAPIDS antes de confirmar volume de dados."

Por que diferencia:

- Passa maturidade tecnica.
- Reduz recomendacoes genericas.

Implementacao MVP:

- A interface ja mostra contraindicacoes simples por categoria sem evidencia,
  como voz, digital twins, otimizacao ou dados.

## Melhor aposta para apresentacao

Se houver pouco tempo, priorizar estes tres diferenciais:

1. **Playbook de abordagem NVIDIA no briefing**: ja implementado e facil de
   demonstrar.
2. **Wrapper Displacement Map**: encaixa perfeitamente na narrativa do case.
3. **Angel Thesis**: conecta nome, decisao e "por que abordar agora".
4. **Evidence Quality Gate visivel**: mostra que o sistema nao alucina
   recomendacoes sem lastro.

## Frase para defender na banca

> O diferencial do nosso projeto nao e so usar RAG ou agentes. E transformar
> dados publicos em uma decisao de prospeccao tecnica: quem abordar, por que
> agora, qual risco competitivo existe, qual tecnologia NVIDIA testar primeiro e
> quais evidencias sustentam essa recomendacao.
