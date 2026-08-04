# NeMo Guardrails

NeMo Guardrails é uma biblioteca open-source da NVIDIA para adicionar **trilhos programáveis**
a aplicações baseadas em LLM. Permite definir, de forma declarativa, o que o assistente pode
ou não fazer, mantendo a conversa dentro do escopo e da política do produto.

## Capacidades
- **Rails de tópico e escopo**: mantêm o agente on-narrative, evitando que ele responda fora
  do domínio ou alucine recomendações sem fundamento.
- **Rails de segurança**: filtram entradas/saídas tóxicas, jailbreaks e vazamento de dados
  sensíveis; integram-se a checadores externos.
- **Rails factuais / anti-alucinação**: ancoram a resposta em fontes recuperadas (RAG),
  bloqueando afirmações sem evidência citável.
- **Configuração declarativa**: políticas em Colang/YAML, versionáveis junto do código.

## Quando recomendar
Essencial para startups que colocam agentes de LLM em produção e precisam de **governança**:
call centers, assistentes regulados (saúde, finanças), automação de workflow. Endereça o gap
de **Workflow Depth** quando há agentes sem controle. No próprio TAPI, o Guardrails protege o
Briefing Agent — nenhuma recomendação sai sem evidência dos dois lados (princípio nº1).
