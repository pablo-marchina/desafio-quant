# Documentação Técnica — `descobre_imprensa.py`

## Visão Geral

O `descobre_imprensa.py` é um módulo de coleta de sinais de IA do projeto. Sua responsabilidade é buscar, em três APIs de notícias distintas, artigos da imprensa brasileira que comprovem que cada empresa monitorada utiliza, adotou ou está relacionada a Inteligência Artificial.

Para cada empresa cadastrada no banco, o módulo constrói uma query booleana que combina o nome da empresa com termos de IA e ação empresarial, consulta as APIs em cascata e aplica um filtro local em cinco camadas sobre os artigos retornados. O resultado — encontrou ou não encontrou notícias relevantes — é registrado na tabela `sinais_ia` do Supabase com a camada identificada como `imprensa`, e também persistido localmente em arquivo JSON para consulta e auditoria.

---

## Posição no Pipeline

```
Supabase (tabela empresas)
    → descobre_imprensa.py     [busca em APIs de notícias + filtro local]
        → Supabase (tabela sinais_ia, camada "imprensa")
        → data/jsons/imprensa/noticias_encontradas.json
```

O módulo é uma das quatro camadas de detecção de sinais de IA do projeto:

| Camada | Script | Fonte |
|---|---|---|
| `institucional` | `descobre_institucional.py` | Site oficial da empresa |
| `imprensa` | **este script** | Notícias na internet |
| `gupy_vagas` | `descobre_gupy_vagas.py` | Vagas de emprego no Gupy |
| `neofeed` | `analisa_neofeed.py` | Notícias do portal NeoFeed |

---

## Tecnologias Utilizadas

### Linguagem

**Python 3.9+**
A anotação `str | None` e o uso de `from __future__ import annotations` requerem Python moderno. O `__future__` ativa avaliação lazy de type hints, permitindo anotações de tipo sem erro de runtime em versões anteriores ao 3.10.

---

### Biblioteca padrão do Python

| Módulo | Uso no código |
|---|---|
| `json` | Leitura do arquivo JSON de cache existente e escrita incremental dos novos registros |
| `os` | Acesso às variáveis de ambiente com as chaves das APIs e do Supabase |
| `re` | Compilação e execução de expressões regulares para detectar sinais de IA e o nome da empresa nos artigos |
| `datetime` / `timezone` | Registro do timestamp UTC exato no momento da coleta de cada registro |
| `pathlib.Path` | Manipulação de caminhos de arquivo de forma orientada a objetos e multiplataforma |
| `urllib.parse.urlparse` | Extração do domínio (`netloc`) de cada URL de artigo para aplicação dos filtros de domínio |

**Sobre o módulo `re` (regex):**
O módulo `re` implementa **expressões regulares** — um mecanismo de busca textual por padrões, em vez de palavras exatas. Neste script, ele é utilizado em três contextos distintos: (1) `_SINAL_IA_COMPOSTO` — detecta termos compostos de IA como `inteligência artificial`, `machine learning`, `chatbot` e outros, compilado com a flag `re.IGNORECASE`; (2) `_SINAL_IA_SIGLA` — detecta a sigla `IA` em maiúsculo, compilado **sem** `re.IGNORECASE` para não confundir com o verbo "ia" do português; (3) `padrao_nome` — verifica se o nome da empresa aparece no título do artigo usando word boundaries (`\b`), impedindo que um nome curto como "IA" dê match dentro de outra palavra. As compilações são feitas uma única vez no momento de carregamento do módulo, o que é mais eficiente do que recompilar a cada artigo processado.

---

### Bibliotecas de terceiros

#### `requests`
Biblioteca HTTP para Python, utilizada para realizar as requisições GET às três APIs de notícias. O script define um timeout fixo de 10 segundos por chamada para evitar que uma API lenta bloqueie indefinidamente a execução.

#### `python-dotenv`
Carrega variáveis de ambiente a partir do arquivo `.env` localizado na raiz do projeto. Provê as quatro credenciais necessárias sem expô-las no código-fonte: `SUPABASE_URL`, `SUPABASE_KEY`, `NEWS_API_KEY`, e as chaves opcionais dos fallbacks `NEWS_DATA_KEY` e `GNNEWS_API_KEY`.

#### `supabase-py`
Cliente Python oficial do **Supabase** (banco de dados PostgreSQL gerenciado na nuvem). Utilizado em dois momentos: para **ler** a lista de empresas a processar (tabela `empresas`) e para **gravar** os sinais detectados (tabela `sinais_ia`).

---

### APIs de notícias (serviços externos)

O script opera com três APIs de notícias dispostas em cascata. Cada uma possui chave própria e é acionada somente quando a anterior falha ou esgota sua cota.

