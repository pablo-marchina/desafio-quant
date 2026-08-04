# Documentação Técnica — `filtro_ia.py`

## Visão Geral

O `filtro_ia.py` é o módulo árbitro final do subpipeline de detecção de IA do projeto. Sua responsabilidade não é coletar dados — essa tarefa é realizada por quatro scripts anteriores —, mas sim **ler, agregar e julgar** todos os sinais já coletados, produzindo um veredito definitivo para cada empresa: ela usa IA ou não?

O módulo opera sobre a tabela `sinais_ia` do Supabase, que contém registros provenientes de até quatro fontes distintas: o site institucional da empresa, notícias do portal NeoFeed, vagas abertas na plataforma Gupy e cobertura em veículos de imprensa brasileiros. Para cada empresa, o `filtro_ia.py` calcula uma **pontuação agregada** a partir desses sinais, aplica um limiar numérico (*threshold*) e emite um veredito booleano. Empresas que atingem ou superam a pontuação mínima são marcadas como aprovadas e avançam para a etapa de análise profunda do projeto.

Os resultados são gravados simultaneamente na tabela `avaliacoes_ia` do Supabase — com suporte a re-execuções idempotentes via `UPSERT` — e em um arquivo JSON diário salvo localmente, que serve de relatório auditável com separação entre aprovadas e reprovadas.

---

## Posição no Pipeline

```
descobre_institucional.py  ──────────────────────────────────────┐
analisa_neofeed.py         ──→ Supabase (tabela sinais_ia)  ─────┤──→ filtro_ia.py ──→ Supabase (tabela avaliacoes_ia)
descobre_gupy_vagas.py     ──────────────────────────────────────┤               ──→ data/jsons/vereditos_ia/YYYY-MM-DD.json
descobre_imprensa.py       ──────────────────────────────────────┘
```

O `filtro_ia.py` é a última etapa do subpipeline de detecção de IA. As quatro camadas que o alimentam são:

| Camada | Script | Fonte de dados |
|---|---|---|
| `institucional` | `descobre_institucional.py` | Site oficial da empresa |
| `neofeed` | `analisa_neofeed.py` | Notícias do portal NeoFeed |
| `gupy_vagas` | `descobre_gupy_vagas.py` | Vagas de emprego na plataforma Gupy |
| `imprensa` | `descobre_imprensa.py` | Artigos em veículos de imprensa brasileiros |

---

## Tecnologias Utilizadas

### Linguagem

**Python 3.9+**

A anotação `str | None` em assinaturas de função e o uso de `from __future__ import annotations` requerem Python moderno. O `__future__` ativa avaliação *lazy* de *type hints*, permitindo anotações de tipo sem erro de runtime em versões anteriores ao 3.10.

---

### Biblioteca padrão do Python

| Módulo | Uso no código |
|---|---|
| `json` | Serialização do relatório JSON diário salvo em `data/jsons/vereditos_ia/` |
| `os` | Acesso às variáveis de ambiente `SUPABASE_URL` e `SUPABASE_KEY` |
| `re` | Compilação e execução dos cinco padrões de expressão regular que classificam as evidências |
| `datetime` / `timezone` | Geração de timestamps UTC registrados nos campos `avaliado_em` e `gerado_em` |
| `pathlib.Path` | Manipulação de caminhos de arquivo de forma orientada a objetos e multiplataforma |

**Sobre o módulo `re` (regex):**

`re` é o módulo Python que implementa **expressões regulares** — um mecanismo de busca textual por padrões, em vez de palavras exatas. No `filtro_ia.py`, são compilados **cinco padrões distintos**, cada um com uma responsabilidade específica na análise das evidências. A compilação prévia via `re.compile()` é feita uma única vez na inicialização do módulo — mais eficiente do que recompilar o padrão a cada empresa processada. Todos os padrões utilizam a flag `re.IGNORECASE` para ignorar diferenças entre maiúsculas e minúsculas, e a maioria usa delimitadores de palavra `\b` para evitar capturas parciais dentro de outras palavras.

---

### Bibliotecas de terceiros

#### `python-dotenv`

Carrega variáveis de ambiente a partir do arquivo `.env` localizado na raiz do projeto. Provê as credenciais `SUPABASE_URL` e `SUPABASE_KEY` sem expô-las no código-fonte.

