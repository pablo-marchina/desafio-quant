# Documentação Técnica — `descobre_gupy_vagas.py`

## Visão Geral

O `descobre_gupy_vagas.py` é um módulo de coleta de sinais de IA do projeto. Sua responsabilidade é visitar automaticamente a página de vagas abertas de cada empresa monitorada na plataforma **Gupy** e identificar se há contratações para posições relacionadas a inteligência artificial, dados ou automação inteligente.

O Gupy é uma plataforma brasileira de recrutamento e seleção. Empresas que a utilizam recebem uma página de vagas no formato `https://[subdominio].gupy.io`. Ao detectar termos de IA no título ou departamento de uma vaga, o módulo registra um **sinal positivo** para aquela empresa. Quando nenhuma vaga relevante é encontrada, registra um **sinal negativo** — indicando que a empresa foi verificada, não ignorada.

Os resultados são gravados na tabela `sinais_ia` do Supabase com a camada identificada como `gupy_vagas`, e também persistidos localmente em arquivo JSON para consulta e auditoria.

---

## Posição no Pipeline

```
Supabase (tabela empresas)
    → descobre_gupy_vagas.py     [coleta de vagas + detecção de termos de IA]
        → Supabase (tabela sinais_ia, camada "gupy_vagas")
        → data/jsons/gupy_vagas/gupy_vagas_ia.json
```

O módulo é uma das quatro camadas de detecção de sinais de IA do projeto:

| Camada | Script | Fonte |
|---|---|---|
| `institucional` | `descobre_institucional.py` | Site oficial da empresa |
| `imprensa` | `descobre_imprensa.py` | Notícias na internet |
| `gupy_vagas` | **este script** | Vagas de emprego no Gupy |
| `neofeed` | `analisa_neofeed.py` | Notícias do portal NeoFeed |

---

## Tecnologias Utilizadas

### Linguagem

**Python 3.10+**
A anotação `str | None` e o uso de `from __future__ import annotations` requerem Python moderno. O `__future__` ativa avaliação lazy de type hints, permitindo anotações de tipo sem erro de runtime em versões anteriores ao 3.10.

---

### Biblioteca padrão do Python

| Módulo | Uso no código |
|---|---|
| `json` | Parsear o bloco `__NEXT_DATA__` extraído do HTML e serializar o arquivo JSON de saída |
| `os` | Acesso às variáveis de ambiente `SUPABASE_URL` e `SUPABASE_KEY` |
| `re` | Expressão regular para localizar e extrair o bloco `__NEXT_DATA__` dentro do HTML da página |
| `time` | `time.sleep(1)` — pausa de 1 segundo entre requisições para não sobrecarregar os servidores do Gupy |
| `datetime` / `timezone` | Registro do timestamp UTC exato em que cada vaga foi coletada |
| `pathlib.Path` | Manipulação de caminhos de arquivo de forma orientada a objetos e multiplataforma |
| `sys` | Leitura do argumento `--debug` de linha de comando via `sys.argv` |

**Sobre o módulo `re` (regex):**
O módulo `re` implementa **expressões regulares** — um mecanismo de busca textual por padrões, em vez de palavras exatas. Neste script, ele é utilizado para localizar especificamente o trecho `<script id="__NEXT_DATA__" type="application/json">...</script>` no HTML da página do Gupy, extraindo apenas o conteúdo JSON interno. A flag `re.DOTALL` é necessária para que o `.` (ponto) no padrão corresponda também a quebras de linha, já que o JSON embutido pode se estender por múltiplas linhas.

---

### Bibliotecas de terceiros

#### `requests`
Biblioteca HTTP para Python, utilizada para realizar as requisições GET às páginas do Gupy. O script instancia um objeto `requests.Session()` — uma sessão reutilizável que mantém a conexão TCP aberta entre requisições ao mesmo host, mais eficiente do que chamadas isoladas. A sessão é configurada com um **User-Agent falso de navegador Chrome no Windows**, necessário porque muitos servidores web bloqueiam automaticamente requisições com User-Agent padrão de scripts Python.

