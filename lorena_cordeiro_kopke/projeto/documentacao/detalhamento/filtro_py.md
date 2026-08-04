# Documentação Técnica — `filtro.py`

## Visão Geral

O `filtro.py` é o segundo módulo do pipeline de coleta de dados do projeto. Sua responsabilidade é processar os artigos brutos coletados pelo `coleta_neofeed.py` e extrair, de forma estruturada, os nomes das startups que são sujeito principal de cada notícia.

O módulo aplica um pipeline de extração em três camadas de decrescente sofisticação, combinando inteligência artificial generativa, processamento de linguagem natural e heurísticas linguísticas baseadas em regex. Ao final, os dados validados são persistidos em arquivo JSON e consultados em relação ao banco de dados Supabase para evitar reprocessamento.

Para a extração via IA, o `filtro.py` chama diretamente o arquivo `src/agents/extrato_nomes_startups_gemini.py`, importando dele a função `extrair_nome_gemini`. Essa separação isola a lógica de comunicação com a API Gemini em um módulo dedicado.

---

## Posição no Pipeline

```
NeoFeed (site)
    → coleta_neofeed.py     [raspagem de artigos brutos]
        → artigos_brutos.json
            → filtro.py     [extração de nomes + validação]
                → nomes_empresas.json
                → Supabase (tabela nomes_empresas)
```

---

## Tecnologias Utilizadas

### Linguagem

**Python 3.10+**
A anotação `str | None` e o uso de `from __future__ import annotations` requerem Python moderno. O `__future__` ativa avaliação lazy de type hints, permitindo anotações de tipo sem erro de runtime em versões anteriores ao 3.10.

---

### Biblioteca padrão do Python

| Módulo | Uso no código |
|---|---|
| `json` | Leitura do JSON de entrada e escrita do JSON de saída |
| `os` | Acesso às variáveis de ambiente `SUPABASE_URL` e `SUPABASE_KEY` |
| `re` | Compilação e execução de expressões regulares para o fallback de extração por verbo |
| `sys` | Leitura de argumentos de linha de comando via `sys.argv` |
| `time` | Pausas entre chamadas à API Gemini para respeitar o rate limit |
| `pathlib.Path` | Manipulação de caminhos de arquivo de forma orientada a objetos e multiplataforma |

**Sobre o módulo `re` (regex):**
`re` é o módulo Python que implementa **expressões regulares** — um mecanismo de busca textual por padrões, em vez de palavras exatas. No `filtro.py`, ele compila uma única expressão que agrupa todos os verbos de ação empresarial em português e detecta onde o predicado começa no título da notícia. A compilação prévia via `re.compile()` é feita uma única vez na inicialização do módulo, o que é mais eficiente do que recompilar o padrão a cada artigo processado.

---

### Bibliotecas de terceiros

#### `python-dotenv`
Carrega variáveis de ambiente a partir do arquivo `.env` localizado na raiz do projeto. Provê as credenciais necessárias para conexão com o Supabase e a API Gemini sem expô-las no código-fonte.

#### `spaCy` com modelo `pt_core_news_sm`
**spaCy** é uma biblioteca de Processamento de Linguagem Natural (PLN) de uso industrial. O modelo `pt_core_news_sm` é um modelo pré-treinado em **português**, capaz de realizar NER (*Named Entity Recognition* — Reconhecimento de Entidades Nomeadas): análise de texto para identificar e classificar entidades como `ORG` (organizações), `PER` (pessoas), `LOC` (locais), entre outras. No pipeline, o spaCy atua como **primeiro fallback**: quando a API Gemini não retorna um resultado, o modelo tenta identificar entidades do tipo `ORG` no título do artigo.

#### `supabase-py`
Cliente Python oficial do **Supabase** (banco de dados PostgreSQL gerenciado). Utilizado para consultar, antes do processamento, quais URLs já foram persistidas na tabela `nomes_empresas`, evitando reprocessamento de artigos já tratados.

#### `google-genai` — via `src/agents/extrato_nomes_startups_gemini.py`
SDK oficial da Google para acesso à API Gemini. O `filtro.py` importa a função `extrair_nome_gemini` diretamente do arquivo `src/agents/extrato_nomes_startups_gemini.py`, que encapsula toda a lógica de comunicação com a API. O modelo utilizado é o **`gemini-flash-lite-latest`**, versão otimizada para velocidade e custo. As chamadas utilizam **JSON estruturado com schema declarado** (`response_schema`), forçando a API a retornar sempre uma resposta no formato `{"startup": "Nome"}` ou `{"startup": null}`. O módulo implementa retry com **backoff exponencial** para erros HTTP 429 (rate limit): 5 segundos na primeira tentativa, 10 na segunda e 20 na terceira.