#### `supabase-py`

Cliente Python oficial do **Supabase** (banco de dados PostgreSQL gerenciado na nuvem). Utilizado em três momentos distintos ao longo da execução: para **ler** o cadastro de empresas na tabela `empresas`, para **ler** todos os sinais coletados na tabela `sinais_ia` e para **gravar** as avaliações finais na tabela `avaliacoes_ia`.

---

## Funcionamento Detalhado

### 1. Inicialização

O módulo resolve a raiz do projeto subindo três níveis a partir de sua localização (`Path(__file__).resolve().parent.parent.parent`) e carrega as variáveis de ambiente do `.env`. O diretório de saída JSON (`data/jsons/vereditos_ia/`) e o cliente Supabase são configurados no nível do módulo — antes da execução de qualquer função —, tornando-os disponíveis globalmente.

### 2. Constantes de calibração

Dois valores centrais controlam o comportamento do sistema de pontuação:

**`THRESHOLD = 3`**: pontuação mínima para que uma empresa seja considerada usuária de IA. Empresas com pontuação total ≥ 3 recebem `veredito = True` e são aprovadas.

**`_TETO_CAMADA`**: dicionário que documenta a pontuação máxima possível por fonte, considerando que apenas o melhor sinal de cada camada contribui para a soma final:

| Camada | Pontuação máxima |
|---|---|
| `institucional` | 3 |
| `neofeed` | 3 |
| `gupy_vagas` | 2 |
| `imprensa` | 2 |

Com quatro camadas independentes, a pontuação máxima teórica alcançável é **10 pontos**.

### 3. Padrões de expressão regular

Cinco padrões são compilados na inicialização do módulo, cada um com uma função específica na cadeia de classificação:

**`_PALAVRAS_IA`** — detector genérico de termos de inteligência artificial em português e inglês. É o padrão mais utilizado no código: todas as camadas de pontuação o consultam para verificar se o texto de uma evidência contém referência real a IA antes de atribuir pontos. Cobre aproximadamente 30 termos, incluindo `IA`, `AI`, `machine learning`, `deep learning`, `LLM`, `GPT`, `embeddings`, `fine-tuning`, `retrieval-augmented`, `foundation model`, `multimodal`, `hugging face`, `langchain`, `openai`, `anthropic`, `claude`, `gemini` e `llama`.

**`_CARGOS_IA`** — detecta títulos de vagas de emprego diretamente ligadas a IA e Machine Learning: `cientista de dados`, `data scientist`, `ML engineer`, `deep learning`, `inteligência artificial` e variações de `engenheiro` ou `especialista` com até 15 caracteres intermediários seguidos de `IA`, `machine` ou `ML`. Usado exclusivamente na camada `gupy_vagas`.

**`_CARGOS_DADOS`** — detecta títulos de vagas relacionadas a dados sem menção explícita a IA: `engenheiro de dados`, `data engineer`, `analytics`, `big data`, `analista de dados`. São tratados como sinais mais fracos do que cargos de IA direta. Também usado exclusivamente na camada `gupy_vagas`.

**`_TENDENCIA`** — detecta artigos do NeoFeed que discutem o mercado de IA em sentido amplo, sem que a empresa monitorada seja protagonista do uso de IA. Expressões como `nova safra`, `bilionários`, `corrida por`, `onda de`, `mercado de IA` e `boom da IA` indicam que o artigo fala *sobre* o cenário de IA, não *sobre* a empresa. Esses artigos recebem pontuação reduzida.

**`_PAPEL_INVESTIDOR`** — detecta verbos que indicam que a empresa mencionada no artigo é **investidora** de uma startup de IA, e não ela própria uma usuária de IA. Os verbos selecionados — `atrai`, `ancora`, `financia`, `co-lidera`, `co-investem` — são inequivocamente papéis financeiros. Verbos como `investe` e `apoia` foram intencionalmente excluídos da lista por também descreverem empresas que adotam IA em seus produtos.

### 4. Pontuação individual por sinal — `_score_sinal()`

Esta função recebe um único sinal — uma linha da tabela `sinais_ia` — e retorna o par `(pontos, razão_textual)`. A lógica é específica para cada camada e só é executada quando o campo `encontrado` é verdadeiro:

- **Camada `institucional`**: aplica `_PALAVRAS_IA` sobre a evidência. Se houver menção explícita a IA → **3 pontos**. Se encontrado sem menção a IA → **0 pontos** (descartado).
- **Camada `neofeed`**: exige menção a IA como pré-requisito (0 pontos sem ela). Se o artigo descreve tendência de mercado (`_TENDENCIA`) → **1 ponto**. Se a empresa aparece como investidora (`_PAPEL_INVESTIDOR`) → **1 ponto**. Caso contrário → **3 pontos**.
- **Camada `gupy_vagas`**: avalia o título da vaga. Cargo de IA/ML (`_CARGOS_IA`) → **2 pontos**. Cargo de dados (`_CARGOS_DADOS`) → **1 ponto**. Vaga sem cargo específico mas com sinal relevante → **1 ponto**.
- **Camada `imprensa`**: aplica `_PALAVRAS_IA` sobre a evidência. Com menção a IA → **2 pontos**. Sem menção → **0 pontos** (descartado).

### 5. Agregação por empresa — `_avaliar_empresa()`

Para cada empresa, a função percorre todos os seus sinais e aplica a lógica de **melhor score por camada**: apenas o sinal de maior pontuação dentro de cada camada é considerado na soma final. Múltiplos sinais positivos na mesma camada não se acumulam — o segundo e o terceiro são descartados se já houver um de pontuação igual ou maior.

Isso implementa uma proteção contra inflação artificial de pontuação: uma empresa com 10 vagas de IA no Gupy pontua exatamente o mesmo que uma empresa com 1 vaga de IA — o teto da camada `gupy_vagas` para cargo de IA é 2 pontos, independentemente da quantidade de vagas.

A pontuação final é a **soma dos melhores scores de cada camada**. Ao término, a função constrói a lista `sinais_ativos` — somente os sinais que efetivamente contribuíram para a pontuação, cada um com camada, score, razão textual e evidência truncada a 120 caracteres.

### 6. Carregamento dos dados — `_carregar_dados()`

Realiza duas consultas ao Supabase:

1. `SELECT id, nome FROM empresas` → constrói o mapa `{id: nome}` de todas as empresas cadastradas
2. `SELECT empresa_id, camada, encontrado, evidencia FROM sinais_ia` → carrega **todos** os sinais de todas as empresas em uma única requisição

A estratégia de carregar tudo de uma vez evita N consultas ao banco para N empresas, trocando volume de dados por número de *roundtrips* de rede.

### 7. Agrupamento — `_agrupar_por_empresa()`

Converte a lista plana de sinais em um dicionário `{empresa_id: [lista de sinais]}`. Essa estrutura permite que o loop principal processe cada empresa de forma independente, sem consultas adicionais ao banco durante a iteração.

### 8. Gravação no Supabase — `_gravar_supabase()`

Executa um `UPSERT` na tabela `avaliacoes_ia` com `on_conflict="empresa_id"`: se já existe uma avaliação para a empresa, ela é **substituída** pela mais recente; caso contrário, é inserida. Isso garante que re-execuções do script produzam sempre o estado mais atualizado, sem duplicatas.

### 9. Gravação em arquivo JSON — `_gravar_json()`

Salva o relatório da execução em `data/jsons/vereditos_ia/YYYY-MM-DD.json`, com nome de arquivo baseado na data UTC atual. O arquivo organiza as empresas em dois grupos:

- **Aprovadas**: ordenadas por pontuação decrescente, com detalhes dos sinais ativos que contribuíram para a pontuação
- **Reprovadas**: ordenadas por pontuação decrescente, com distinção entre `"pontuação abaixo do threshold"` (teve algum sinal, mas não o suficiente) e `"nenhum sinal de IA encontrado"` (pontuação zero)

O arquivo inclui ainda metadados de execução: timestamp de geração, threshold utilizado e total de empresas avaliadas.

### 10. Função de entrada — `filtrar()`

Ponto de entrada do módulo, chamado diretamente ao executar o script. Orquestra todo o fluxo: carregamento, agrupamento, avaliação empresa a empresa, impressão de resumo no terminal e gravação dos resultados. Aceita dois parâmetros opcionais:

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `gravar_banco` | `True` | Se `False`, executa a avaliação completa mas não grava em `avaliacoes_ia` no Supabase |
| `filtrar_nome` | `None` | Se informado, restringe o processamento à empresa com esse nome exato |

