# Scraper V1 — Estado Implementado e Próximos Passos

## 1. Objetivo deste documento

Este documento descreve a primeira versão funcional do módulo `scraping`.

Ele registra:

```txt
o que foi implementado
como o fluxo funciona atualmente
quais decisões arquiteturais foram adotadas
quais limitações ainda existem
como executar e testar o módulo
qual é a ordem recomendada dos próximos passos
```

O documento `modulo_scraping_atualizado.md` continua sendo a referência da
arquitetura desejada. Este arquivo descreve o estado real da implementação V1.

---

## 2. Escopo da V1

A V1 recebe uma URL pública, coleta o HTML, extrai texto básico, valida a
qualidade do conteúdo e produz um resultado bruto aprovado.

Fluxo atual:

```txt
Criar ScrapingJob
→ executar BeautifulSoupScraper
→ validar tecnicamente a URL e a resposta
→ validar qualidade textual
→ calcular sinais evidenciais básicos
→ calcular quality_score
→ aceitar, aplicar fallback ou rejeitar
→ registrar ScrapingAttempt
→ salvar ScrapingResult aprovado
→ concluir ou falhar o job
```

A V1 não executa:

```txt
Playwright real
Trafilatura
Firecrawl
PostgreSQL
Redis ou Dramatiq
revisão semântica com LLM
investigação com agentes
ingestion
chunking
embeddings
RAG
recomendação NVIDIA
```

---

## 3. Arquitetura implementada

O módulo segue a arquitetura em camadas definida na documentação:

```txt
Presentation
→ entrada e saída HTTP

Application
→ casos de uso, pipeline, DTOs, portas, limites e serviços

Domain
→ entidades, estados, exceções, contratos e políticas

Infrastructure
→ BeautifulSoup, HTTP, proteção SSRF, validadores e repositórios em memória

Factories
→ composição das implementações concretas

Worker externo
→ chama o caso de uso pela factory
```

Regra de dependência aplicada:

```txt
presentation → application → domain
infrastructure → application/domain
factory → conecta todas as camadas
worker externo → factory/caso de uso
```

---

## 4. Estrutura atual

```txt
apps/api/src/modules/scraping/
├── presentation/
│   ├── routes.py
│   └── schemas.py
├── application/
│   ├── use_cases/
│   │   ├── create_scraping_job.py
│   │   ├── execute_scraping_job.py
│   │   ├── get_scraping_job.py
│   │   └── get_scraping_result.py
│   ├── dto.py
│   ├── ports.py
│   ├── quality_scoring_service.py
│   ├── scraping_limits.py
│   ├── scraping_pipeline.py
│   └── strategy_selector.py
├── domain/
│   ├── entities.py
│   ├── enums.py
│   ├── exceptions.py
│   ├── policies.py
│   └── repositories.py
├── infrastructure/
│   ├── queue/
│   ├── repositories/
│   ├── scrapers/
│   ├── security/
│   └── validators/
├── factories/
│   └── scraping_factory.py
└── tests/
    ├── unit/
    └── integration/

workers/scraper_worker/
└── tasks.py
```

---

## 5. Entidades principais

### ScrapingJob

Representa o processo completo de scraping.

```txt
pending → running → completed
                  → failed
```

O próprio objeto bloqueia transições inválidas.

### ScrapingAttempt

Representa uma tentativa feita com uma estratégia específica.

Exemplo:

```txt
BeautifulSoup
→ texto insuficiente
→ fallback
```

Cada tentativa registra:

```txt
método
status
decisão
scores
problemas
warnings
erro técnico
timestamps
```

### ScrapingResult

Representa somente conteúdo aprovado.

Guarda:

```txt
URL original e final
título
HTML bruto
texto bruto
método utilizado
status HTTP
scores
hash do conteúdo
metadados
```

---

## 6. Pipeline atual

A `ScrapingPipeline` coordena componentes especializados.

```txt
StrategySelector escolhe estratégias
→ Scraper coleta
→ DeterministicValidator mede qualidade
→ QualityScoringService calcula quality_score
→ ValidationDecisionPolicy decide
→ AttemptRepository registra a tentativa
→ pipeline retorna ScrapingResult aprovado
```

Decisões atuais:

