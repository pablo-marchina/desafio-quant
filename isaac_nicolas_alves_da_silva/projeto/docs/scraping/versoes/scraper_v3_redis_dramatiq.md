# Scraper V3 - Redis, Dramatiq e Worker Distribuido

## 1. Objetivo

A V3 separa a criacao do job de sua execucao.

Na V2, PostgreSQL tornou os dados duraveis, mas o `LocalTaskDispatcher`
executava o scraping dentro do processo da API. Na V3, a API publica uma
mensagem no Redis e um worker separado executa o caso de uso.

```txt
V1 -> fluxo funcional em memoria
V2 -> persistencia PostgreSQL
V3 -> fila Redis e worker Dramatiq separado
```

Estado verificado ao concluir esta versao:

```txt
68 testes passando
```

---

## 2. Fluxo atual

### Processo da API

```txt
POST /scraping/jobs
-> cria ScrapingJob pending
-> salva e confirma no PostgreSQL
-> publica somente job_id no Redis
-> responde imediatamente
```

### Processo worker

```txt
Redis
-> worker consome mensagem
-> actor converte job_id para UUID
-> factory cria ExecuteScrapingJob
-> job muda para running
-> pipeline executa scraping
-> PostgreSQL recebe tentativa, resultado e estado final
```

Fluxo completo:

```txt
FastAPI
-> CreateScrapingJob
-> PostgreSQL: pending
-> DramatiqTaskDispatcher
-> Redis
-> scraper_worker
-> ExecuteScrapingJob
-> PostgreSQL: running
-> scraping e validacao
-> PostgreSQL: completed ou failed
```

---

## 3. Componentes adicionados

```txt
apps/api/src/modules/scraping/infrastructure/queue/
|-- dramatiq_broker.py
`-- dramatiq_task_dispatcher.py

workers/scraper_worker/
|-- run.py
`-- tasks.py

apps/api/src/modules/scraping/tests/
|-- unit/
|   |-- test_dramatiq_task_dispatcher.py
|   |-- test_scraper_worker_entrypoint.py
|   |-- test_create_scraping_job.py
|   |-- test_execute_scraping_job.py
|   `-- test_health.py
`-- integration/
    `-- test_distributed_worker_flow.py
```

Dependencia adicionada:

```txt
dramatiq[redis]>=2.1,<3
```

---

## 4. Broker Redis

O arquivo `dramatiq_broker.py` cria o `RedisBroker` usando:

```txt
REDIS_URL=redis://localhost:6379
```

O broker possui o middleware `AsyncIO`.

Esse middleware e necessario porque o actor chama casos de uso assincronos:

```python
async def execute_scraping_job(job_id: str) -> None:
    ...
```

Responsabilidades:

```txt
Redis transporta mensagens
PostgreSQL armazena estado e resultados
```

Redis nao armazena documentos completos. Cada mensagem transporta somente o
identificador do job.

---

## 5. Actor do worker

O actor fica fora do modulo de scraping:

```txt
workers/scraper_worker/tasks.py
```

Configuracao:

```txt
actor: execute_scraping_job
fila: scraping
max_retries: 3
argumento: job_id como string
```

O worker nao possui logica de negocio.

Ele somente:

```txt
recebe job_id
-> converte para UUID
-> chama ExecuteScrapingJob pela ScrapingFactory
```

---

## 6. DramatiqTaskDispatcher

`DramatiqTaskDispatcher` implementa a porta `TaskDispatcher`.

```txt
Application conhece TaskDispatcher
Infrastructure implementa DramatiqTaskDispatcher
```

O envio usa `asyncio.to_thread` porque o cliente Redis utilizado por
`Actor.send`/`broker.enqueue` e sincrono.

```python
await asyncio.to_thread(publisher.send, str(job_id))
```

Isso evita bloquear o event loop da FastAPI durante a publicacao.

---

## 7. Publicacao sem importar o worker

A factory nao importa `workers.scraper_worker.tasks`.

Essa regra evita:

```txt
dependencia circular
modulo interno dependendo de processo externo
factory conhecendo detalhes do worker
```

O `DramatiqJobPublisher` cria uma mensagem pelo contrato:

```txt
actor_name = execute_scraping_job
queue_name = scraping
args = (job_id,)
```

O worker registra o actor com o mesmo nome e consome a mensagem.

---

## 8. Factory na V3

A `ScrapingFactory` agora usa:

```txt
DramatiqTaskDispatcher
DramatiqJobPublisher
RedisBroker
```

Ela nao usa mais `LocalTaskDispatcher` no fluxo da API.

Efeito:

```txt
antes:
POST aguardava o scraping terminar

