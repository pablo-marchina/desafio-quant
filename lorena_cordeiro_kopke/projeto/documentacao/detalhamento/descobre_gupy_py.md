# Documentação Técnica — `descobre_gupy.py`

## Visão Geral

O `descobre_gupy.py` é um módulo do pipeline de coleta de dados do projeto. Sua responsabilidade é identificar, de forma automática, o **subdomínio que cada empresa cadastrada no banco de dados utiliza na plataforma Gupy** — a principal plataforma brasileira de recrutamento e seleção.

A Gupy disponibiliza a cada empresa contratante uma página pública de vagas no formato `https://[subdominio].gupy.io`. O script parte dos nomes das empresas armazenados no Supabase e, por meio de geração de variações e confirmação via requisições HTTP, determina qual slug corresponde a cada empresa na plataforma. Essa informação é então persistida tanto no banco de dados quanto em arquivo JSON local.

A abordagem não utiliza nenhuma API oficial da Gupy (que não existe para esse fim). Em vez disso, o script emprega **enumeração de subdomínios por tentativa e erro**: gera candidatos plausíveis a partir do nome da empresa e confirma cada um via requisição HTTP, usando critérios específicos para distinguir subdomínios válidos de redirecionamentos para a página principal.

---

## Posição no Pipeline

```
Supabase (tabela empresas)
    → descobre_gupy.py        [geração de candidatos + confirmação HTTP]
        → empresas.gupy_subdominio  [coluna atualizada no Supabase]
        → gupy_encontrados.json     [registro local dos subdomínios encontrados]
            → gupy_vagas/           [coleta de vagas por subdomínio confirmado]
```

---

## Tecnologias Utilizadas

### Linguagem

**Python 3.10+**
O uso de `str | None` como anotação de tipo e a presença de `from __future__ import annotations` requerem Python moderno. O `__future__` ativa avaliação lazy de type hints, permitindo essa sintaxe sem erro de runtime em versões anteriores ao 3.10.

---

### Biblioteca padrão do Python

| Módulo | Uso no código |
|---|---|
| `json` | Leitura do arquivo JSON existente e escrita incremental dos novos registros encontrados |
| `os` | Acesso às variáveis de ambiente `SUPABASE_URL` e `SUPABASE_KEY` |
| `time` | Pausa de 400ms entre requisições HTTP para não sobrecarregar o servidor da Gupy |
| `unicodedata` | Normalização Unicode no modo `NFKD` para remoção de acentos e diacríticos |
| `datetime`, `timezone` | Geração de timestamp no padrão ISO 8601 com fuso horário UTC explícito |
| `pathlib.Path` | Manipulação de caminhos de arquivo de forma orientada a objetos e multiplataforma |
| `sys` | Leitura de argumentos de linha de comando (`--debug`) via `sys.argv` |

**Sobre `unicodedata` e normalização NFKD:**
NFKD (*Normalisation Form Compatibility Decomposition*) é um padrão Unicode que decompõe caracteres compostos nos seus constituintes básicos. Por exemplo, `é` é decomposto em `e` + ` ́` (acento separado). Em seguida, o encode `ascii` com `ignore` descarta os caracteres não-ASCII — incluindo os acentos — deixando apenas as letras base. Isso é o que permite que `"Méliuz"` se torne `"Meliuz"` antes da transformação em slug.

---

### Bibliotecas de terceiros

#### `requests`
Biblioteca HTTP de uso geral para Python. É usada tanto para criar a sessão HTTP reutilizável (`requests.Session`) quanto para executar as requisições GET de confirmação dos subdomínios. O uso de `Session` em vez de chamadas diretas a `requests.get()` mantém a mesma conexão TCP entre requisições, reduzindo overhead de handshake.

#### `python-dotenv`
Carrega variáveis de ambiente a partir do arquivo `.env` localizado na raiz do projeto. Provê as credenciais `SUPABASE_URL` e `SUPABASE_KEY` sem expô-las no código-fonte.

#### `supabase-py`
Cliente Python oficial do **Supabase** (banco de dados PostgreSQL gerenciado na nuvem). Utilizado em dois momentos: para buscar as empresas pendentes antes do processamento e para atualizar a coluna `gupy_subdominio` de cada empresa assim que o subdomínio é confirmado.