---

## Sistema de Pontuação por Camada

A tabela abaixo consolida todas as regras de pontuação aplicadas pelo módulo:

| Camada | Condição | Pontos | Razão gravada |
|---|---|---|---|
| `institucional` | evidência contém termo de IA | **3** | "site menciona IA explicitamente" |
| `institucional` | encontrado sem menção a IA | 0 | descartado |
| `neofeed` | evidência sem menção a IA | 0 | descartado |
| `neofeed` | artigo sobre tendência de mercado | **1** | "artigo sobre tendência de mercado" |
| `neofeed` | empresa mencionada como investidora | **1** | "empresa mencionada como investidora/parceira, não como usuária de IA" |
| `neofeed` | artigo sobre IA diretamente da empresa | **3** | "artigo sobre IA diretamente relacionado à empresa" |
| `gupy_vagas` | cargo de IA/ML (`_CARGOS_IA`) | **2** | título da vaga (truncado a 60 chars) |
| `gupy_vagas` | cargo de dados (`_CARGOS_DADOS`) | **1** | título da vaga (truncado a 60 chars) |
| `gupy_vagas` | vaga encontrada sem cargo específico | **1** | "vaga relevante" + título |
| `imprensa` | evidência contém termo de IA | **2** | "imprensa menciona IA" |
| `imprensa` | encontrado sem menção a IA | 0 | descartado |

**Regra de anti-inflação:** apenas o maior score de cada camada entra na soma final. A pontuação de cada camada nunca excede os valores da coluna "Pontos" acima, independentemente da quantidade de sinais daquela fonte.

---

## Estrutura dos Dados de Saída

### Tabela `avaliacoes_ia` no Supabase

Cada empresa recebe exatamente um registro na tabela (UPSERT por `empresa_id`):

```json
{
  "empresa_id": 12,
  "pontuacao": 5,
  "veredito": true,
  "sinais_ativos": [
    {
      "camada": "institucional",
      "score": 3,
      "razao": "site menciona IA explicitamente",
      "evidencia": "...utilizamos modelos de deep learning para análise preditiva de..."
    },
    {
      "camada": "gupy_vagas",
      "score": 2,
      "razao": "vaga de IA/ML: Engenheiro de Machine Learning Sênior",
      "evidencia": "Engenheiro de Machine Learning Sênior"
    }
  ],
  "avaliado_em": "2026-06-25T14:03:17.441283+00:00"
}
```

| Campo | Descrição |
|---|---|
| `empresa_id` | Chave estrangeira referenciando a tabela `empresas` |
| `pontuacao` | Soma dos melhores scores de cada camada |
| `veredito` | `true` se `pontuacao >= THRESHOLD`; `false` caso contrário |
| `sinais_ativos` | Lista JSON com os sinais que contribuíram para a pontuação, incluindo razão e trecho da evidência (máximo 120 caracteres) |
| `avaliado_em` | Timestamp UTC do momento da avaliação no formato ISO 8601 |

---

### Arquivo JSON diário — `data/jsons/vereditos_ia/YYYY-MM-DD.json`

```json
{
  "gerado_em": "2026-06-25T14:03:21.983412+00:00",
  "threshold": 3,
  "total_avaliadas": 87,
  "aprovadas": [
    {
      "empresa_id": 12,
      "nome": "Docket",
      "pontuacao": 5,
      "sinais_ativos": [...]
    }
  ],
  "reprovadas": [
    {
      "empresa_id": 43,
      "nome": "FitBank",
      "pontuacao": 1,
      "motivo": "pontuação abaixo do threshold"
    },
    {
      "empresa_id": 71,
      "nome": "Conta Simples",
      "pontuacao": 0,
      "motivo": "nenhum sinal de IA encontrado"
    }
  ]
}
```

| Campo | Descrição |
|---|---|
| `gerado_em` | Timestamp UTC da execução no formato ISO 8601 |
| `threshold` | Valor do `THRESHOLD` utilizado na execução |
| `total_avaliadas` | Total de empresas processadas |
| `aprovadas` | Lista de empresas com `veredito = true`, ordenadas por pontuação decrescente |
| `reprovadas` | Lista de empresas com `veredito = false`, com campo `motivo` indicando se a empresa teve algum sinal ou nenhum |