#### `python-dotenv`
Carrega variáveis de ambiente a partir do arquivo `.env` localizado na raiz do projeto. Provê as credenciais `SUPABASE_URL` e `SUPABASE_KEY` sem expô-las no código-fonte.

#### `supabase-py`
Cliente Python oficial do **Supabase** (banco de dados PostgreSQL gerenciado na nuvem). Utilizado em dois momentos: para **ler** a lista de empresas com `gupy_subdominio` cadastrado (tabela `empresas`) e para **gravar** os sinais detectados (tabela `sinais_ia`).

---

## Funcionamento Detalhado

### 1. Inicialização

O módulo resolve a raiz do projeto subindo três níveis a partir de sua localização (`Path(__file__).resolve().parent.parent.parent`) e carrega as variáveis de ambiente do `.env`. Em seguida, instancia a sessão HTTP com o User-Agent de navegador e cria a conexão com o Supabase.

### 2. Lista de termos de IA

Uma lista estática com aproximadamente 50 termos é definida diretamente no código, organizada em cinco categorias:

- **IA/ML genérico:** `inteligência artificial`, `machine learning`, `deep learning`, `llm`, `nlp`, `visão computacional`, `reinforcement learning`, `generative ai`, `foundation model`, entre outros
- **Dados:** `data science`, `data scientist`, `engenheiro de dados`, `analytics`, `big data`, `dbt`, `airflow`, `spark`, `data lake`, `data warehouse`, entre outros
- **Automação e produto:** `rpa`, `process mining`, `fraud detection`, `forecast`, `scoring`, `recomendação`, entre outros
- **Infraestrutura de ML:** `mlflow`, `kubeflow`, `sagemaker`, `vertex ai`, `databricks`, `feature store`, entre outros
- **Abreviações curtas com espaço:** ` ia `, ` ai `, ` ml `, ` bi ` — os espaços ao redor são intencionais para evitar falsos positivos em palavras que contenham essas sequências de letras (ex.: "feira", "email")

### 3. Busca de vagas — `_buscar_vagas()`

Esta é a etapa técnica central. O Gupy é construído com **Next.js**, um framework React para renderização no servidor (SSR — *Server-Side Rendering*). Uma característica de páginas Next.js é embutir no HTML um bloco JSON chamado `__NEXT_DATA__`:

```html
<script id="__NEXT_DATA__" type="application/json">
  {"props": {"pageProps": {"jobs": [...]}}}
</script>
```

Esse bloco contém todos os dados que o React utiliza para renderizar a página, incluindo a **lista completa de vagas abertas**. O script:

1. Faz um GET em `https://[subdominio].gupy.io`
2. Usa regex para extrair o conteúdo do `<script id="__NEXT_DATA__">`
3. Executa `json.loads()` sobre esse conteúdo
4. Navega no caminho `props → pageProps → jobs` para obter a lista de vagas
5. Retorna essa lista

Essa abordagem não requer autenticação, não simula navegador completo (como Playwright faria) e não depende de APIs privadas do Gupy — apenas lê o HTML estático que o servidor já entrega publicamente.

### 4. Busca no Supabase e loop principal — `pesquisar()`

**Consulta inicial:** o módulo busca na tabela `empresas` apenas os registros que possuem `gupy_subdominio` preenchido — ou seja, empresas para as quais já foi identificado anteriormente que utilizam o Gupy. O parâmetro opcional `nome` permite filtrar para uma única empresa durante testes.

**Para cada empresa:**
1. Chama `_buscar_vagas()` para obter todas as vagas abertas
2. Para cada vaga, concatena o campo `title` e `department` em um único texto e executa `_contem_termo_ia()`
3. `_contem_termo_ia()` percorre a lista de termos e retorna o **primeiro termo encontrado** (busca case-insensitive via `.lower()`), ou `None` se nenhum termo for encontrado

