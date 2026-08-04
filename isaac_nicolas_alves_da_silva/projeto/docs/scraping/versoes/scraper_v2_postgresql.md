# Scraper V2 - Persistencia PostgreSQL

## 1. Objetivo deste documento

Este documento descreve a segunda versao funcional do modulo `scraping`.

A V1 demonstrou o fluxo completo usando repositorios em memoria. A V2 mantem
o mesmo dominio, pipeline e API, mas substitui a persistencia usada pela
aplicacao por PostgreSQL real.

Este documento registra:

```txt
o que mudou da V1 para a V2
como o PostgreSQL foi integrado
como as transacoes sao controladas
como models, mappers e repositorios colaboram
como executar migrations e testes
quais limitacoes ainda existem
quais sao os proximos passos recomendados
```

Documentos relacionados:

```txt
docs/scraping/scraper_v1.md
-> estado inicial com persistencia em memoria

docs/scraping/modulo_scraping_atualizado.md
-> arquitetura desejada para a evolucao completa do modulo

docs/scraping/scraper_v2_postgresql.md
-> estado real da implementacao com PostgreSQL
```

---

## 2. Resumo da V2

O objetivo principal desta versao foi:

```txt
substituir repositorios em memoria por persistencia relacional real
```

Entregaveis concluidos:

```txt
PostgreSQL executado com Docker
SQLAlchemy assincrono
asyncpg
Alembic
migration inicial
tabelas scraping_jobs, scraping_attempts e scraping_results
models relacionais
mappers entre models e entidades
repositorios PostgreSQL
Unit of Work transacional
casos de uso adaptados para transacoes
factory configurada com PostgreSQL
testes unitarios e integrados
```

Estado verificado da suite ao concluir esta versao:

```txt
60 testes passando
```

---

## 3. O que permaneceu igual

A V2 nao reescreveu a logica de scraping criada na V1.

Continuam existindo:

```txt
ScrapingJob
ScrapingAttempt
ScrapingResult
BeautifulSoupScraper
UrlGuard contra SSRF
validacao deterministica
quality score
politicas de ACCEPT, FALLBACK e REJECT
limites individuais e globais
rotas HTTP
worker externo sem logica de negocio
```

O fluxo de coleta continua:

```txt
criar job
-> coletar pagina
-> validar conteudo
-> calcular scores
-> registrar tentativa
-> salvar resultado aprovado
-> concluir ou falhar o job
```

A principal mudanca esta na forma como esses dados sao armazenados e
recuperados.

---

## 4. Diferenca entre V1 e V2

### V1

```txt
Factory
-> repositorios em memoria compartilhados
-> dados desaparecem ao reiniciar o processo
```

### V2

```txt
Factory
-> cria uma Unit of Work por operacao
-> Unit of Work abre uma AsyncSession
-> repositorios PostgreSQL compartilham a sessao
-> commit confirma a transacao
-> dados permanecem depois que a aplicacao reinicia
```

Os repositorios em memoria continuam no projeto porque ainda sao uteis para
testes rapidos e exemplos isolados. Entretanto, eles nao sao mais utilizados
pela `ScrapingFactory` da aplicacao.

---

## 5. Arquitetura implementada

Fluxo atual:

```txt
Presentation
-> recebe e responde HTTP

Application
-> executa casos de uso e controla fronteiras transacionais por contrato

Domain
-> mantem entidades, estados, politicas e contratos de repositorio

Infrastructure
-> implementa PostgreSQL, SQLAlchemy, mappers e repositorios

Factory
-> conecta casos de uso, Unit of Work, PostgreSQL e pipeline
```

Fluxo concreto de uma requisicao:

```txt
Rota FastAPI
-> ScrapingFactory
-> Caso de uso
-> ScrapingUnitOfWork
-> PostgresScrapingUnitOfWork
-> repositorios PostgreSQL
-> mappers
-> models SQLAlchemy
-> PostgreSQL Docker
```

Regra preservada:

```txt
domain e application nao importam SQLAlchemy
```

Isso permite trocar a tecnologia de persistencia sem alterar as regras de
negocio do scraper.

---

## 6. Estrutura adicionada na V2

```txt
apps/api/src/database/relational/
|-- base.py
`-- session.py

