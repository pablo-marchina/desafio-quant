# Startups V2 — Campos Estruturados (founders/funding/customers)

Esta versao adiciona founders, funding (estagio + valor) e customers ao
`Startup`. Desbloqueia o Extraction Agent (Agents V8), que precisa de um
destino para persistir o que extrai das evidencias.

## 1. Objetivo

```txt
empresa + evidencias -> founders, funding_stage, funding_amount_usd, customers
```

## 2. Decisoes de design

- **`funding_stage` e enum fechado** (`PRE_SEED/SEED/SERIES_A/SERIES_B/
  SERIES_C_PLUS/UNKNOWN`), nao texto livre — vai ser preenchido por LLM
  (Extraction Agent), e um enum garante saida estruturada validavel
  (regra 9 do CLAUDE.md) em vez de variacoes tipo "Series A" vs
  "series-a".
- **`founders`/`customers` sao `list[str]` simples** (nomes), nao
  sub-entidades com campos extras (cargo, LinkedIn, etc.) — sem
  consumidor concreto pedindo isso ainda (regra 8: nao construir para
  hipotese futura). JSONB, mesmo padrao de `Recommendation.matched_keywords`.
- **Nao entram em `CreateStartupInput`**, so em `UpdateStartupInput` —
  mesmo padrao de `ai_maturity_level` (Startups V3), que tambem so e
  setado depois da criacao.
- **JSONB NOT NULL com default `[]`** para as listas (nunca `None`,
  sempre lista, eventualmente vazia); `funding_stage`/
  `funding_amount_usd` ficam nullable (genuinamente desconhecidos até
  extraidos).

## 3. Entregue

- Enum `FundingStage` (`domain/enums.py`).
- `Startup.update()` estendido com os 4 parametros novos; validacao de
  `funding_amount_usd` negativo.
- `UpdateStartupInput`/`StartupView` com os 4 campos.
- Migration `f77998c46d08`: `ALTER TABLE startups` (4 colunas).
- `PATCH /startups/{id}` aceita os 4 campos novos; `GET /startups/{id}`
  devolve.

## 4. Validacao

Testes novos:

```txt
test_startup_entities.py (+4)         update() com campos novos,
                                       funding_amount_usd negativo (na
                                       criacao e no update), defaults
test_startup_use_cases.py (+1)        UpdateStartup repassa os campos novos
test_postgres_startup_repositories.py estendido com round-trip dos 4
                                       campos novos
```

Total apos esta entrega (modulo `startups`): 24 unit + 1 integracao.

## 5. Limites conhecidos

```txt
founders/customers sao so nomes (string) - sem estrutura adicional
  (cargo, contato, etc.)

funding_amount_usd e um unico valor em USD - sem moeda explicita nem
  historico de rounds anteriores

sem preenchimento automatico ainda - Extraction Agent (proximo passo) e
  quem vai popular esses campos a partir de evidencias
```

## 6. Proximo passo

```txt
Extraction Agent (Agents V8) - agora desbloqueado por este V2
```