#### `httpx`
Biblioteca HTTP moderna para Python. Utilizada dentro de `src/agents/extrato_nomes_startups_gemini.py` para substituir o cliente HTTP padrão do SDK do Google por uma instância customizada com `verify=False`. Esse parâmetro desativa a verificação de certificado SSL, contornando um problema comum em redes corporativas com **proxy de inspeção SSL**: nesses ambientes, o proxy intercepta conexões HTTPS e apresenta um certificado próprio no lugar do certificado do servidor de destino. Como esse certificado não está na lista de autoridades confiáveis padrão do Python, a conexão seria rejeitada com erro `SSL: CERTIFICATE_VERIFY_FAILED`. A solução adotada permite que o código opere normalmente nesses ambientes.

---

## Funcionamento Detalhado

### 1. Inicialização

O módulo resolve a raiz do projeto subindo três níveis a partir de sua localização e carrega as variáveis de ambiente do `.env`. O modelo spaCy é carregado uma única vez na memória no início da função `filtrar()`, evitando overhead de carregamento a cada artigo.

### 2. Listas de controle estático

Antes de qualquer processamento dinâmico, três estruturas estáticas são definidas:

**`DENYLIST`**: conjunto de nomes que o modelo NER frequentemente classifica como `ORG` mas que não são startups-alvo do projeto. Inclui grandes empresas de tecnologia, bancos, fundos de investimento, redes sociais, países e nomes de pessoas públicas. Qualquer candidato presente nessa lista é descartado imediatamente.

**`BLOCKLIST_INICIO`**: conjunto de palavras que, quando aparecem como primeira palavra do título, indicam que o título não se inicia com o nome de uma startup (ex: artigos, preposições, conjunções, palavras de contexto como "Startup", "Fintech", "Mercado"). Utilizada tanto na validação quanto no fallback de regex.

**`_VERBOS` / `_VERBOS_REGEX`**: lista de aproximadamente 90 verbos de ação empresarial em português no presente do indicativo (singular e plural), compilados em uma única expressão regular. Utilizados para detectar o limite entre o sujeito e o predicado nos títulos das notícias.

### 3. Deduplicação via Supabase

Antes de processar qualquer artigo, o módulo consulta a tabela `nomes_empresas` no Supabase e obtém o conjunto de todas as URLs já presentes. Artigos com URL já registrada são ignorados durante o loop principal.

### 4. Loop de processamento

Para cada artigo presente no JSON de entrada:

1. **Filtro de seção**: artigos cuja URL não contenha `/startups/` são descartados — garantindo que apenas notícias da seção de startups do NeoFeed sejam processadas.
2. **Filtro de duplicata**: artigos com URL já presente no Supabase são ignorados.
3. **Extração do nome**: execução do pipeline de três camadas descrito abaixo.
4. **Validação**: o candidato extraído passa pela função `_is_valido()`.
5. **Deduplicação em memória**: o conjunto `vistos` impede que o mesmo nome de startup apareça mais de uma vez na saída da execução atual.
6. **Persistência incremental**: o arquivo de saída é reescrito a cada startup válida encontrada, protegendo os dados em caso de interrupção do processo.
7. **Pausa entre chamadas**: aguarda 1 segundo (configurável) entre iterações para respeitar o rate limit da API Gemini.

---

## Pipeline de Extração de Nomes — Três Camadas

A extração opera em cascata. Cada camada só é acionada se a anterior não produzir resultado.

```
Camada 1: Gemini API (IA generativa)
    ↓ retornou null ou falhou
Camada 2: spaCy NER (modelo de linguagem)
    ↓ nenhuma entidade ORG válida encontrada
Camada 3: Regex por posição verbal (heurística linguística)
```

### Camada 1 — Gemini API

Envia o título para o modelo `gemini-flash-lite-latest` através da função `extrair_nome_gemini` definida em `src/agents/extrato_nomes_startups_gemini.py`. O prompt contém 12 exemplos few-shot em português e a resposta é forçada para o formato JSON `{"startup": string | null}` via schema declarado. O prompt instrui o modelo a retornar `null` nos seguintes casos: o sujeito é um investidor ou fundo; a notícia é regulatória ou de opinião; o sujeito é uma pessoa física; o título descreve um tipo genérico de empresa sem nome próprio; múltiplas startups aparecem sem protagonista clara; o sujeito é um fenômeno ou tendência genérica.

### Camada 2 — spaCy NER

Processa o título com o pipeline NLP do spaCy e extrai todas as entidades classificadas como `ORG`. Cada candidato passa pela função `_is_valido()` e o primeiro aprovado é retornado.

