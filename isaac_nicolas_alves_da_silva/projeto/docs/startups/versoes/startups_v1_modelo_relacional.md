# Startups V1 - Modelo Relacional Basico

Esta versao cria o modulo `startups`, responsavel por organizar empresas e
evidencias aprovadas em uma base relacional consultavel.

## 1. Objetivo

```txt
startup -> evidencias aprovadas
```

O modulo nao faz scraping, ingestion, embeddings ou recomendacao. Ele apenas
cria a representacao estruturada que sera consumida por RAG, classificacao e
recommendations.

## 2. Modelo

`Startup`:

```txt
id
name
website_url
description
sector
country
created_at
updated_at
```

`StartupEvidence`:

```txt
id
startup_id
scraping_result_id
source_url
evidence_type
title
confidence_score
notes
created_at
```

`startup_evidences.scraping_result_id` referencia `scraping_results.id`, ou
seja, a evidencia associada deve vir da camada de scraping validada.

## 3. Casos de Uso

```txt
CreateStartup
GetStartup
UpdateStartup
AddStartupEvidence
ListStartupEvidences
```

## 4. API

```txt
POST   /startups
GET    /startups?page=1&page_size=20&query=&sector=&country=&ai_maturity_level=
GET    /startups/{startup_id}
PATCH  /startups/{startup_id}
POST   /startups/{startup_id}/evidences
GET    /startups/{startup_id}/evidences
```

## 5. Validacao

Testes unitarios:

```txt
test_startup_entities.py
test_startup_use_cases.py
```

Teste de persistencia:

```txt
test_postgres_startup_repositories.py
```

Validacao executada no ambiente atual:

```txt
285 testes unitarios passando
```

O teste de persistencia foi adicionado, mas depende de PostgreSQL local com
migrations aplicadas, como os demais testes de integracao do projeto.

## 6. Proximo Passo

```txt
Startups V2 - Consolidacao de Evidencias
```

V2 deve deduplicar startups por nome/site e associar multiplas fontes a uma
mesma empresa automaticamente.
