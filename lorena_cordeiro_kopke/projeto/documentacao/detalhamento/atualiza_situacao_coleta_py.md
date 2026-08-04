# Documentação Técnica — `atualiza_situacao_coleta.py`

## Visão Geral

O `atualiza_situacao_coleta.py` é o módulo responsável por **sincronizar o campo `situacao_coleta`** da tabela `empresas_uso_ia` com o estado real dos dados de cada empresa no banco. Sua responsabilidade não é coletar nem enriquecer informações — essas tarefas são executadas pelos scripts anteriores do pipeline —, mas sim **inspecionar, auditar e corrigir** a etiqueta de status que indica se uma empresa está com seus dados completos ou não.

O módulo opera sobre a tabela `empresas_uso_ia` do Supabase. Para cada empresa, ele verifica se todos os **22 campos obrigatórios** estão preenchidos e, com base nessa verificação, decide se o status da empresa precisa ser promovido para `'completo'`, revertido para `'informação pendente'`, ou mantido como está. Empresas marcadas incorretamente como `'completo'` mas com campos faltando são identificadas e sinalizadas como inconsistências — o script as reverte automaticamente.

O resultado é um banco de dados sempre consistente: o campo `situacao_coleta` reflete com precisão o estado real dos dados, o que é fundamental para que a etapa seguinte do pipeline — a geração de recomendações para a NVIDIA — opere apenas sobre empresas verdadeiramente completas.

---

## Posição no Pipeline

```
inicia_aprofundamento.py ──→ empresas_uso_ia (seed de aprovadas) ──→ atualiza_situacao_coleta.py ──→ empresas_uso_ia (situacao_coleta atualizada)
```

O `atualiza_situacao_coleta.py` é a **etapa 13 de 14** do pipeline principal orquestrado pelo `app.py`:

| Etapa | Script | O que faz |
|---|---|---|
| 1 | `coleta_neofeed.py` | Raspa artigos brutos do NeoFeed |
| 2 | `filtro.py` | Extrai nomes de startups dos artigos |
| 3 | `upload_nomes_empresas.py` | Envia nomes brutos para o Supabase |
| 4 | `upload_empresas.py` | Envia empresas para a tabela `empresas` no Supabase |
| 5 | `descobre_dominio.py` | Descobre o domínio do site de cada empresa |
| 6 | `descobre_gupy.py` | Descobre subdomínio Gupy de cada empresa |
| 7 | `descobre_gupy_vagas.py` | Pesquisa vagas de IA no Gupy |
| 8 | `descobre_institucional.py` | Analisa o site institucional com LLM |
| 9 | `descobre_imprensa.py` | Busca notícias de IA via News API |
| 10 | `analisa_neofeed.py` | Classifica artigos NeoFeed quanto à menção de IA |
| 11 | `filtro_ia.py` | Avalia sinais e emite veredito de uso de IA |
| 12 | `inicia_aprofundamento.py` | Cria linhas em `empresas_uso_ia` para empresas aprovadas |
| **13** | **`atualiza_situacao_coleta.py`** | **Audita e atualiza o campo `situacao_coleta`** |
| 14 | `inicia_recomendacao.py` | Gera recomendações de tecnologias NVIDIA via LangGraph |

Além do pipeline principal, o módulo também é chamado diretamente em outros dois contextos:

- **`define_maturidade.py`** — após calcular o score e o nível de maturidade de IA da empresa, chama `atualizar()` para que o novo preenchimento dos campos `score_maturidade_ia` e `nivel_maturidade_ia` seja refletido imediatamente no `situacao_coleta`
- **`reprocessa_empresa.py`** — ao reprocessar manualmente uma empresa específica, chama `define_maturidade` ao final, que por sua vez aciona `atualizar()`

---

## Tecnologias Utilizadas

### Linguagem

**Python 3.9+**

A declaração `from __future__ import annotations` no topo do arquivo ativa avaliação *lazy* de *type hints*, permitindo escrever anotações de tipo como `frozenset[str]` sem erro de runtime em versões anteriores ao Python 3.10.

---

### Biblioteca padrão do Python

| Módulo | Uso no código |
|---|---|
| `os` | Acesso às variáveis de ambiente `SUPABASE_URL` e `SUPABASE_KEY` via `os.environ` após o carregamento do `.env` |
| `pathlib.Path` | Localiza a raiz do projeto subindo três níveis a partir do arquivo atual, de forma portável e sem *hardcode* de caminhos absolutos |

**Sobre `frozenset`:**

