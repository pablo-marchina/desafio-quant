# NVIDIA Startup AI Radar

Plataforma para descobrir startups brasileiras IA-native, coletar evidências públicas recentes, rankear oportunidades para NVIDIA, analisar maturidade de IA e gerar briefings executivos.

O projeto tem dois fluxos principais:

- Descoberta de mercado: busca automática em fontes recentes via Google News RSS, extração de candidatas e ranking por LLM quando configurado, usando sinais IA-native, fit NVIDIA, urgência, risco de wrapper, recência e quantidade de evidências.
- Análise de startup: análise de uma empresa específica a partir de URL/texto público, com perfil, evidências, maturidade de IA, gaps, recomendações NVIDIA, radar de ameaça/oportunidade e briefing em Markdown. Com `OPENAI_API_KEY`, as etapas analíticas usam LLM; sem chave, usam fallback local.

## Stack

- FastAPI
- SQLAlchemy + PostgreSQL
- Qdrant
- Python 3.11+
- Frontend estático em HTML/CSS/JavaScript
- Docker Compose para serviços locais

## Funcionalidades

- Crawling de descoberta por consultas de mercado.
- Ranking automático de empresas candidatas com LLM e fallback local.
- UI em português com modo claro/escuro baseado no dispositivo.
- Logo NVIDIA adaptada para tema claro e noturno.
- Extração estruturada de perfil de startup.
- Classificação de maturidade AI-native.
- Diagnóstico de gaps de stack de IA.
- Recomendações de tecnologias NVIDIA.
- Radar de risco de wrapper, defensibilidade, fit NVIDIA e urgência.
- Briefing executivo em Markdown.
- Download, impressão e envio de relatório por e-mail via SMTP.

## Configuração Local

Crie o ambiente Python:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Crie o arquivo de ambiente:

```bash
cp .env.example .env
```

Suba os serviços:

```bash
docker compose up -d
```

Inicie a API:

```bash
uvicorn app.main:app --reload
```

Em outro terminal, sirva a UI:

```bash
python3 -m http.server 5180 --bind 127.0.0.1 -d web
```

Acesse:

- UI: http://127.0.0.1:5180
- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

## Variáveis de Ambiente

As variáveis ficam em `.env`. Não suba `.env` para o GitHub.

Obrigatórias para o funcionamento local básico:

```bash
APP_NAME=NVIDIA Startup AI Radar
APP_ENV=development
DATABASE_URL=postgresql+psycopg://radar:radar@localhost:5433/radar
QDRANT_URL=http://localhost:6333
SCRAPER_USER_AGENT=NVIDIA Startup AI Radar/0.1
```

Opcionais:

```bash
MODEL_PROVIDER=openai
OPENAI_MODEL=gpt-4.1-mini
OPENAI_API_KEY=
COHERE_API_KEY=
```

`OPENAI_API_KEY` ativa LLM para extração, classificação, diagnóstico de gaps, recomendações, radar estratégico e rankeamento de candidatas descobertas no crawling. Sem chave, o sistema usa fallback local para manter a demo funcionando.

`OPENAI_MODEL` define o modelo usado. Troque para o modelo mais forte disponível na sua conta quando quiser maior qualidade. Para demonstração rápida e custo menor, mantenha um modelo menor.

Para envio de relatório por e-mail, configure SMTP:

```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=usuario
SMTP_PASSWORD=senha
SMTP_FROM_EMAIL=radar@example.com
SMTP_USE_TLS=true
```

Sem SMTP configurado, o endpoint de e-mail responde `503 SMTP não configurado`.

## Comandos de Desenvolvimento

```bash
make dev
make lint
make test
```

Equivalentes:

```bash
uvicorn app.main:app --reload
ruff check .
pytest
```

## Principais Endpoints

Descoberta de mercado:

```bash
curl -X POST http://127.0.0.1:8000/runs/discovery \
  -H "Content-Type: application/json" \
  -d '{"query":"IA generativa para saúde","country":"Brasil","max_results":5}'
```

Análise de URL:

```bash
curl -X POST http://127.0.0.1:8000/runs/analyze-url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","fetch":false}'
```

Extração direta de perfil:

```bash
curl -X POST http://127.0.0.1:8000/extraction/startup-profile \
  -H "Content-Type: application/json" \
  -d '{"url":"https://medai.example","title":"MedAI","extracted_text":"MedAI automatiza fluxos de trabalho em saúde com agentes de IA e copilotos baseados em LLM."}'
```