---

## Funcionamento Detalhado

### 1. Inicialização

```python
_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "Mozilla/5.0 (compatible; pesquisa-academica/1.0)"
```

O módulo resolve a raiz do projeto subindo três níveis a partir de sua localização (`src/dados_startups/descobre_gupy.py`), carrega o `.env` e instancia o cliente Supabase e a sessão HTTP. O `User-Agent` customizado identifica o agente como pesquisa acadêmica — servidores que bloqueiam requisições sem identificação são contornados sem recorrer a agentes genéricos.

### 2. Busca das empresas pendentes

A função `descobrir()` inicia consultando a tabela `empresas` no Supabase e filtrando apenas as linhas em que `gupy_subdominio` ainda não está preenchido. Isso garante idempotência: executar o script múltiplas vezes não reprocessa empresas já resolvidas.

```python
pendentes = [r for r in rows if not r.get("gupy_subdominio")]
```

Se o parâmetro `nome` for fornecido, a query inclui um filtro `.eq("nome", nome)`, útil para testar ou reprocessar uma empresa específica.

### 3. Geração de candidatos

Para cada empresa pendente, a função `_candidatos()` produz uma lista ordenada de slugs para testar. O processo tem duas etapas:

**Etapa 1 — `_slugify()`**: transforma o nome da empresa em texto puro ASCII, minúsculo, sem caracteres especiais.

**Exemplo passo a passo com `"Méliuz & Cia"`:**

| Passo | Operação | Resultado |
|---|---|---|
| Entrada | — | `"Méliuz & Cia"` |
| `NFKD` normalize | Decompõe acento em caractere base + diacrítico | `"Méliuz & Cia"` |
| encode ASCII ignore | Descarta os diacríticos | `"Meliuz & Cia"` |
| lower + substituições | `&` → `e`, `/` → espaço | `"meliuz e cia"` |
| remove não-alfanum | Remove qualquer char fora de `[a-z0-9 ]` | `"meliuz e cia"` |
| strip | Remove espaços nas bordas | `"meliuz e cia"` |

**Etapa 2 — `_candidatos()`**: a partir do slug base, gera variações na ordem de maior para menor probabilidade:

| Candidato | Como é gerado | Exemplo para `"Banco Inter S.A."` → `"banco inter sa"` |
|---|---|---|
| Palavras com hífen | `"-".join(palavras)` | `"banco-inter-sa"` |
| Palavras sem separador | `"".join(palavras)` | `"bancointersa"` |
| Primeira palavra | `palavras[0]` | `"banco"` |
| Sigla (iniciais de palavras ≥3 letras) | `"".join(p[0] for p in palavras if len(p) >= 3)` | `"bi"` (banco+inter) |
| Primeiras duas palavras com hífen | `"-".join(palavras[:2])` | `"banco-inter"` |
| Primeiras duas palavras sem separador | `"".join(palavras[:2])` | `"bancointer"` |

A deduplicação final via `dict.fromkeys()` elimina repetições mantendo a ordem de inserção.

### 4. Confirmação do subdomínio

Para cada candidato, `_provar_subdominio()` faz uma requisição GET para `https://[slug].gupy.io` e aplica dois critérios simultâneos para considerar o subdomínio como válido:

1. O status HTTP da resposta final deve ser **200**
2. A URL final (após seguir todos os redirecionamentos) **não pode ser** `https://www.gupy.io` nem `https://gupy.io`

**Por que o segundo critério é necessário?** Quando um subdomínio não existe na Gupy, o servidor não retorna 404 — ele redireciona para a página principal da Gupy com status 200. Esse padrão é chamado de **wildcard DNS com soft 404**: qualquer subdomínio inexistente resolve para a mesma página raiz. Sem esse filtro, todos os candidatos seriam falsos positivos.

```
Slug inexistente: https://empresa-fake.gupy.io → 302 → https://www.gupy.io (200)  ← descartado
Slug real:        https://nubank.gupy.io        →                          200      ← confirmado
```