apps/api/src/modules/scraping/
|-- application/
|   `-- unit_of_work.py
|
`-- infrastructure/database/
    |-- postgres_unit_of_work.py
    |-- models/
    |   |-- scraping_job_model.py
    |   |-- scraping_attempt_model.py
    |   `-- scraping_result_model.py
    |-- mappers/
    |   |-- scraping_job_mapper.py
    |   |-- scraping_attempt_mapper.py
    |   `-- scraping_result_mapper.py
    `-- repositories/
        |-- postgres_job_repository.py
        |-- postgres_attempt_repository.py
        `-- postgres_result_repository.py

apps/api/migrations/
|-- env.py
`-- versions/
    `-- 20260613_2137_f3f7f3959ccc_create_scraping_tables.py

infra/
`-- docker-compose.yml
```

---

## 7. Infraestrutura Docker

O arquivo `infra/docker-compose.yml` define:

```txt
PostgreSQL 16
Redis 7
Qdrant
```

Nesta V2, somente o PostgreSQL esta integrado ao fluxo do scraper.

Configuracao atual do PostgreSQL:

```txt
container: ai_radar_postgres
database: radar
usuario: postgres
porta interna: 5432
porta no host: 5433
volume: postgres_data
```

A porta `5433` no host evita conflitos com instalacoes locais do PostgreSQL na
porta padrao `5432`.

Subir somente o PostgreSQL:

```powershell
docker compose -f infra\docker-compose.yml up -d postgres
```

Verificar containers:

```powershell
docker compose -f infra\docker-compose.yml ps
```

Encerrar a infraestrutura:

```powershell
docker compose -f infra\docker-compose.yml down
```

O volume nomeado preserva os dados mesmo quando o container e encerrado.

---

## 8. Configuracao da conexao

A conexao e lida pelo `Settings`:

```txt
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/radar
```

Arquivos envolvidos:

```txt
.env
-> configuracao local e nao versionada

.env.example
-> exemplo seguro para novos ambientes

apps/api/src/config/settings.py
-> carrega as variaveis da aplicacao
```

Dependencias adicionadas:

```txt
sqlalchemy[asyncio]
asyncpg
alembic
```

---

## 9. Base, engine e sessoes

### Base declarativa

`apps/api/src/database/relational/base.py` define a `Base` compartilhada pelos
models SQLAlchemy.

Ela tambem define convencoes de nomes para:

```txt
indices
unique constraints
check constraints
foreign keys
primary keys
```

Nomes previsiveis facilitam migrations futuras com Alembic.

### Engine

`apps/api/src/database/relational/session.py` cria um engine assincrono.

```txt
engine
-> administra o pool de conexoes

AsyncSessionFactory
-> cria sessoes independentes por operacao
```

O engine usa `pool_pre_ping=True` para verificar conexoes antes de reutiliza-las.

As sessoes usam:

```txt
expire_on_commit=False
```

Assim, as entidades e models continuam acessiveis depois de um commit sem
precisar recarregar automaticamente todos os seus campos.

---

## 10. Tabelas implementadas

### scraping_jobs

Representa o ciclo completo de um job.

Campos:

```txt
id
url
status
error_message
created_at
started_at
finished_at
```

Indice:

```txt
status
```

### scraping_attempts

Registra cada estrategia tentada pela pipeline.

Campos:

```txt
id
job_id
method
status
decision
technical_score
text_score
evidence_score
quality_score
problems
warnings
error_message
started_at
finished_at
```

Caracteristicas:

```txt
job_id possui foreign key para scraping_jobs
exclusao do job remove tentativas com CASCADE
problems e warnings usam JSONB
scores opcionais permitem tentativas ainda em execucao ou com falha
```

Indices:

```txt
job_id
status
started_at
```

### scraping_results

Armazena somente conteudos aprovados.

Campos:

```txt
id
job_id
url
final_url
title
raw_html
raw_text
method
status_code
technical_score
text_score
evidence_score
quality_score
content_hash
metadata
created_at
```

Caracteristicas:

```txt
job_id e unico
cada job pode ter no maximo um resultado
exclusao do job remove o resultado com CASCADE
metadata usa JSONB
```

Indices:

```txt
job_id unico
content_hash
```

---

## 11. Restricoes no banco