| API | Papel | Variável de ambiente | Observação |
|---|---|---|---|
| **newsapi.org** | Fonte primária | `NEWS_API_KEY` | Suporta query booleana completa com `OR`/`AND`/aspas |
| **newsdata.io** | Fallback 1 | `NEWS_DATA_KEY` | Plano gratuito não suporta operadores booleanos; usa query simplificada |
| **gnews.io** | Fallback 2 | `GNNEWS_API_KEY` | Suporta alternativas com `OR`; restringe por país e idioma |

---

## Funcionamento Detalhado

### 1. Inicialização

O módulo resolve a raiz do projeto subindo três níveis a partir de sua localização (`Path(__file__).resolve().parent.parent.parent`) e carrega as variáveis de ambiente do `.env`. Em seguida, instancia o cliente Supabase e define todas as constantes de configuração: a query booleana, a lista de domínios permitidos, a lista de domínios bloqueados, os padrões regex e a variável de flag de sessão `_news_api_esgotada`.

### 2. Query booleana

A query enviada às APIs é construída em dois blocos conectados por `AND`:

**Bloco de ação/produto e investimento:**
```
(implementou OR lançou OR integrou OR desenvolveu OR automatizou
 OR "com IA" OR "assistente virtual" OR chatbot OR copilot
 OR aporte OR rodada OR captou OR investimento OR "Series A" OR seed)
```

**Bloco de tecnologia de IA:**
```
("inteligência artificial" OR "machine learning" OR "IA generativa"
 OR "modelo de linguagem" OR GPT OR LLM OR IA)
```

Na chamada real, o nome da empresa é prefixado com aspas: `"Nome da Empresa" AND (bloco_ação) AND (bloco_ia)`. Isso garante que o nome apareça exatamente como cadastrado e que o artigo trate tanto de uma ação concreta quanto de uma tecnologia de IA específica.

O filtro de domínio (`domains=...`) **não é passado à API de forma intencional**: restringir os domínios no lado do servidor eliminaria artigos válidos antes que o filtro local de qualidade pudesse avaliá-los. A estratégia adotada é buscar com amplitude e filtrar com precisão localmente.

### 3. Flag de sessão `_news_api_esgotada`

Uma variável global em nível de módulo controla se a newsapi.org deve ser tentada. Quando ela retorna HTTP 429 (cota diária esgotada), a flag é ativada e **todas as chamadas subsequentes na mesma execução** já partem diretamente para os fallbacks, sem nem tentar a API primária. Isso evita consumir tentativas restantes depois que a cota acabou.

### 4. Busca no Supabase e loop principal — `pesquisar()`

**Consulta inicial:** o módulo busca na tabela `empresas` os campos `id` e `nome` de todos os registros. O parâmetro opcional `nome` permite filtrar para uma única empresa durante testes.

**Para cada empresa:**

1. Chama `_ja_checado(empresa_id)` — se já existe qualquer registro com `camada = "imprensa"` no Supabase para essa empresa, ela é pulada completamente.
2. Chama `_buscar(nome_empresa)` — executa o cascade de APIs descrito na seção seguinte.
3. Chama `_filtrar(artigos, nome_empresa)` — aplica os cinco filtros locais de qualidade.
4. Persiste o resultado no Supabase e acumula na lista local.

### 5. Persistência em JSON — `_salvar_json()`

Ao final do loop, o módulo grava os resultados em `data/jsons/imprensa/noticias_encontradas.json`. A escrita é **incremental com deduplicação por URL**: se o arquivo já existir, o módulo carrega os registros anteriores, constrói um conjunto (`set`) com todas as `fonte_url` já presentes e adiciona somente os registros cujas URLs ainda não foram vistas.

---

## Cascade de APIs de Notícias

A busca opera em cascata. Cada API só é acionada se a anterior falhar ou tiver sua cota esgotada.

```
Primária: newsapi.org (query booleana completa, idioma pt)
    ↓ erro 429 / erro 5xx / timeout / resposta inválida
Fallback 1: newsdata.io (query simplificada, country=br)
    ↓ erro 429 / erro 5xx / timeout / resposta inválida / lista vazia
Fallback 2: gnews.io (query com OR, lang=pt, country=br)
```

**newsapi.org (primária):**
Envia a query booleana completa via parâmetro `q`, com `language=pt`, `sortBy=relevancy` e `pageSize=10`. Trata explicitamente: `429` → ativa a flag `_news_api_esgotada` e aciona fallback permanente para a execução inteira; `5xx` → tenta fallback pontualmente nesta empresa; timeout de 10 s → tenta fallback; resposta não-JSON → tenta fallback; campo `status != "ok"` → tenta fallback; campo `articles` ausente ou não é lista → tenta fallback.