O parâmetro `allow_redirects=True` faz o `requests` seguir automaticamente os redirecionamentos e inspecionar a URL final.

No modo `--debug`, cada tentativa é impressa no terminal com origem, destino e status:
```
[debug] https://banco-inter.gupy.io → https://www.gupy.io  status=200
[debug] https://bancointer.gupy.io  → https://bancointer.gupy.io  status=200
```

### 5. Persistência dos resultados

Ao confirmar um subdomínio, o script persiste o resultado em dois lugares de forma imediata:

**No Supabase:**
```python
supabase.table("empresas").update({"gupy_subdominio": slug}).eq("id", empresa["id"]).execute()
```
A coluna `gupy_subdominio` é atualizada na linha da empresa correspondente.

**Em arquivo JSON local (`data/jsons/gupy_empresas/gupy_encontrados.json`):**
O script lê o arquivo existente, extrai o conjunto de IDs já presentes e adiciona apenas registros novos — garantindo que múltiplas execuções não gerem duplicatas no JSON.

### 6. Relatório final

Ao terminar, o script imprime um resumo com a contagem de empresas encontradas versus pendentes e lista as empresas para as quais nenhum candidato foi confirmado, sinalizando a necessidade de revisão manual.

---

## Como Executar

```bash
# Processa todas as empresas sem gupy_subdominio
python descobre_gupy.py

# Com log detalhado de cada requisição HTTP
python descobre_gupy.py --debug
```

---

## Estrutura dos Dados de Saída

### JSON local — `gupy_encontrados.json`

```json
[
  {
    "empresa_id": 42,
    "nome": "Nubank",
    "gupy_subdominio": "nubank",
    "gupy_url": "https://nubank.gupy.io",
    "descoberto_em": "2026-07-02T14:30:00.000000+00:00"
  }
]
```

| Campo | Descrição |
|---|---|
| `empresa_id` | ID da empresa na tabela `empresas` do Supabase |
| `nome` | Nome original da empresa conforme cadastrado no banco |
| `gupy_subdominio` | Slug confirmado (ex: `"nubank"`) |
| `gupy_url` | URL completa da página pública de vagas da empresa |
| `descoberto_em` | Timestamp ISO 8601 com fuso horário UTC de quando foi confirmado |

### Supabase — tabela `empresas`

A coluna `gupy_subdominio` é atualizada diretamente na linha da empresa. Os demais campos da tabela não são alterados por este script.

---

## Pontos de Atenção

**Cobertura dependente de convenção de nomenclatura**
O algoritmo de geração de candidatos é heurístico: parte do nome cadastrado no banco e gera variações previsíveis. Empresas que registraram na Gupy com um nome substancialmente diferente do cadastrado (apelido, marca comercial alternativa, sigla não óbvia) não serão encontradas automaticamente. Nesses casos, o script sinaliza a empresa na seção de revisão manual ao final da execução.

**Dependência do comportamento de redirecionamento da Gupy**
A detecção de subdomínios inválidos depende do comportamento atual da Gupy de redirecionar slugs inexistentes para a página raiz. Se a plataforma alterar essa política — passando a retornar 404 ou a exibir uma página de erro com URL diferente —, o filtro anti-falso-positivo precisará ser atualizado para refletir os novos destinos de redirecionamento.

**Controle de cadência por sleep fixo**
A pausa de 400ms entre requisições (`time.sleep(0.4)`) é um controle preventivo para não sobrecarregar o servidor. Para lotes muito grandes de empresas, o volume acumulado de requisições pode atrair atenção do servidor. Não há rotação de IP ou mecanismo de proxy implementado.

**Ausência de retry em falhas de rede**
Erros de rede transientes — timeout, falha de DNS, conexão recusada — são capturados pela exceção `requests.RequestException` e tratados como `False`, ou seja, o candidato é considerado inexistente. 

**Escopo restrito à confirmação de existência**
O script verifica apenas se o subdomínio existe e retorna status 200. Não realiza autenticação, não acessa dados internos da página e não coleta vagas — essa responsabilidade pertence ao módulo `gupy_vagas/`. O `descobre_gupy.py` é exclusivamente um passo de descoberta e mapeamento.