agora:
POST confirma o job pending, publica e responde
```

O `LocalTaskDispatcher` permanece util para testes isolados.

---

## 9. Ponto de entrada do worker

Arquivo:

```txt
workers/scraper_worker/run.py
```

Configuracao de desenvolvimento:

```txt
processos: 1
threads: 4
fila: scraping
```

Executar:

```powershell
.\venv\Scripts\python.exe workers\scraper_worker\run.py
```

O processo permanece ativo aguardando mensagens.

---

## 10. Idempotencia e retries

Filas normalmente oferecem entrega "pelo menos uma vez".

Isso significa:

```txt
a mesma mensagem pode ser entregue novamente
```

Para impedir scraping duplicado, `ExecuteScrapingJob` executa somente jobs
`pending`.

```txt
pending -> pode executar
running -> ignora mensagem duplicada
completed -> ignora mensagem duplicada
failed -> ignora mensagem duplicada
cancelled -> ignora mensagem duplicada
```

Isso protege:

```txt
resultados duplicados
tentativas duplicadas
transicoes invalidas
```

Limitacao conhecida:

```txt
um job que ficar running apos queda abrupta precisa de uma politica futura de
recuperacao por timeout ou lease
```

---

## 11. Falha ao publicar no Redis

O job precisa ser confirmado no PostgreSQL antes de ser publicado.

```txt
commit antes do dispatch
```

Motivo:

```txt
o worker precisa encontrar o job quando consumir a mensagem
```

Se o Redis estiver indisponivel:

```txt
DramatiqTaskDispatcher converte a falha para TaskDispatchError
-> CreateScrapingJob marca o job como failed
-> estado e motivo sao persistidos
-> API responde HTTP 503
```

O job nao e apagado porque seu historico e util para auditoria.

Limitacao conhecida:

```txt
existe uma pequena janela entre commit no PostgreSQL e publicacao no Redis
```

A solucao mais forte para uma versao futura e o padrao Transactional Outbox.

---

## 12. Health check

Endpoint:

```txt
GET /health
```

Ele verifica:

```txt
PostgreSQL
Redis
```

Resposta saudavel:

```json
{
  "status": "ok",
  "dependencies": {
    "postgres": true,
    "redis": true
  }
}
```

Se uma dependencia falhar:

```txt
HTTP 503
status = degraded
```

As verificacoes sao executadas juntas e uma falha nao esconde o estado da
outra dependencia.

---

## 13. Teste distribuido automatizado

Arquivo:

```txt
test_distributed_worker_flow.py
```

O teste utiliza:

```txt
Redis real
broker real
dramatiq.Worker real
actor real
PostgreSQL real
factory real
casos de uso reais
```

Somente a resposta HTTP da pagina e simulada para manter o teste previsivel.

O teste cria uma fila exclusiva com UUID para nao consumir mensagens da fila
normal.

Fluxo validado:

```txt
factory cria job pending
-> mensagem real entra no Redis
-> worker real consome
-> actor chama ExecuteScrapingJob
-> job termina completed no PostgreSQL
```

---

## 14. Teste manual distribuido realizado

Tambem foi executado um worker em processo separado.

Primeiro caso:

```txt
Wikipedia Artificial Intelligence
pending -> running -> failed
motivo: pipeline detectou captcha e repeticao
```

Segundo caso:

```txt
IBM Artificial Intelligence
pending -> running -> completed
quality_score = 0.979
texto extraido = 28042 caracteres
```

Isso validou:

```txt
API/factory
Redis
processo worker separado
HTTP publico real
pipeline
PostgreSQL
```

Os registros criados durante a validacao foram removidos ao final.

---

## 15. Como executar a V3

### Instalar dependencias

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Subir PostgreSQL e Redis

```powershell
docker compose -f infra\docker-compose.yml up -d postgres redis
```

### Aplicar migrations

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

### Iniciar API

```powershell
.\venv\Scripts\python.exe -m uvicorn apps.api.src.main:app --reload --port 8000
```

### Iniciar worker em outro terminal

```powershell
.\venv\Scripts\python.exe workers\scraper_worker\run.py
```

### Criar job

```http
POST /scraping/jobs
```

```json
{
  "url": "https://www.ibm.com/think/topics/artificial-intelligence"
}
```

### Consultar status

```http
GET /scraping/jobs/{job_id}
```

---

## 16. Testes

Executar suite completa:

```powershell
.\venv\Scripts\python.exe -m pytest apps\api\src\modules\scraping\tests -q
```

Estado verificado:

```txt
68 passed
```

Existe um aviso de permissao do cache do pytest no ambiente Windows atual. Ele
nao representa falha funcional da aplicacao ou dos testes.

---

## 17. Limitacoes restantes

```txt
nao existe Transactional Outbox
nao existe recuperacao automatica de jobs presos em running
nao existe dead-letter queue configurada explicitamente
nao existem metricas e logs estruturados da fila
somente BeautifulSoup esta implementado
nao existe fallback real com Playwright
nao existe retry manual de jobs failed
nao existe deploy/container dedicado para API e worker
```

---

## 18. Proximo passo recomendado

O proximo passo funcional recomendado e implementar Playwright como segunda
estrategia real de scraping.

```txt
BeautifulSoup falha por JavaScript ou HTML insuficiente
-> pipeline registra fallback
-> Playwright tenta a mesma URL
-> nova ScrapingAttempt e persistida
```

Antes de producao, tambem sera importante implementar:

```txt
Transactional Outbox
recuperacao de jobs running antigos
dead-letter queue
observabilidade
```

---

## 19. Criterio de conclusao da V3

A V3 pode ser considerada concluida porque demonstra:

```txt
Redis real
Dramatiq configurado
actor async
worker separado
API respondendo com job pending
mensagens contendo somente IDs
execucao idempotente
falha de dispatch tratada
health checks de PostgreSQL e Redis
teste distribuido automatizado
fluxo distribuido manual validado
```

Resumo:

```txt
V1 provou o comportamento.
V2 tornou o estado duravel.
V3 separou API e execucao com fila e worker.
```