**Se houver vagas com sinal de IA:**
- Insere **um registro por vaga** na tabela `sinais_ia` com `encontrado=True`, o título da vaga como evidência e a URL direta para a vaga
- Adiciona os registros à lista de saída local

**Se não houver vagas com sinal de IA:**
- Insere **um único registro** na tabela `sinais_ia` com `encontrado=False` — isso garante que a empresa seja marcada como verificada, e não como pendente
- Adiciona um registro de resultado negativo à lista de saída local

**Pausa entre empresas:** `time.sleep(1)` aguarda 1 segundo entre cada empresa processada.

### 5. Persistência local em JSON

Ao final, o módulo grava os resultados em `data/jsons/gupy_vagas/gupy_vagas_ia.json`. A escrita é **incremental com deduplicação por URL**: se o arquivo já existir, o módulo carrega os registros anteriores e adiciona apenas os novos — registros cuja `fonte_url` ainda não esteja presente no arquivo.

---

## Estrutura dos Dados de Saída

Cada registro no arquivo JSON e na tabela `sinais_ia` segue o formato abaixo.

**Registro com sinal positivo (vaga de IA encontrada):**

```json
{
  "empresa_id": 35,
  "nome_empresa": "Asaas",
  "titulo_vaga": "Analista de Governança de Dados e IA Sênior",
  "departamento": "Tecnologia",
  "fonte_url": "https://asaas.gupy.io/job/11496762",
  "termo_encontrado": "dados",
  "encontrado": true,
  "coletado_em": "2026-06-25T11:26:24.244585+00:00"
}
```

**Registro com sinal negativo (empresa verificada, sem vaga de IA):**

```json
{
  "empresa_id": 41,
  "nome_empresa": "DNA Capital",
  "titulo_vaga": null,
  "departamento": null,
  "fonte_url": "https://dna.gupy.io",
  "termo_encontrado": null,
  "encontrado": false,
  "coletado_em": "2026-06-25T11:26:26.707478+00:00"
}
```

| Campo | Descrição |
|---|---|
| `empresa_id` | Chave estrangeira referenciando a tabela `empresas` no Supabase |
| `nome_empresa` | Nome da empresa conforme cadastrado no Supabase |
| `titulo_vaga` | Título da vaga conforme retornado pelo Gupy; `null` em registros negativos |
| `departamento` | Departamento da vaga conforme retornado pelo Gupy; `null` em registros negativos |
| `fonte_url` | URL direta da vaga (`/job/[id]`) em positivos; URL da página principal do Gupy em negativos |
| `termo_encontrado` | Primeiro termo da lista `_TERMOS_IA` encontrado no texto; `null` em registros negativos |
| `encontrado` | `true` se há sinal de IA; `false` se a empresa foi verificada sem resultado |
| `coletado_em` | Timestamp UTC do momento da coleta no formato ISO 8601 |

---

## Pontos de Atenção

**Dependência da estrutura `__NEXT_DATA__` do Gupy**
O script depende de que o Gupy continue utilizando Next.js com o bloco `__NEXT_DATA__` embutido no HTML. Se a plataforma migrar para outro framework ou passar a carregar as vagas via API assíncrona (requisições feitas pelo navegador após o carregamento da página), o script retornará listas vazias.

**Cobertura restrita ao título e departamento**
A detecção de termos de IA analisa apenas os campos `title` e `department` das vagas. A descrição completa da vaga não está disponível no bloco `__NEXT_DATA__` da listagem e não é coletada por este módulo.

**Escopo limitado a empresas no Gupy**
O módulo só processa empresas que utilizam o Gupy como plataforma de vagas e que já tiveram o `gupy_subdominio` identificado e cadastrado no Supabase por um script anterior. Empresas que publicam vagas no LinkedIn, Workable, Lever, ou no próprio site, ficam fora do escopo deste módulo.