O banco protege regras basicas mesmo se houver um erro na aplicacao.

Scores possuem `CHECK`:

```txt
0 <= score <= 1
```

O status HTTP possui `CHECK`:

```txt
100 <= status_code <= 599
```

Relacionamentos:

```txt
scraping_attempts.job_id
-> scraping_jobs.id

scraping_results.job_id
-> scraping_jobs.id
```

Ambos usam:

```txt
ON DELETE CASCADE
```

---

## 12. Decisao sobre result_id

A entidade de dominio `ScrapingJob` possui `result_id`, mas a tabela
`scraping_jobs` nao possui essa coluna.

O relacionamento real e:

```txt
scraping_results.job_id -> scraping_jobs.id
```

Ao consultar um job, o `PostgresScrapingJobRepository` procura o resultado pelo
`job_id` e reconstrui o `result_id` da entidade.

Motivo:

```txt
evitar duas foreign keys apontando uma para a outra
evitar duplicar a mesma relacao em duas tabelas
manter scraping_results.job_id como fonte da verdade
```

---

## 13. Models e entidades

As entidades do dominio e os models SQLAlchemy possuem responsabilidades
diferentes.

### Entidades

```txt
representam regras de negocio
controlam transicoes de estado
usam enums do dominio
nao conhecem SQLAlchemy
```

### Models

```txt
descrevem tabelas e colunas
definem indices e constraints
usam tipos PostgreSQL
nao substituem as entidades
```

Exemplo:

```txt
ScrapingJob
-> entidade de dominio

ScrapingJobModel
-> representacao da tabela scraping_jobs
```

---

## 14. Mappers

Os mappers traduzem explicitamente entre dominio e persistencia.

```txt
entidade -> mapper -> model SQLAlchemy
model SQLAlchemy -> mapper -> entidade
```

Mappers implementados:

```txt
ScrapingJobMapper
ScrapingAttemptMapper
ScrapingResultMapper
```

Responsabilidades:

```txt
converter enums para strings
reconstruir enums a partir das strings
copiar listas e dicionarios
preservar timestamps
atualizar models existentes
manter o dominio desacoplado do banco
```

Os mappers nao criam tabelas e nao executam consultas. Eles somente transformam
objetos.

---

## 15. Repositorios PostgreSQL

Repositorios implementados:

```txt
PostgresScrapingJobRepository
PostgresScrapingAttemptRepository
PostgresScrapingResultRepository
```

Cada repositorio recebe uma `AsyncSession`.

Os metodos `save`:

```txt
procuram o registro pelo ID
criam um model quando ele ainda nao existe
atualizam o model quando ele ja existe
executam flush
```

### Flush nao e commit

Os repositorios executam:

```txt
session.flush()
```

Eles nao executam:

```txt
session.commit()
```

O `flush` envia alteracoes ao banco dentro da transacao atual. O commit fica
sob responsabilidade da Unit of Work.

Isso permite confirmar varias alteracoes juntas:

```txt
salvar tentativa
salvar resultado
atualizar job
-> um unico commit
```

---

## 16. Unit of Work

A Unit of Work representa a fronteira de uma transacao.

Contrato:

```txt
ScrapingUnitOfWork
```

Implementacao:

```txt
PostgresScrapingUnitOfWork
```

Fluxo:

```python
async with unit_of_work_factory() as unit_of_work:
    await unit_of_work.job_repository.save(job)
    await unit_of_work.commit()
```

Ao entrar no contexto:

```txt
abre uma AsyncSession
cria os tres repositorios
entrega a mesma sessao aos repositorios
```

Ao sair:

```txt
desfaz alteracoes ainda pendentes
fecha a sessao
```

Beneficio principal:

```txt
ou todas as alteracoes da operacao sao confirmadas
ou alteracoes nao confirmadas sao desfeitas
```

A camada `application` depende apenas do contrato `ScrapingUnitOfWork`. Somente
a infraestrutura conhece `AsyncSession`.

---

## 17. Transacoes dos casos de uso

### CreateScrapingJob

Fluxo:

```txt
cria ScrapingJob pending
-> abre Unit of Work
-> salva job
-> commit
-> fecha Unit of Work
-> envia job_id ao dispatcher
```

