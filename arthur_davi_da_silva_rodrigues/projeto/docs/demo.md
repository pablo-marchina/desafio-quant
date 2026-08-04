# Guia de Demonstração

## Como Rodar

1. Instale dependências:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

2. Configure ambiente:

```bash
cp .env.example .env
```

3. Suba serviços:

```bash
docker compose up -d
```

4. Rode a API:

```bash
uvicorn app.main:app --reload
```

5. Rode a interface:

```bash
python3 -m http.server 5180 --bind 127.0.0.1 -d web
```

URLs:

- Interface: http://127.0.0.1:5180
- Documentação da API: http://127.0.0.1:8000/docs

## Fluxo de Apresentação

1. Abrir a interface.
2. Mostrar que o tema acompanha o dispositivo e pode alternar entre claro/noturno.
3. Rodar uma busca como `IA generativa para saúde`.
4. Explicar que o sistema coleta notícias recentes e usa LLM para extrair e rankear empresas candidatas quando `OPENAI_API_KEY` está configurada.
5. Escolher uma candidata e clicar em `Analisar`.
6. Rodar a análise da startup.
7. Mostrar perfil, maturidade de IA, radar de ameaça, gaps e recomendações.
8. Abrir a prévia do briefing.
9. Demonstrar copiar, baixar, imprimir ou enviar por e-mail.

## Exemplo Manual

```text
MedAI automatiza fluxos de trabalho em saúde com agentes de IA e copilotos baseados em LLM.
A plataforma usa APIs da OpenAI e enfrenta pressão de latência.
```

## Pontos de Destaque

- O sistema não analisa apenas startups específicas: ele também descobre candidatas no mercado.
- O ranking considera sinais de IA-native, fit NVIDIA, risco de wrapper, urgência, recência e evidências.
- Com `OPENAI_API_KEY`, a descoberta, extração, classificação, diagnóstico, recomendações e radar usam LLM.
- O briefing final serve como material executivo de priorização e outreach.
- O envio por e-mail é real quando SMTP está configurado.

## O Que Precisa Estar Configurado

- Docker rodando para PostgreSQL e Qdrant.
- `.env` criado a partir de `.env.example`.
- `OPENAI_API_KEY` configurada se quiser demonstrar a análise completa com LLM.
- `OPENAI_MODEL` ajustado para o modelo que será usado na demonstração.
- SMTP configurado apenas se quiser demonstrar envio real de e-mail.

Sem `OPENAI_API_KEY`, o sistema usa fallback local. Sem SMTP, o sistema ainda permite copiar, baixar e imprimir relatórios.