```txt
ACCEPT
→ produz ScrapingResult

FALLBACK
→ tenta a próxima estratégia disponível

REJECT
→ encerra sem resultado aprovado
```

Atualmente a factory configura apenas o `BeautifulSoupScraper`. A pipeline já
suporta várias estratégias, mas as demais ainda não foram implementadas.

---

## 7. Validação determinística

O `BasicDeterministicValidator` calcula:

```txt
technical_score
text_score
evidence_score
```

### Validação técnica

Verifica:

```txt
URL de origem
status HTTP
content-type
HTML vazio
captcha
```

### Validação textual

Verifica:

```txt
quantidade de caracteres
quantidade de palavras
repetição
texto insuficiente
```

### Sinais evidenciais

Procura sinais básicos relacionados à IA:

```txt
inteligência artificial
machine learning
deep learning
computer vision
modelos de linguagem
IA generativa
```

Esses sinais não provam o uso real de IA. Eles servem apenas para o score
inicial e futuramente serão complementados pela validação semântica.

---

## 8. Score e políticas

Fórmula implementada:

```txt
quality_score =
    technical_score × 0.30
    + text_score × 0.30
    + evidence_score × 0.40
```

Regras iniciais:

```txt
quality_score >= 0.75 e sem bloqueadores
→ ACCEPT

problema recuperável e existe próxima estratégia
→ FALLBACK

demais casos
→ REJECT
```

Problemas bloqueadores incluem:

```txt
captcha
conteúdo vazio
status bloqueado
URL ausente
content-type não suportado
```

---

## 9. Limites e fallback

Existem dois níveis de limites.

### Limites por estratégia

`ScrapingLimits`:

```txt
timeout_seconds = 15
max_response_bytes = 5 MB
max_redirects = 5
```

Uma estratégia que excede esses limites gera erro recuperável e pode permitir
fallback para outra tecnologia.

### Limites globais da pipeline

`PipelineLimits`:

```txt
max_strategies = 4
total_timeout_seconds = 90
```

Quando um limite global é atingido, o job inteiro deve parar.

Diferença:

```txt
limite individual excedido
→ pode trocar de tecnologia

limite global excedido
→ encerra o job
```

---

## 10. Segurança SSRF

O `UrlGuard` bloqueia:

```txt
esquemas diferentes de HTTP/HTTPS
localhost
IPs privados
IPs reservados
endereços de metadata cloud
domínios que resolvem para IPs internos
```

Redirects são seguidos manualmente.

Fluxo seguro:

```txt
recebe redirect
→ lê Location
→ transforma destino em URL absoluta
→ valida destino com UrlGuard
→ somente depois realiza a próxima requisição
```

Isso impede que uma URL pública redirecione o scraper para um serviço interno.

---

## 11. Persistência atual

A V1 utiliza repositórios em memória:

```txt
InMemoryScrapingJobRepository
InMemoryScrapingAttemptRepository
InMemoryScrapingResultRepository
```

Vantagens:

```txt
permite desenvolver sem banco
facilita testes
preserva os contratos de repositório
```

Limitação:

```txt
todos os dados são perdidos quando o processo reinicia
```

O índice por `content_hash` já permite procurar resultados com conteúdo igual.

---

## 12. Dispatcher e worker

O `LocalTaskDispatcher` executa o job no mesmo processo.

Fluxo atual:

```txt
CreateScrapingJob
→ salva job
→ LocalTaskDispatcher
→ ExecuteScrapingJob
```

Ele preserva a porta `TaskDispatcher`, mas ainda espera a execução terminar.

O worker externo existe em:

```txt
workers/scraper_worker/tasks.py
```

Ele recebe apenas `job_id` e chama o caso de uso pela factory. A lógica de
scraping não fica no worker.

---

## 13. API disponível

Endpoints:

```txt
POST /scraping/jobs
GET /scraping/jobs/{job_id}
GET /scraping/results/{result_id}
GET /health
```

Exemplo de criação:

```json
{
  "url": "https://example.com"
}
```

Observação: como o dispatcher atual é local, o endpoint de criação ainda espera
o scraping terminar antes de responder.

---

## 14. Como executar

Instalar dependências:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Executar API:

```powershell
.\venv\Scripts\python.exe -m uvicorn apps.api.src.main:app --reload --port 8000
```

Documentação interativa:

```txt
http://localhost:8000/docs
```

