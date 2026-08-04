# Scraper V5 - Validacao Deterministica e Deduplicacao

## 1. Objetivo

A V5 melhora a decisao sobre a qualidade do conteudo coletado.

```txt
reduzir falsos positivos
reduzir falsos negativos
explicar por que uma pagina foi aceita, rejeitada ou enviada para fallback
impedir persistencia repetida do mesmo conteudo
```

Esta versao conclui o Passo 4 descrito em `scraper_v1.md`.

---

## 2. Fluxo atual

```txt
scraper produz ScrapingOutput
-> validacao tecnica
-> validacao textual
-> validacao evidencial
-> calculo do quality_score
-> politica decide ACCEPT, FALLBACK ou REJECT
-> conteudo aceito passa pela deduplicacao
-> PostgreSQL persiste somente conteudo novo
```

Os validadores nao consultam banco e nao controlam o job. Eles apenas medem e
devolvem sinais objetivos.

---

## 3. Validadores especializados

### TechnicalValidator

Avalia se a coleta e tecnicamente utilizavel:

```txt
status HTTP
content-type
HTML vazio
captcha
URL de origem
redirect
pagina dependente de JavaScript
```

Uma pagina com shell vazio, como `<div id="root"></div>`, recebe o problema:

```txt
javascript_required
```

Isso permite fallback de BeautifulSoup para Playwright.

### TextualValidator

Avalia a qualidade e a estrutura do texto:

```txt
quantidade de caracteres
quantidade de palavras
repeticao
boilerplate
proporcao de links
idioma provavel
```

Limites calibrados:

```txt
texto minimo = 300 caracteres
texto considerado bom = 800 caracteres
minimo = 80 palavras

boilerplate elevado = 35%
boilerplate critico = 60%

links elevados = 50%
link farm = 70%
```

Entre `50%` e `70%`, a pagina recebe o warning `high_link_ratio`.

A partir de `70%`, recebe tambem o problema bloqueador `link_farm`.

### EvidenceValidator

Procura sinais objetivos relacionados ao objetivo do AI Venture Radar:

```txt
termos de IA
termos de produto ou servico
descricao de capacidade
titulo da pagina
```

Uma mencao isolada a IA nao e suficiente para produzir evidencia forte.

---

## 4. Score e decisao

Formula preservada:

```txt
quality_score =
    technical_score * 0.30
    + text_score * 0.30
    + evidence_score * 0.40
```

Para aceitar, o conteudo precisa:

```txt
quality_score >= 0.75
e
nenhum problema bloqueador
```

Problemas bloqueadores atuais:

```txt
blocked_status
captcha
empty_content
high_boilerplate
insufficient_text
javascript_required
link_farm
missing_source_url
unsupported_content_type
```

Essa regra impede que um score alto esconda um defeito estrutural grave.

`high_repetition` permanece como problema auditavel e reduz o score textual,
mas nao bloqueia sozinho. Paginas reais podem repetir chamadas comerciais,
nomes de produto e elementos visuais sem serem necessariamente invalidas.

---

## 5. Cenarios de calibracao

A calibracao usa perfis representativos de paginas reais, sem depender da rede
durante os testes:

| Perfil | Decisao esperada | Motivo |
|---|---|---|
| landing page detalhada de produto de IA | ACCEPT | texto, produto e capacidade claros |
| artigo geral que apenas menciona IA | REJECT | evidencia insuficiente sobre produto |
| diretorio dominado por links e palavras-chave | REJECT | `link_farm` |
| shell HTML dependente de JavaScript | FALLBACK | `javascript_required` |
| pagina curta | FALLBACK | `insufficient_text` |

Esses cenarios ficam em:

```txt
apps/api/src/modules/scraping/tests/unit/test_validation_calibration.py
```

Ao alterar thresholds ou pesos, esses testes mostram se a mudanca melhora um
caso sem degradar os demais.

---

## 6. Deduplicacao

Depois que a validacao aceita o conteudo, o
`ContentDeduplicationService` procura outro resultado com o mesmo
`content_hash`.

```txt
hash novo
-> salva resultado

hash existente
-> nao salva segundo resultado
-> job termina como FAILED com referencia ao resultado original
```

O servico depende apenas de `ScrapingResultRepository`, portanto funciona com
repositorios em memoria e PostgreSQL.

---

## 7. Protecao contra concorrencia

A consulta previa nao e suficiente quando dois workers processam o mesmo
conteudo simultaneamente:

```txt
worker A consulta -> nao encontrou
worker B consulta -> nao encontrou
worker A salva
worker B tenta salvar
```

Por isso, `scraping_results.content_hash` possui indice unico no PostgreSQL.

O repositorio PostgreSQL usa um savepoint para traduzir a colisao em
`DuplicateScrapingContentError` sem inutilizar a transacao externa.

Migration:

```txt
a41c96d32e57_make_content_hash_unique
```

---

## 8. Arquivos principais

```txt
application/content_deduplication_service.py
infrastructure/validators/technical_validator.py
infrastructure/validators/textual_validator.py
infrastructure/validators/evidence_validator.py
infrastructure/validators/composite_deterministic_validator.py
domain/policies.py
infrastructure/database/repositories/postgres_result_repository.py
```

---

## 9. Limitacoes conhecidas

```txt
idioma detectado apenas por heuristica simples
thresholds calibrados com poucos perfis representativos
evidencia baseada em palavras-chave, sem compreensao semantica
duplicidade usa igualdade exata do texto normalizado pelo scraper
conteudos quase iguais ainda produzem hashes diferentes
job duplicado usa status FAILED; ainda nao existe status DUPLICATE
```

---

## 10. Proximo passo

O proximo passo recomendado no plano original e a V6 com Trafilatura.

Objetivo:

```txt
melhorar a extracao de artigos, noticias e blogs
reduzir boilerplate antes da validacao
comparar a qualidade das estrategias
```

Depois disso:

```txt
validacao semantica com LLM para casos ambiguos
agentes para investigacao em multiplas fontes
integracao com ingestion e banco vetorial
```

---

## 11. Criterio de conclusao da V5

A V5 esta concluida quando:

```txt
validadores tecnico, textual e evidencial estao separados
boilerplate, links, idioma e JavaScript sao detectados
problemas graves bloqueiam aceitacao
thresholds possuem cenarios de calibracao
duplicidade normal e concorrente e impedida
comportamento esta documentado e coberto por testes
```