`frozenset` é uma estrutura de dados nativa do Python — um conjunto imutável e sem ordem. É usada para armazenar os 22 campos obrigatórios (`CAMPOS_COMPLETO`) por dois motivos práticos: a imutabilidade impede modificações acidentais durante a execução, e a operação de **união** (`|`) entre dois `frozenset`s permite montar a lista de campos da query de forma concisa — `CAMPOS_COMPLETO | {"empresa_id", "situacao_coleta"}` — sem duplicatas e sem loops adicionais.

---

### Bibliotecas de terceiros

#### `python-dotenv`

Carrega variáveis de ambiente a partir do arquivo `.env` localizado na raiz do projeto. Provê as credenciais `SUPABASE_URL` e `SUPABASE_KEY` sem expô-las no código-fonte.

#### `supabase-py`

Cliente Python oficial do **Supabase** (banco de dados PostgreSQL gerenciado na nuvem). Utilizado em dois momentos distintos ao longo da execução: para **ler** todos os registros de `empresas_uso_ia` com os campos obrigatórios e o status atual, e para **gravar** as atualizações de `situacao_coleta` empresa a empresa.

---

## Funcionamento Detalhado

### 1. Inicialização

O módulo resolve a raiz do projeto subindo três níveis a partir de sua localização (`Path(__file__).resolve().parent.parent.parent`) e carrega as variáveis de ambiente do `.env`. O cliente Supabase é criado dentro da função `atualizar()` a cada execução, garantindo que as credenciais sejam sempre lidas do ambiente no momento da chamada.

### 2. Definição dos campos obrigatórios — `CAMPOS_COMPLETO`

```python
CAMPOS_COMPLETO: frozenset[str] = frozenset({
    "cnpj", "cnpj_pendente", "dominio", "razao_social", "situacao_rf",
    "municipio", "uf", "cnae_principal", "porte", "capital_social",
    "natureza_juridica", "produto", "modelo_negocio", "mercado_alvo",
    "setor", "uso_ia_descricao", "ia_e_core_product", "ia_tipo",
    "ano_fundacao", "produto_ia_lancado",
    "score_maturidade_ia", "nivel_maturidade_ia",
})
```

São **22 campos** que, juntos, definem uma empresa como "completa". Estão organizados em três categorias:

| Categoria | Campos |
|---|---|
| Dados da Receita Federal | `cnpj`, `cnpj_pendente`, `razao_social`, `situacao_rf`, `municipio`, `uf`, `cnae_principal`, `porte`, `capital_social`, `natureza_juridica` |
| Dados de uso de IA (preenchidos por LLM) | `dominio`, `produto`, `modelo_negocio`, `mercado_alvo`, `setor`, `uso_ia_descricao`, `ia_e_core_product`, `ia_tipo`, `ano_fundacao`, `produto_ia_lancado` |
| Dados calculados por `define_maturidade.py` | `score_maturidade_ia`, `nivel_maturidade_ia` |

Campos como `fonte_dados`, `programa_aceleracao` e `nome_fantasia` são **intencionalmente excluídos** da obrigatoriedade por serem considerados opcionais no contexto do pipeline.

### 3. Consulta ao banco

```python
campos_select = ", ".join(CAMPOS_COMPLETO | {"empresa_id", "situacao_coleta"})
todas = supabase.table("empresas_uso_ia").select(campos_select).execute().data
```

A query monta a lista de colunas unindo os 22 campos obrigatórios com `empresa_id` (chave primária, necessária para o update posterior) e `situacao_coleta` (o valor atual a ser auditado). Busca **todas** as empresas da tabela em uma única requisição.

### 4. Classificação de cada empresa

Para cada empresa retornada, o script executa duas verificações independentes:

```python
faltando = [c for c in CAMPOS_COMPLETO if emp.get(c) is None]
```

Essa linha lista todos os campos obrigatórios cujo valor é `None` (nulo no banco) para aquela empresa. Com base no resultado, três situações são possíveis:

| Condição | Ação |
|---|---|
| Nenhum campo faltando + `situacao_coleta` ≠ `'completo'` | **Promover** — empresa entra na lista `promover` |
| Campo(s) faltando + `situacao_coleta` = `'completo'` | **Regredir** — inconsistência detectada, empresa entra na lista `regredir`, aviso impresso no terminal |
| Campo(s) faltando + `situacao_coleta` = `'informação pendente'` ou `None` | **Sem alteração** — apenas imprime quais campos estão faltando |

Ao final do loop, o script exibe um resumo no terminal:

```
[situacao_coleta] 3 promovida(s) para 'completo' | 1 revertida(s) para 'informação pendente' | 42 sem alteração
```

### 5. Aplicação das mudanças no banco