O commit acontece antes do dispatch.

Motivo:

```txt
um worker usando outra sessao precisa encontrar o job no banco
```

### ExecuteScrapingJob

Fluxo:

```txt
abre Unit of Work
-> busca job
-> muda para running
-> commit
-> cria pipeline com o repositorio de tentativas da sessao atual
-> executa coleta e validacao
-> salva tentativas
-> salva resultado quando aprovado
-> atualiza job para completed ou failed
-> commit final
```

Existem dois commits intencionais.

Primeiro commit:

```txt
torna o estado running visivel durante a operacao demorada
```

Segundo commit:

```txt
confirma tentativas, resultado e estado final
```

Erros inesperados tambem salvam o job como `failed` antes de serem propagados.

### GetScrapingJob

```txt
abre Unit of Work
-> consulta job
-> consulta tentativas com a mesma sessao
-> fecha sem commit
```

### GetScrapingResult

```txt
abre Unit of Work
-> consulta resultado
-> fecha sem commit
```

Consultas nao executam commit porque nao alteram dados.

---

## 18. Factory atual

A `ScrapingFactory` e o ponto de composicao da aplicacao.

Ela conhece:

```txt
PostgresScrapingUnitOfWork
BeautifulSoupScraper
UrlGuard
BasicDeterministicValidator
QualityScoringService
politicas
LocalTaskDispatcher
```

Ela nao possui mais repositorios em memoria compartilhados.

Cada operacao recebe:

```txt
uma nova PostgresScrapingUnitOfWork
uma nova AsyncSession quando a Unit of Work abre
```

A pipeline e criada depois que a Unit of Work abre, porque ela precisa receber
o repositorio de tentativas associado a sessao atual.

---

## 19. Alembic e migrations

O Alembic controla a evolucao do schema.

Arquivos:

```txt
alembic.ini
apps/api/migrations/env.py
apps/api/migrations/versions/
```

O `env.py`:

```txt
le DATABASE_URL pelo Settings
importa Base.metadata
importa os models
usa engine assincrono
permite autogenerate
```

Migration inicial:

```txt
20260613_2137_f3f7f3959ccc_create_scraping_tables.py
```

Ela cria:

```txt
scraping_jobs
scraping_attempts
scraping_results
indices
foreign keys
check constraints
```

Aplicar migrations:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

Verificar versao atual:

```powershell
.\venv\Scripts\python.exe -m alembic current
```

Criar uma migration futura:

```powershell
.\venv\Scripts\python.exe -m alembic revision --autogenerate -m "descricao"
```

Antes de aplicar uma migration gerada automaticamente, seu conteudo deve ser
revisado.

---

## 20. Testes da persistencia

A V2 possui tres niveis importantes de teste.

### Testes unitarios

Validam isoladamente:

```txt
models
mappers
repositorios PostgreSQL com sessoes simuladas
dominio
pipeline
scraper
validator
seguranca
```

### Fluxo integrado em memoria

Arquivo:

```txt
test_scraping_flow.py
```

Valida a colaboracao da aplicacao sem depender do banco.

### Repositorios contra PostgreSQL real

Arquivo:

```txt
test_postgres_repositories.py
```

Valida:

```txt
persistencia dos tres repositorios
restauracao das entidades
relacionamentos
consulta por content_hash
```

### Factory contra PostgreSQL real

Arquivo:

```txt
test_postgres_factory_flow.py
```

Valida o fluxo real:

```txt
Factory
-> casos de uso
-> Unit of Work
-> repositorios
-> PostgreSQL
-> consulta do job
-> consulta do resultado
```

Somente a resposta HTTP e simulada. Factory, transacoes, repositorios e banco
sao reais.

Os testes que usam o engine global executam `engine.dispose()` ao final para
fechar as conexoes antes que o AnyIO encerre o event loop no Windows.

Executar a suite:

```powershell
.\venv\Scripts\python.exe -m pytest apps\api\src\modules\scraping\tests -q
```

Estado verificado:

```txt
60 passed
```

---

## 21. Como executar a V2

### 1. Criar o arquivo de ambiente

Use `.env.example` como referencia para criar o `.env` local.

### 2. Subir o PostgreSQL

```powershell
docker compose -f infra\docker-compose.yml up -d postgres
```