Executar todos os testes do módulo:

```powershell
.\venv\Scripts\python.exe -m pytest apps\api\src\modules\scraping\tests -v
```

Estado atual da suíte:

```txt
34 testes passando
```

---

## 15. Limitações conhecidas da V1

```txt
somente BeautifulSoup está implementado
não existe fallback técnico real para outra tecnologia
persistência é apenas em memória
dispatcher local não é realmente assíncrono
worker ainda não consome uma fila
repositórios em memória não funcionam entre processos separados
não existe validação semântica com LLM
não existe investigação com agentes
não existe deduplicação como política da pipeline
limites e thresholds ainda não foram calibrados com dataset real
```

Uma limitação arquitetural importante:

```txt
API e worker separados não podem compartilhar repositórios em memória.
```

Por isso, PostgreSQL precisa ser implementado antes de ativar uma fila e um
worker realmente separados.

---

## 16. Próximos passos recomendados

### Passo 1 — Persistência PostgreSQL

Objetivo:

```txt
substituir repositórios em memória por persistência real
```

Entregáveis:

```txt
SQLAlchemy assíncrono
Alembic
tabelas scraping_jobs, scraping_attempts e scraping_results
mappers entre models e entidades
repositórios PostgreSQL
testes de integração de persistência
```

Esse é o próximo passo prioritário porque permite separar API e worker.

### Passo 2 — Redis + Dramatiq

Objetivo:

```txt
executar scraping fora do processo da API
```

Entregáveis:

```txt
DramatiqTaskDispatcher
configuração Redis
processo scraper_worker
retries controlados
API retorna job pending imediatamente
```

### Passo 3 — Playwright real

Objetivo:

```txt
criar fallback para páginas dependentes de JavaScript
```

Entregáveis:

```txt
PlaywrightScraper implementando a porta Scraper
limites específicos da estratégia
tratamento de timeout
registro das tentativas
testes com páginas dinâmicas
```

### Passo 4 — Melhorar validação determinística

Objetivo:

```txt
reduzir falsos positivos e falsos negativos
```

Entregáveis:

```txt
separar validadores técnico, textual e evidencial
detectar boilerplate
medir proporção de links
detectar idioma
detectar duplicidade
identificar páginas dependentes de JavaScript
calibrar thresholds com exemplos reais
```

### Passo 5 — Trafilatura

Objetivo:

```txt
melhorar extração de artigos, notícias e blogs
```

Entregáveis:

```txt
TrafilaturaScraper
regras do StrategySelector por tipo de fonte
comparação de qualidade por estratégia
```

### Passo 6 — Validação semântica com LLM

Objetivo:

```txt
analisar somente conteúdos intermediários ou ambíguos
```

Entregáveis:

```txt
LLMReviewPolicy
SemanticValidator port
saída estruturada
semantic_confidence calculado pelo sistema
controle de custo e latência
```

### Passo 7 — Agentes

Objetivo:

```txt
investigar casos que exigem múltiplas fontes ou ferramentas
```

O agente deverá ser implementado no módulo `agents`. O módulo `scraping`
conhecerá apenas o contrato público `SemanticInvestigator`.

### Passo 8 — Integração com ingestion

Objetivo:

```txt
entregar somente resultados brutos aprovados para tratamento
```

Entregáveis:

```txt
ScrapingResultReader público
acionamento da ingestion
contrato RawScrapingDocumentDTO
```

---

## 17. Ordem recomendada imediata

Sequência sugerida a partir do estado atual:

```txt
1. PostgreSQL + SQLAlchemy + Alembic
2. repositórios PostgreSQL
3. Redis + Dramatiq
4. worker realmente separado
5. Playwright como fallback real
6. validação determinística mais completa
7. Trafilatura
8. validação semântica com LLM
9. agentes
10. integração com ingestion
```

---

## 18. Critério para considerar a V1 concluída

A V1 atual demonstra corretamente:

```txt
arquitetura em camadas
casos de uso
pipeline de scraping
validação determinística
scores e políticas
registro de tentativas
segurança SSRF
limites individuais e globais
API
worker externo sem lógica de negócio
testes unitários e integrados
```

Ela é uma base funcional e testada para a evolução do módulo, mas ainda não é
uma versão pronta para produção por utilizar persistência e dispatcher locais.