As atualizações são enviadas em sequência, **uma por empresa**, alterando apenas o campo `situacao_coleta`:

```python
for eid in promover:
    supabase.table("empresas_uso_ia").update(
        {"situacao_coleta": "completo"}
    ).eq("empresa_id", eid).execute()

for eid in regredir:
    supabase.table("empresas_uso_ia").update(
        {"situacao_coleta": "informação pendente"}
    ).eq("empresa_id", eid).execute()
```

Nenhum outro campo da tabela é tocado durante esse processo.

### 6. Parâmetro `atualizar_banco`

A função `atualizar()` aceita o parâmetro `atualizar_banco: bool = True`. Quando chamado com `atualizar_banco=False`, o script executa toda a análise e imprime o relatório completo no terminal — incluindo quais empresas seriam promovidas ou revertidas — mas **não envia nenhuma alteração ao banco**. Esse modo é útil para diagnóstico e auditoria sem efeito colateral.

---

## Os Valores de `situacao_coleta` no Sistema

O campo `situacao_coleta` pode assumir quatro valores distintos ao longo do pipeline. O `atualiza_situacao_coleta.py` gerencia diretamente dois deles; os outros dois são definidos por intervenção manual via `atualiza_status.py`:

| Valor | Definido por | Significado |
|---|---|---|
| `'completo'` | `atualiza_situacao_coleta.py` | Todos os 22 campos obrigatórios estão preenchidos |
| `'informação pendente'` | `atualiza_situacao_coleta.py`, `inicia_aprofundamento.py` | Um ou mais campos obrigatórios estão nulos |
| `'seguir para próxima fase apesar de incompleto'` | `atualiza_status.py` (intervenção manual) | Operador decidiu que a empresa avança mesmo incompleta |
| `'empresa deve ser ignorada'` | `atualiza_status.py` (intervenção manual) | Operador descartou a empresa manualmente |

Os dois últimos valores, definidos manualmente, são **preservados** por este script: uma empresa marcada como `'empresa deve ser ignorada'` não será promovida para `'completo'` mesmo que todos os seus campos estejam preenchidos, respeitando a decisão humana registrada.

O módulo `verifica_situacao_coleta.py`, que opera na etapa de recomendação, trata os valores `'completo'` e `'seguir para próxima fase apesar de incompleto'` como **elegíveis** para avançar no pipeline, e os demais como bloqueantes.

---

## Dados Acessados na Tabela `empresas_uso_ia`

O script lê os seguintes campos de cada empresa para realizar a auditoria:

### Dados da Receita Federal

| Campo | Descrição |
|---|---|
| `cnpj` | CNPJ principal da empresa |
| `cnpj_pendente` | Indicação de pendência no cadastro do CNPJ |
| `razao_social` | Razão social oficial registrada na Receita Federal |
| `situacao_rf` | Situação cadastral (ativa, inapta, baixada, etc.) |
| `municipio` | Município sede da empresa |
| `uf` | Unidade federativa (estado) |
| `cnae_principal` | Classificação Nacional de Atividades Econômicas principal |
| `porte` | Porte da empresa (MEI, EPP, Média, Grande) |
| `capital_social` | Capital social declarado na Receita Federal |
| `natureza_juridica` | Tipo jurídico (SA, Ltda, etc.) |

### Dados de Uso de IA

| Campo | Descrição |
|---|---|
| `dominio` | Domínio do site institucional da empresa |
| `produto` | Descrição do produto ou serviço principal |
| `modelo_negocio` | Modelo de negócio (B2B, B2C, B2B2C, etc.) |
| `mercado_alvo` | Segmento de mercado atendido |
| `setor` | Setor de atuação |
| `uso_ia_descricao` | Descrição textual de como a empresa utiliza IA |
| `ia_e_core_product` | Booleano: IA é o produto principal? |
| `ia_tipo` | Tipo de IA utilizada (Generativa, NLP/LLM, Visão Computacional, etc.) |
| `ano_fundacao` | Ano de fundação da empresa |
| `produto_ia_lancado` | Booleano: a empresa já lançou um produto com IA? |

### Dados Calculados por `define_maturidade.py`

| Campo | Descrição |
|---|---|
| `score_maturidade_ia` | Pontuação numérica de maturidade em IA |
| `nivel_maturidade_ia` | Nível em texto derivado do score (ex: "Avançado", "Iniciante") |

### Campos de Controle

| Campo | Modo de acesso | Descrição |
|---|---|---|
| `empresa_id` | Leitura | Chave primária — usada para identificar a empresa nos updates |
| `situacao_coleta` | Leitura e escrita | Único campo que este script pode modificar |