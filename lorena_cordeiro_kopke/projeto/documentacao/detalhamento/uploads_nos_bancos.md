# Documentação Técnica — upload_empresas.py e upload_nomes_empresas.py

**Localizações:**
- [`src/interacoes_banco/upload_empresas.py`](../../src/interacoes_banco/upload_empresas.py)
- [`src/interacoes_banco/upload_nomes_empresas.py`](../../src/interacoes_banco/upload_nomes_empresas.py)

---

## Visão Geral

Esses dois scripts formam a **etapa de carga inicial do pipeline**. Ambos leem o mesmo arquivo de entrada — `nomes_empresas.json`, produzido pela etapa de coleta — e o persistem no banco de dados Supabase, cada um em uma tabela diferente e com propósitos distintos:

| Script | Tabela destino | O que envia | Chave de conflito |
|---|---|---|---|
| `upload_empresas.py` | `empresas` | Apenas os **nomes únicos** de startups | `nome` |
| `upload_nomes_empresas.py` | `nomes_empresas` | **Todos os artigos completos** (startup + titulo + url + tags) | `url` |

Os dois são executados uma vez por ciclo de coleta, antes das etapas de enriquecimento. A tabela `empresas` resultante serve como **catálogo mestre** do pipeline — todos os módulos subsequentes referenciam seus registros via chave estrangeira (`empresa_id`). A tabela `nomes_empresas` guarda o histórico completo de artigos coletados.

---

## Tecnologias Utilizadas

As duas tecnologias são idênticas nos dois scripts.

### `json` — Biblioteca Padrão Python
Módulo nativo responsável pela leitura e desserialização de arquivos no formato JSON. Converte o conteúdo do arquivo em estruturas de dados nativas do Python (listas e dicionários), permitindo iteração e filtragem dos registros.

### `os` — Biblioteca Padrão Python
Módulo nativo utilizado para acesso às variáveis de ambiente do sistema operacional. As credenciais de conexão ao banco de dados (`SUPABASE_URL` e `SUPABASE_KEY`) são lidas exclusivamente via `os.environ`, mantendo-as fora do código-fonte.

### `pathlib.Path` — Biblioteca Padrão Python
Classe para manipulação de caminhos de arquivo de forma orientada a objetos. A construção `Path(__file__).resolve().parent.parent.parent` resolve dinamicamente o caminho absoluto da raiz do projeto a partir da localização do próprio script, tornando os caminhos independentes do diretório de execução.

### `python-dotenv` (v1.2.2)
Biblioteca externa que lê o arquivo `.env` localizado na raiz do projeto e carrega suas variáveis como variáveis de ambiente do processo. Essa abordagem separa configuração de código e evita que credenciais sejam expostas no repositório.

### `supabase-py` (v2.31.0)
Cliente Python oficial para o Supabase. Abstrai as chamadas à API REST (PostgREST) do projeto, permitindo operações de banco de dados como `upsert`, `select` e `update` por meio de uma interface fluente em Python. Internamente, traduz cada operação em uma requisição HTTP direcionada ao endpoint do projeto Supabase.

> **Supabase** é uma plataforma de banco de dados como serviço (DBaaS) construída sobre PostgreSQL. Expõe a base de dados via API REST gerada automaticamente pelo PostgREST, com autenticação e políticas de acesso configuráveis por tabela.

---

## Arquivo de Entrada (compartilhado)

Ambos os scripts leem o mesmo arquivo:

```
data/jsons/nomes_empresas/nomes_empresas.json
```

Cada elemento da lista segue a estrutura:

```json
{
  "startup": "Nome da Empresa",
  "titulo": "Título do artigo",
  "url": "https://neofeed.com.br/startups/...",
  "tags": []
}
```

---

## Funcionamento do Código

Os dois scripts compartilham os mesmos três primeiros passos de inicialização. A diferença está no que cada um faz com os dados antes de enviá-los ao banco.

### Passo 1 — Inicialização do módulo (idêntico nos dois)

```python
_RAIZ = Path(__file__).resolve().parent.parent.parent
load_dotenv(_RAIZ / ".env")
```

Ao ser importado, o módulo resolve o caminho absoluto da raiz do projeto e carrega as variáveis de ambiente do arquivo `.env`. Esse bloco é executado antes de qualquer chamada à função `upload()`.

### Passo 2 — Conexão com o banco (idêntico nos dois)

```python
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
```

Instancia o cliente Supabase com a URL do projeto e a chave de API. A chave utilizada pode ser a `anon key` (sujeita às políticas de Row-Level Security) ou a `service_role key` (acesso administrativo irrestrito), conforme configurado no `.env`.

### Passo 3 — Leitura do arquivo de entrada (idêntico nos dois)