### 3. Aplicar migrations

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

### 4. Executar os testes

```powershell
.\venv\Scripts\python.exe -m pytest apps\api\src\modules\scraping\tests -q
```

### 5. Executar a API

```powershell
.\venv\Scripts\python.exe -m uvicorn apps.api.src.main:app --reload --port 8000
```

Documentacao interativa:

```txt
http://localhost:8000/docs
```

---

## 22. API disponivel

Endpoints:

```txt
POST /scraping/jobs
GET /scraping/jobs/{job_id}
GET /scraping/results/{result_id}
GET /health
```

Os endpoints agora consultam e persistem dados no PostgreSQL.

Exemplo:

```json
{
  "url": "https://example.com"
}
```

Apesar de persistir no PostgreSQL, o endpoint de criacao ainda espera a
execucao terminar porque o dispatcher atual continua local.

---

## 23. O que a V2 possibilita

A persistencia real resolve a principal limitacao arquitetural da V1.

Agora:

```txt
jobs sobrevivem a reinicios da API
API e worker podem acessar os mesmos dados
tentativas ficam disponiveis para auditoria
resultados aprovados podem ser consultados depois
migrations controlam a evolucao do schema
transacoes protegem alteracoes relacionadas
```

Isso prepara o sistema para separar a API do worker.

---

## 24. Limitacoes conhecidas

Persistencia PostgreSQL esta concluida, mas o scraper ainda nao esta pronto
para producao.

Limitacoes atuais:

```txt
LocalTaskDispatcher executa no processo da API
POST /scraping/jobs ainda espera o scraping terminar
Redis existe no Docker, mas nao esta conectado ao scraper
worker externo existe, mas ainda nao consome fila
somente BeautifulSoup esta implementado
nao existe fallback real para Playwright ou outra tecnologia
nao existe retry distribuido
nao existe observabilidade estruturada
nao existe validacao semantica com LLM
nao existe integracao com ingestion
deduplicacao por content_hash existe como consulta, mas nao como politica
```

Os repositorios em memoria continuam no codigo, mas sao usados apenas em
testes e cenarios isolados. A factory da aplicacao usa PostgreSQL.

---

## 25. Proximo passo prioritario

### Redis + Dramatiq

Objetivo:

```txt
executar scraping fora do processo da API
```

Fluxo desejado:

```txt
API
-> cria e confirma job pending no PostgreSQL
-> envia job_id ao Redis
-> responde imediatamente

Worker
-> recebe job_id
-> consulta o mesmo PostgreSQL
-> executa scraping
-> persiste tentativas, resultado e estado final
```

Entregaveis:

```txt
adicionar Dramatiq
configurar broker Redis
criar DramatiqTaskDispatcher
registrar a task do worker
executar processo worker separado
configurar retries controlados
testar API e worker em processos separados
```

A ordem `commit antes do dispatch`, implementada nesta V2, ja prepara o caso de
uso para esse fluxo.

---

## 26. Proximos passos posteriores

Depois da fila e do worker separado:

### Playwright

```txt
implementar fallback para paginas dependentes de JavaScript
```

### Validacao deterministica melhorada

```txt
detectar boilerplate
medir proporcao de links
detectar idioma
calibrar thresholds com exemplos reais
```

### Trafilatura

```txt
melhorar extracao de artigos, noticias e blogs
```

### Deduplicacao

```txt
usar content_hash como politica antes de aceitar ou processar resultados
```

### Validacao semantica

```txt
usar LLM apenas para casos ambiguos
```

### Integracao com ingestion

```txt
entregar resultados brutos aprovados por um contrato publico
```

---

## 27. Criterio de conclusao da V2

A V2 pode ser considerada concluida porque demonstra:

```txt
PostgreSQL real em Docker
schema versionado com Alembic
SQLAlchemy assincrono
models separados das entidades
mappers explicitos
repositorios PostgreSQL
transacoes com Unit of Work
casos de uso independentes de SQLAlchemy
factory configurada com persistencia real
testes contra o banco real
fluxo completo da factory validado
```

Resumo:

```txt
V1 provou o comportamento do scraper.
V2 tornou o estado do scraper duravel e compartilhavel.
V3 devera separar a execucao usando Redis e worker.
```