**Quando a Camada 2 não produz resultado e a Camada 3 é acionada:**

- O modelo não reconhece a entidade como `ORG` — nomes de startups com vocabulário não convencional (inventados, em inglês, siglas) podem ser classificados como `MISC`, `LOC` ou ignorados;
- O modelo reconhece como `ORG`, mas `_is_valido()` rejeita o candidato — por exemplo, quando extrai o nome com pontuação anexada, quando extrai um nome presente na `DENYLIST`, ou quando agrupa entidades demais formando uma frase longa;
- O título não contém nenhum nome próprio que o modelo consiga identificar — como em títulos genéricos sem empresa nomeada.

### Camada 3 — Regex por posição verbal

Localiza o primeiro verbo de ação empresarial no título usando `_VERBOS_REGEX`. Extrai tudo que precede o verbo como candidato ao nome da startup. A heurística se baseia na estrutura típica de manchetes em português: `[Sujeito] [verbo] [complemento]`. O candidato é descartado se a primeira palavra estiver na `BLOCKLIST_INICIO` ou se não iniciar com letra maiúscula.

---

## Função de Validação — `_is_valido()`

Todo candidato extraído por qualquer camada passa pelas seguintes verificações:

| Regra | Justificativa |
|---|---|
| Mínimo de 3 caracteres | Evita siglas soltas e ruído |
| Não presente na `DENYLIST` | Remove grandes empresas, bancos e fundos |
| Inicia com letra maiúscula | Nomes próprios seguem essa convenção |
| Não contém `,` `:` `"` | Descarta frases capturadas erroneamente |
| Primeira palavra não na `BLOCKLIST_INICIO` | Evita capturar início de frase genérica |
| Máximo de 6 palavras | Nomes de empresa raramente excedem esse limite |

---

## Estrutura dos Dados de Saída

Cada registro produzido pelo módulo segue o seguinte formato:

```json
{
  "startup": "Trace Finance",
  "titulo": "Trace Finance capta mais de R$ 160 milhões em rodada Série B",
  "url": "https://neofeed.com.br/startups/trace-finance-capta...",
  "tags": ["fintech", "série b", "captação"]
}
```

| Campo | Descrição |
|---|---|
| `startup` | Nome da startup extraído pelo pipeline |
| `titulo` | Título original do artigo conforme coletado |
| `url` | URL canônica do artigo no NeoFeed |
| `tags` | Categorias do artigo extraídas durante a coleta |

---

## Pontos de Atenção

**Precisão do modelo spaCy `_sm`**
O modelo `pt_core_news_sm` é um modelo de tamanho reduzido, treinado predominantemente em textos jornalísticos formais. Nomes de startups com vocabulário não convencional, estrangeiro ou inventado podem não ser reconhecidos corretamente como entidades `ORG`, aumentando a dependência das camadas de fallback.

**Manutenção das listas estáticas**
A `DENYLIST` e a `BLOCKLIST_INICIO` são mantidas manualmente no código-fonte. Novos fundos de investimento, bancos ou grandes empresas que passem a aparecer com frequência nos títulos não serão filtrados automaticamente até que as listas sejam atualizadas.

**Sensibilidade à estrutura do NeoFeed**
O filtro de seção (`'/startups/' not in url`) e a estrutura dos dados de entrada dependem de que o NeoFeed mantenha seu padrão atual de URLs e organização de conteúdo. Alterações no site podem exigir revisão do módulo de coleta e dos critérios de filtragem.

**Rate limit da API Gemini no tier gratuito**
O tier gratuito da API Gemini possui limites de requisições por minuto (RPM) e por dia (RPD). O delay padrão de 1 segundo entre chamadas é um controle preventivo, mas em lotes grandes pode não ser suficiente para evitar erros 429. O mecanismo de retry com backoff exponencial mitiga ocorrências pontuais, porém o esgotamento da cota diária redireciona todo o processamento para as camadas de fallback.

**Ausência de validação externa do nome extraído**
O módulo valida os candidatos por critérios sintáticos (formato, comprimento, presença em listas), mas não verifica se a startup extraída de fato existe como empresa — por exemplo, consultando uma base de CNPJs ou uma API externa. Extrações sintaticamente válidas mas semanticamente incorretas podem passar pela validação sem serem detectadas.

**`verify=False` no cliente HTTP**
A desativação da verificação de certificado SSL via `httpx` com `verify=False` é uma solução adotada para compatibilidade com ambientes corporativos que utilizam proxy de inspeção SSL. Em redes não confiáveis ou em ambiente de produção, essa configuração representa uma exposição a potenciais ataques de interceptação de tráfego HTTPS.