```python
json_path = _RAIZ / "data" / "jsons" / "nomes_empresas" / "nomes_empresas.json"
with open(json_path, encoding="utf-8") as f:
    dados = json.load(f)
```

Abre e desserializa o JSON gerado pela etapa de coleta. O `encoding="utf-8"` garante a leitura correta de nomes com caracteres especiais.

---

### `upload_empresas.py` — Extração de nomes únicos e carga na tabela `empresas`

#### Passo 4 — Extração e deduplicação de nomes

```python
nomes_unicos = list({item["startup"] for item in dados if item.get("startup")})
registros = [{"nome": nome} for nome in sorted(nomes_unicos)]
```

Utiliza uma *set comprehension* para eliminar automaticamente nomes duplicados — situação comum quando uma mesma startup é mencionada em múltiplos artigos. O filtro `item.get("startup")` descarta entradas com o campo ausente ou nulo. Os registros são ordenados alfabeticamente antes do envio.

#### Passo 5 — Upsert na tabela `empresas`

```python
response = (
    supabase.table("empresas")
    .upsert(registros, on_conflict="nome")
    .execute()
)
```

Envia todos os registros em uma única operação de upsert. O parâmetro `on_conflict="nome"` instrui o PostgreSQL a detectar conflitos pela coluna `nome` (que possui constraint `UNIQUE`) e, em caso de duplicata, manter o registro existente sem modificações. Isso equivale à seguinte instrução SQL:

```sql
INSERT INTO empresas (nome)
VALUES ('Empresa A'), ('Empresa B'), ...
ON CONFLICT (nome) DO UPDATE SET nome = EXCLUDED.nome;
```

| Aspecto | Detalhe |
|---|---|
| **Campo consumido** | `startup` |
| **Campos ignorados** | `titulo`, `url`, `tags` |
| **Tabela de destino** | `empresas` |
| **Campo gravado** | `nome` (text UNIQUE NOT NULL) |

---

### `upload_nomes_empresas.py` — Carga completa dos artigos na tabela `nomes_empresas`

#### Passo 4 — Upsert na tabela `nomes_empresas`

```python
response = (
    supabase.table("nomes_empresas")
    .upsert(dados, on_conflict="url")
    .execute()
)
```

Envia a lista completa de artigos diretamente, sem filtragem ou deduplicação prévia. O parâmetro `on_conflict="url"` instrui o PostgreSQL a usar a coluna `url` como critério de unicidade — se o mesmo artigo for enviado em execuções futuras, ele não será duplicado no banco, apenas atualizado. Isso equivale à seguinte instrução SQL:

```sql
INSERT INTO nomes_empresas (startup, titulo, url, tags)
VALUES ('Kalshi', 'Kalshi pode dobrar...', 'https://...', '[]'),
       ...
ON CONFLICT (url) DO UPDATE
  SET startup = EXCLUDED.startup,
      titulo  = EXCLUDED.titulo,
      tags    = EXCLUDED.tags;
```

| Aspecto | Detalhe |
|---|---|
| **Campos consumidos** | `startup`, `titulo`, `url`, `tags` |
| **Tabela de destino** | `nomes_empresas` |
| **Campos gravados** | `startup`, `titulo`, `url`, `tags` |

---

## Relação com Outros Arquivos

Este par de scripts é a porta de entrada do pipeline a partir do JSON de coleta:

```
[Coleta Neofeed]
      ↓
  nomes_empresas.json
      ↓
  upload_nomes_empresas.py → tabela nomes_empresas (artigos completos)
  upload_empresas.py       → tabela empresas       (catálogo de nomes únicos)
      ↓
  [Módulos de enriquecimento e recomendação — referenciam tabela empresas]
```

O script [`nova_empresa.py`](../../src/nova_empresa.py) utiliza o mesmo mecanismo de upsert para inserir manualmente uma empresa e disparar as etapas de processamento subsequentes.

---

## Pontos de Atenção

**Volume de registros por requisição**
Todos os registros são enviados ao Supabase em uma única requisição HTTP, sem paginação ou divisão em lotes. Para volumes muito elevados de startups, essa abordagem pode atingir limites de tamanho de payload da API REST.

**Carregamento de credenciais em nível de módulo**
A chamada `load_dotenv()` é executada no momento em que o módulo é importado. Caso o arquivo `.env` esteja ausente ou com variáveis incompletas, a ausência das credenciais será percebida somente quando a função `create_client()` for chamada, o que pode dificultar o diagnóstico do problema.

**Caminho do arquivo de entrada fixo no código**
O caminho para `nomes_empresas.json` é definido diretamente no código. Caso o arquivo não exista no local esperado, o script falhará com `FileNotFoundError`, sem possibilidade de configuração alternativa por parâmetro ou variável de ambiente.