Classificação de maturidade:

```bash
curl -X POST http://127.0.0.1:8000/classification/ai-maturity \
  -H "Content-Type: application/json" \
  -d '{"url":"https://medai.example","title":"MedAI","extracted_text":"MedAI usa agentes de IA e LLMs em produção."}'
```

Diagnóstico de gaps:

```bash
curl -X POST http://127.0.0.1:8000/diagnostics/gaps \
  -H "Content-Type: application/json" \
  -d '{"url":"https://medai.example","title":"MedAI","extracted_text":"MedAI usa APIs da OpenAI e enfrenta pressão de latência."}'
```

Recomendações NVIDIA:

```bash
curl -X POST http://127.0.0.1:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{"url":"https://medai.example","title":"MedAI","extracted_text":"MedAI usa APIs da OpenAI e enfrenta pressão de latência."}'
```

Radar de ameaça e oportunidade:

```bash
curl -X POST http://127.0.0.1:8000/radar/threat-opportunity \
  -H "Content-Type: application/json" \
  -d '{"url":"https://medai.example","title":"MedAI","extracted_text":"MedAI usa APIs da OpenAI e enfrenta pressão de latência."}'
```

Briefing executivo:

```bash
curl -X POST http://127.0.0.1:8000/briefings \
  -H "Content-Type: application/json" \
  -d '{"url":"https://medai.example","title":"MedAI","extracted_text":"MedAI usa APIs da OpenAI e enfrenta pressão de latência."}'
```

Enviar relatório por e-mail:

```bash
curl -X POST http://127.0.0.1:8000/briefings/email \
  -H "Content-Type: application/json" \
  -d '{"to_email":"vc@example.com","subject":"Relatório NVIDIA Startup AI Radar","markdown":"# Relatório\n\nConteúdo."}'
```

## O Que Você Precisa Mudar Antes de Apresentar

- `.env`: copie de `.env.example` e ajuste se necessário.
- SMTP: configure apenas se quiser enviar e-mails reais.
- `DATABASE_URL`: mantenha o padrão se usar o `docker-compose.yml` local.
- `QDRANT_URL`: mantenha o padrão se usar o `docker-compose.yml` local.
- Logo: já está em `web/src/images/`.
- Dados reais: a descoberta usa Google News RSS, então depende de rede e da qualidade das fontes retornadas.
- `OPENAI_API_KEY`: configure para apresentar a versão com LLM. Sem ela, o projeto ainda roda, mas com fallback local.

Para a melhor demonstração, configure `OPENAI_API_KEY` e mantenha `OPENAI_MODEL` ajustado para o modelo que você quer usar na conta.

## Limitações Atuais

- O crawler usa Google News RSS; se não houver `OPENAI_API_KEY`, o rankeamento cai para fallback local.
- A extração de nome de empresa a partir de títulos ainda pode precisar de validação humana.
- O sistema não resolve todos os links do Google News para a URL final da empresa.
- Persistência em PostgreSQL depende do Docker estar rodando.
- Envio de e-mail depende de SMTP válido.
- Não há autenticação/multiusuário ainda.

## Subir Para o GitHub

Esta pasta ainda não está inicializada como Git. Para publicar:

```bash
git init
git add .
git commit -m "Initial NVIDIA Startup AI Radar MVP"
```

Crie um repositório vazio no GitHub e conecte:

```bash
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/nvidia-startup-ai-radar.git
git push -u origin main
```

Antes do push, confira:

```bash
git status
```

Garanta que `.env` não aparece no commit. O `.gitignore` já ignora `.env`, `.venv/`, caches Python e dados locais.

## Estrutura

```text
app/
  api/              Rotas FastAPI
  briefings/        Geração e envio de relatórios
  classification/   Classificação de maturidade de IA
  collectors/       Coleta e parsing de páginas
  diagnostics/      Diagnóstico de gaps
  discovery/        Crawling e ranking de mercado
  rag/              Catálogo e busca de tecnologias NVIDIA
  radar/            Radar de ameaça/oportunidade
  recommendations/  Motor de recomendações
web/
  index.html        UI estática
  app.js            Lógica do frontend
  styles.css        Tema claro/escuro e layout
  src/images/       Logos NVIDIA
tests/              Testes automatizados
docs/               Arquitetura, demo e glossário
```

## Documentação

- [Architecture](docs/architecture.md)
- [Demo Guide](docs/demo.md)
- [Glossary](docs/glossary.md)
