# Documentação Técnica — `analisa_neofeed.py`

## Visão Geral

O `analisa_neofeed.py` é um módulo de classificação de sinais de IA do projeto. Sua responsabilidade é percorrer os artigos do portal **Neofeed** já armazenados no Supabase e determinar, a partir do título de cada notícia, se aquela startup apresenta algum sinal de uso de inteligência artificial.

O módulo aplica uma única camada de detecção: uma **expressão regular multilíngue** que verifica a presença de termos relacionados à IA no título do artigo. Quando um ou mais termos são encontrados, o módulo registra um **sinal positivo** para aquela empresa. Quando nenhum termo relevante é identificado, registra um **sinal negativo** — indicando que a empresa foi verificada, não ignorada.

Os resultados são gravados na tabela `sinais_ia` do Supabase com a camada identificada como `neofeed`, e também persistidos localmente em arquivo JSON para consulta e auditoria.

---

## Posição no Pipeline

```
coleta_neofeed.py       [raspagem de artigos brutos do NeoFeed]
    → filtro.py         [extração de nomes de startups dos títulos]
        → Supabase (tabela nomes_empresas)
            → analisa_neofeed.py    [classificação de sinais de IA]
                → Supabase (tabela sinais_ia, camada "neofeed")
                → data/jsons/neofeed/neofeed.json
```

O módulo é uma das quatro camadas de detecção de sinais de IA do projeto:

| Camada | Script | Fonte |
|---|---|---|
| `institucional` | `descobre_institucional.py` | Site oficial da empresa |
| `imprensa` | `descobre_imprensa.py` | Notícias na internet |
| `gupy_vagas` | `descobre_gupy_vagas.py` | Vagas de emprego no Gupy |
| `neofeed` | **este script** | Artigos do portal NeoFeed |

---

## Tecnologias Utilizadas

### Linguagem

**Python 3.10+**
A anotação `str | None` e o uso de `from __future__ import annotations` requerem Python moderno. O `__future__` ativa avaliação lazy de type hints, permitindo anotações de tipo sem erro de runtime em versões anteriores ao 3.10.

---

### Biblioteca padrão do Python

| Módulo | Uso no código |
|---|---|
| `json` | Leitura do arquivo JSON local existente e serialização dos novos registros ao disco |
| `os` | Acesso às variáveis de ambiente `SUPABASE_URL` e `SUPABASE_KEY` |
| `re` | Compilação e execução da expressão regular multilíngue para detecção de termos de IA nos títulos |
| `datetime` / `timezone` | Registro do timestamp UTC exato em que cada análise foi realizada |
| `pathlib.Path` | Manipulação de caminhos de arquivo de forma orientada a objetos e multiplataforma |

**Sobre o módulo `re` (regex):**
O módulo `re` implementa **expressões regulares** — um mecanismo de busca textual por padrões, em vez de palavras exatas. Neste script, ele compila uma única expressão que agrupa todos os termos de IA em português e inglês e detecta sua presença no título de cada artigo. A compilação prévia via `re.compile()` é feita uma única vez na inicialização do módulo, o que é mais eficiente do que recompilar o padrão a cada artigo processado.

---

### Bibliotecas de terceiros

#### `python-dotenv`
Carrega variáveis de ambiente a partir do arquivo `.env` localizado na raiz do projeto. Provê as credenciais `SUPABASE_URL` e `SUPABASE_KEY` sem expô-las no código-fonte.

#### `supabase-py`
Cliente Python oficial do **Supabase** (banco de dados PostgreSQL gerenciado na nuvem). Utilizado em três momentos distintos: para **ler** todos os artigos da tabela `nomes_empresas`, para **consultar** a tabela `empresas` e obter os IDs correspondentes a cada startup, e para **gravar** os sinais detectados na tabela `sinais_ia`.

---

## Funcionamento Detalhado

### 1. Inicialização

O módulo resolve a raiz do projeto subindo três níveis a partir de sua localização (`Path(__file__).resolve().parent.parent.parent`) e carrega as variáveis de ambiente do `.env`. Em seguida, cria a conexão global com o Supabase — reutilizada por todas as funções — e define o caminho de saída do arquivo JSON em `data/jsons/neofeed/`.

### 2. Expressão Regular de IA

Uma expressão regular multilíngue é compilada uma única vez no nível do módulo:

```python
_PALAVRAS_IA = re.compile(
    r'\b('
    r'IA|AI|intelig[eê]ncia artificial|artificial intelligence'
    r'|machine learning|deep learning|LLM|GPT|chatbot'
    r'|modelo preditivo|MLOps|data science|algoritmo'
    r'|automa[çc][ãa]o inteligente|rede neural|neural'
    r'|generativa|generativo|gen.?ai|copilot'
    r'|processamento de linguagem|NLP|computer vision'
    r'|reconhecimento de imagem|aprendizado de m[áa]quina'
    r')\b',
    re.IGNORECASE,
)
```

Detalhes técnicos relevantes do padrão:

- **`\b`** — *word boundary*: garante que "IA" não case dentro de palavras como "VIAGEM" ou "DIÁRIO"
- **`re.IGNORECASE`** — insensível a maiúsculas e minúsculas, portanto "LLM", "llm" e "Llm" são todos detectados
- **`[eê]`** — alternativa de caracteres para cobrir "inteligência" (com acento) e "inteligencia" (sem acento)
- **`[çc][ãa]o`** — cobre "automação" e "automacao" simultaneamente
- **`gen.?ai`** — o `.?` significa zero ou um caractere qualquer, cobrindo "genai", "gen-ai" e "gen ai"
- A regex cobre português e inglês no mesmo padrão

A função `_e_ia(titulo)` aplica essa regex e retorna `True` se qualquer termo for encontrado.

### 3. Mapa de Empresas

A função `_carregar_mapa_empresas()` carrega **todas as empresas cadastradas** no Supabase e constrói um dicionário `{ "nome em minúsculo": id_numérico }`. Esse índice permite, dado o nome de uma startup vindo da tabela `nomes_empresas`, localizar rapidamente o seu `id` na tabela `empresas`. O `.strip().lower()` normaliza os nomes para evitar falhas por espaços extras ou capitalização diferente.

### 4. Verificação de Duplicata

Antes de processar qualquer empresa, a função `_ja_checado(empresa_id)` consulta a tabela `sinais_ia` verificando se já existe um registro com aquele `empresa_id` e a camada `"neofeed"`. O `.limit(1)` é uma otimização: não é necessário buscar todos os registros, apenas confirmar a existência de ao menos um. Empresas já verificadas são ignoradas, tornando o script seguro para reexecução sem criar duplicatas.

### 5. Persistência Incremental em JSON

A função `_salvar_json()` mantém o arquivo `data/jsons/neofeed/neofeed.json` como um **cache local incremental**. A cada execução:

1. Lê os registros já presentes no arquivo
2. Extrai todas as URLs salvas para um `set` (estrutura de dados com busca em tempo constante)
3. Filtra os novos registros, mantendo apenas os que ainda não estão no arquivo
4. Concatena os novos com os existentes e regrava o arquivo completo

Isso garante que rodadas repetidas não dupliquem dados no arquivo local.

### 6. Função Principal — `classificar()`

É a função que orquestra todas as etapas. Aceita dois parâmetros opcionais:

- `atualizar_banco: bool = True` — se `False`, processa e retorna os dados sem gravar no Supabase (útil para testes)
- `nome: str | None = None` — se fornecido, filtra para analisar apenas uma startup específica

**Fluxo interno:**

```
Busca todos os artigos da tabela nomes_empresas
    ↓ (filtra por nome, se fornecido)
Carrega o mapa de empresas (nome → id)
    ↓
Para cada artigo:
    ├── Descarta se startup não está no cadastro de empresas
    ├── Descarta se empresa já foi verificada nessa camada
    ├── Aplica a regex no título (_e_ia)
    ├── Insere resultado em sinais_ia no Supabase
    └── Adiciona à lista de registros processados
    ↓
Salva todos os registros no arquivo JSON local
    ↓
Imprime estatísticas no terminal
    ↓
Retorna apenas os registros com encontrado=True
```

---

## Estrutura dos Dados de Saída

Cada registro produzido pelo módulo segue o formato abaixo.

**Registro com sinal positivo (termo de IA encontrado no título):**

```json
{
  "empresa_id": 12,
  "nome_empresa": "Sami Saúde",
  "titulo": "Sami Saúde usa machine learning para reduzir sinistros em 30%",
  "fonte_url": "https://neofeed.com.br/startups/sami-saude-machine-learning/",
  "encontrado": true,
  "coletado_em": "2026-06-25T14:32:10.482301+00:00"
}
```

**Registro com sinal negativo (empresa verificada, sem termo de IA):**

```json
{
  "empresa_id": 27,
  "nome_empresa": "Loft",
  "titulo": "Loft expande operações para São Paulo e anuncia novo CEO",
  "fonte_url": "https://neofeed.com.br/startups/loft-expansao-sao-paulo/",
  "encontrado": false,
  "coletado_em": "2026-06-25T14:32:11.901245+00:00"
}
```

| Campo | Descrição |
|---|---|
| `empresa_id` | Chave estrangeira referenciando a tabela `empresas` no Supabase |
| `nome_empresa` | Nome da startup conforme cadastrado no Supabase |
| `titulo` | Título do artigo conforme armazenado na tabela `nomes_empresas` |
| `fonte_url` | URL do artigo original no portal NeoFeed |
| `encontrado` | `true` se há sinal de IA no título; `false` se a empresa foi verificada sem resultado |
| `coletado_em` | Timestamp UTC do momento da análise no formato ISO 8601 |

Na tabela `sinais_ia` do Supabase, o campo `evidencia` recebe o título do artigo quando `encontrado=true`, e `null` quando `encontrado=false`.