**newsdata.io (fallback 1):**
O plano gratuito não suporta operadores `OR` ou parênteses na query. A query enviada é simplificada: `"Nome da Empresa" inteligência artificial` — os dois termos funcionam como `AND` implícito. Restringe ao país Brasil com `country=br`. Os campos da resposta são normalizados para o mesmo formato da newsapi (`link` → `url`, `pubDate` → `publishedAt`).

O newsdata.io é o primeiro fallback por uma razão prática de cota: o plano gratuito oferece **200 créditos/dia** (1 crédito por requisição), o dobro dos 100 disponíveis no gnews.io. Como o script faz uma requisição por empresa, isso significa que o newsdata.io consegue cobrir o dobro de empresas antes de esgotar — o que é exatamente o que se quer de um primeiro fallback: durar o máximo possível antes de precisar acionar a reserva final.

**gnews.io (fallback 2):**
Suporta alternativas com `OR` entre aspas. A query enviada é: `"Nome" ("inteligência artificial" OR "machine learning" OR "IA generativa" OR "chatbot" OR "automação inteligente" OR "LLM")`. Restringe com `lang=pt` e `country=br`. O campo da resposta já usa `url` e `publishedAt`, compatíveis com o formato padrão. Erros `401`, `403` e `429` desativam o GNews para o restante da execução.

---

## Filtro de Qualidade Local — Cinco Camadas

Todo artigo retornado por qualquer API passa pelo filtro local antes de ser considerado relevante. Os filtros são aplicados em ordem de custo crescente de processamento:

```
Camada 1: Schema válido
    ↓ passou
Camada 2: Domínio não bloqueado
    ↓ passou
Camada 3: Domínio brasileiro (lista de veículos permitidos)
    ↓ passou
Camada 4: Nome da empresa no título
    ↓ passou
Camada 5: Sinal explícito de IA no título ou descrição
```

### Camada 1 — Schema válido (`_artigo_valido`)

Verifica a estrutura mínima antes de qualquer processamento:
- A URL começa com `http`
- O título existe e tem pelo menos 10 caracteres
- Elimina placeholders da newsapi: título `[Removed]` ou URL `https://removed.com` — artigos pagos ou removidos que a API continua listando como fantasmas

### Camada 2 — Domínio não bloqueado (`_dominio_bloqueado`)

Remove fontes sabidamente irrelevantes para o contexto do projeto:

| Categoria | Domínios |
|---|---|
| Acadêmico / científico | `nature.com`, `arxiv.org`, `pubmed.ncbi.nlm.nih.gov`, `sciencedirect.com`, `springer.com`, `wiley.com`, `researchgate.net`, `semanticscholar.org` |
| Irrelevante para o contexto | `highsnobiety.com`, `naturalnews.com` |

### Camada 3 — Domínio brasileiro

Aceita **somente** os 19 veículos da lista explícita `_DOMINIOS_BR_SET`. Qualquer URL fora dessa lista é descartada — inclusive veículos internacionais válidos como TechCrunch ou Reuters.

| Veículo | Domínio |
|---|---|
| Valor Econômico | `valor.globo.com` |
| Exame | `exame.com` |
| Startups.com.br | `startups.com.br` |
| NeoFeed | `neofeed.com` |
| Folha de S.Paulo | `folha.uol.com.br` |
| Estadão | `estadao.com.br` |
| InfoMoney | `infomoney.com.br` |
| TecMundo | `tecmundo.com.br` |
| Olhar Digital | `olhardigital.com.br` |
| Canarinho.vc | `canarinho.vc` |
| Forbes Brasil | `forbes.com.br` |
| Pequenas Empresas & Grandes Negócios | `pegn.globo.com` / `revistapegn.globo.com` |
| Época Negócios | `epocanegocios.globo.com` |
| Brazil Journal | `braziljournal.com` |
| Silicon Valley Brasil | `siliconvalleybrasil.com.br` |
| CanalTech | `canaltech.com.br` |
| Computer World | `computerworld.com.br` |
| Startupi | `startupi.com.br` |

### Camada 4 — Nome da empresa no título

Verifica se o nome da empresa aparece **no título** usando um padrão regex com word boundary: `re.compile(r'\b' + re.escape(nome.lower()) + r'\b')`. O `re.escape` protege caracteres especiais que alguns nomes possam conter. O word boundary `\b` impede que um nome curto dê match dentro de outra palavra (ex.: "IA" não deveria casar dentro de "viagem").

O critério é intencional: o artigo precisa ser **sobre** a empresa, não apenas mencioná-la de passagem no corpo do texto.

### Camada 5 — Sinal explícito de IA no título ou descrição

Exige que o artigo trate concretamente de IA, não apenas que a query server-side tenha retornado um match no corpo. Dois padrões complementares são aplicados sobre a concatenação de título e descrição:

**`_SINAL_IA_COMPOSTO`** (case-insensitive):
Detecta termos compostos: `inteligência artificial`, `machine learning`, `ia generativa`, `modelo de linguagem`, `gpt`, `llm`, `chatbot`, `copilot`, `automação inteligente`, `assistente virtual`, `deep learning`, `rede neural`.

**`_SINAL_IA_SIGLA`** (case-sensitive, `\bIA\b`):
Detecta a sigla em maiúsculo. Este padrão é deliberadamente **separado e case-sensitive** porque pesquisar `ia` em lowercase confundiria com o verbo "ia" do português ("a empresa ia ao mercado").

Ao final das cinco camadas, o resultado é truncado para no máximo **5 artigos por empresa** (`_MAX_ARTIGOS_POR_EMPRESA = 5`).

---

## Estrutura dos Dados de Saída

Cada registro no arquivo JSON e na tabela `sinais_ia` segue o formato abaixo.

**Registro com sinal positivo (notícia de IA encontrada):**

```json
{
  "empresa_id": 12,
  "nome_empresa": "Kenoby",
  "evidencia": "Kenoby lança assistente virtual com IA generativa para triagem de candidatos — A plataforma integrou LLM ao fluxo de recrutamento automatizado.",
  "fonte_url": "https://startups.com.br/kenoby-lanca-assistente-virtual-ia",
  "publicado_em": "2024-11-03T14:00:00Z",
  "encontrado": true,
  "coletado_em": "2026-06-30T10:42:17.308+00:00"
}
```

**Registro com sinal negativo (empresa verificada, sem notícia de IA):**

```json
{
  "empresa_id": 27,
  "nome_empresa": "Conta Simples",
  "evidencia": null,
  "fonte_url": null,
  "publicado_em": null,
  "encontrado": false,
  "coletado_em": "2026-06-30T10:43:05.112+00:00"
}
```

| Campo | Descrição |
|---|---|
| `empresa_id` | Chave estrangeira referenciando a tabela `empresas` no Supabase |
| `nome_empresa` | Nome da empresa conforme cadastrado no Supabase |
| `evidencia` | Título + " — " + descrição do artigo; `null` em registros negativos |
| `fonte_url` | URL completa do artigo; `null` em registros negativos |
| `publicado_em` | Data de publicação original do artigo conforme retornada pela API (`publishedAt`); `null` em registros negativos |
| `encontrado` | `true` se ao menos um artigo passou pelos cinco filtros; `false` se a empresa foi verificada sem resultado |
| `coletado_em` | Timestamp UTC do momento da coleta no formato ISO 8601 |

---

## Pontos de Atenção

**Lista de veículos brasileiros definida estaticamente**
Os 19 domínios aceitos pela camada 3 são uma lista fixa no código. Novos veículos de qualidade que surjam ou que passem a cobrir startups brasileiras de IA precisam ser adicionados manualmente à constante `_DOMINIOS_BR_SET` para serem considerados.

**Cotas diárias das APIs**
A newsapi.org no plano gratuito permite aproximadamente 100 requisições por dia. Em execuções com muitas empresas, é possível esgotar a cota antes de processar todas. Os fallbacks têm cotas ainda menores, e o plano gratuito do newsdata.io não suporta query booleana completa — o que reduz a precisão dos resultados quando ele é acionado.

**Query simplificada no fallback newsdata.io**
Por limitação do plano gratuito, a query enviada ao newsdata.io é `"Nome da Empresa" inteligência artificial`, sem os operadores de aporte, rodada ou investimento do bloco primário. Artigos sobre adoção de IA que não mencionem explicitamente `inteligência artificial` no texto podem não ser retornados por esse fallback.

**Cobertura restrita à imprensa nacional listada**
A camada 3 exclui toda fonte fora da lista de 19 veículos. Cobertura internacional (ex.: TechCrunch cobrindo uma startup brasileira) e portais nacionais não listados são descartados independentemente do artigo.

**Empresa verificada não é reverificada automaticamente**
`_ja_checado()` verifica se existe **qualquer** registro na tabela `sinais_ia` com `camada = "imprensa"` para a empresa, independentemente de quando foi feito. Uma empresa que recebeu `encontrado=False` há meses não será reprocessada em execuções futuras, mesmo que tenha lançado novos produtos de IA nesse intervalo.

**Ausência de janela temporal na query**
A query não impõe filtro de data. Artigos antigos sobre IA de uma empresa podem ser retornados e registrados como evidência, sem distinção de quão recente é a cobertura.

**Nome da empresa deve aparecer no título**
A camada 4 exige que o nome da empresa esteja no título do artigo, não apenas no corpo. Cobertura de imprensa que mencione a empresa apenas no subtítulo, na legenda ou no decorrer do texto não passa por esse filtro.