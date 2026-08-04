# Documentação Técnica — `coleta_neofeed.py`

## 1. Visão Geral

O módulo `coleta_neofeed.py` é responsável pela **primeira etapa do pipeline de coleta de dados** do projeto. Sua função é realizar a extração automatizada (*web scraping*) de artigos publicados na seção de startups do portal de notícias **Neofeed** (`https://neofeed.com.br/startups/`), salvando os dados brutos em um arquivo JSON para consumo pelas etapas subsequentes do sistema.

O módulo opera de forma isolada e deliberadamente não realiza nenhum tipo de processamento, filtragem ou extração semântica sobre os dados coletados. Essa separação é intencional: como a coleta exige a abertura de um navegador e depende da disponibilidade do site externo, ela é classificada como uma operação custosa, devendo ser reexecutada apenas quando novos dados são necessários.

---

## 2. Localização no Projeto

```
src/
└── coleta_startups/
    └── coleta_neofeed.py
```

**Arquivo de saída padrão:**
```
data/jsons/artigos_nomes_empresas/artigos_brutos.json
```

---

## 3. Tecnologias e Dependências

### 3.1 Bibliotecas externas

| Biblioteca | Versão mínima | Finalidade |
|---|---|---|
| `playwright` | — | Automação de navegador para interação com páginas que carregam conteúdo via JavaScript |

### 3.2 Bibliotecas padrão do Python

| Módulo | Finalidade |
|---|---|
| `json` | Serialização e escrita dos dados coletados no formato JSON |
| `os` | Leitura de variáveis de ambiente do sistema operacional |
| `sys` | Leitura de argumentos passados via linha de comando |
| `pathlib.Path` | Manipulação de caminhos de arquivos e diretórios de forma multiplataforma |

### 3.3 Navegador

O módulo utiliza o **Chromium** — base open-source do Google Chrome — controlado via Playwright. A função interna `_chromium_executable()` localiza o executável instalado pelo Playwright no ambiente Windows (`LOCALAPPDATA/ms-playwright/`), tentando primeiro a versão *headless shell* (mais leve, sem interface gráfica) e, como alternativa, a versão completa do navegador.

---

## 4. Justificativa para o Uso de Playwright

O Neofeed renderiza seu conteúdo de forma **dinâmica via JavaScript (AJAX)**: os artigos não estão presentes no HTML inicial retornado pelo servidor, sendo carregados progressivamente conforme o usuário interage com a página. Isso torna inviável o uso de bibliotecas de requisição HTTP simples, como `requests`, pois estas obtêm apenas o HTML estático e não executam o JavaScript da página.

O Playwright resolve esse problema controlando um navegador real, que executa todo o JavaScript da página assim como faria um usuário humano, tornando o conteúdo dinâmico acessível para extração.

---

## 5. Funcionamento Detalhado

### 5.1 Fluxo de execução

```
Abertura do Chromium
        ↓
Navegação até neofeed.com.br/startups/
        ↓
Aguarda carregamento dos artigos iniciais
        ↓
Cliques repetidos em "Carregar mais" (paginação dinâmica)
        ↓
Execução de JavaScript para extração dos dados de cada artigo
        ↓
Fechamento do navegador
        ↓
Persistência dos dados em arquivo JSON
```

### 5.2 Descrição das funções

#### `_chromium_executable() → str | None`

Localiza o executável do Chromium instalado pelo Playwright no sistema Windows. Verifica dois caminhos possíveis dentro de `%LOCALAPPDATA%/ms-playwright/`:
- `chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe`
- `chromium-*/chrome-win64/chrome.exe`

Retorna o caminho do executável encontrado ou `None`, caso em que o Playwright utiliza sua resolução interna padrão.

---

#### `contar_artigos(page) → int`

Conta o número de elementos `<article>` presentes no DOM da página no momento da chamada. Utilizado como referência para detectar se novos artigos foram carregados após um clique em "Carregar mais".

---

#### `carregar_mais_artigos(page, cliques_max: int = 10) → int`

Automatiza a expansão da listagem de artigos por meio de cliques successivos no botão "Carregar mais". A cada clique, aguarda que a contagem de `<article>` no DOM supere o valor anterior (timeout de 8 segundos). O processo encerra quando:
- O botão deixa de estar presente na página (sem mais artigos disponíveis), ou
- O número máximo de cliques (`cliques_max`) é atingido, ou
- O botão não responde dentro do tempo limite.

O parâmetro `cliques_max` controla diretamente o volume de histórico coletado: valores maiores resultam em mais artigos, porém aumentam o tempo de execução.

---

#### `coletar(cliques_max: int = 3, caminho_saida: str = _SAIDA_PADRAO) → list[dict]`

Função principal do módulo. Orquestra todas as etapas da coleta:

1. Inicializa o Playwright e abre o Chromium
2. Navega até `URL_BASE` com timeout de 60 segundos
3. Aguarda o aparecimento de pelo menos um `<article>` (timeout de 30 segundos)
4. Chama `carregar_mais_artigos` para expandir a listagem
5. Executa JavaScript diretamente no contexto do navegador para extrair os dados de todos os artigos visíveis
6. Encerra o navegador
7. Cria o diretório de saída caso não exista
8. Persiste os dados no arquivo JSON indicado por `caminho_saida`
9. Retorna a lista de artigos como estrutura Python

---

## 6. Dados Coletados

Para cada artigo encontrado na página, são extraídos os seguintes campos:

| Campo | Tipo | Descrição |
|---|---|---|
| `titulo` | `string` | Texto do elemento de cabeçalho do artigo (`<h2>` ou `<h3>`) |
| `url` | `string` | URL absoluta para o artigo completo no Neofeed |
| `tags` | `list[string]` | Lista de categorias/etiquetas associadas ao artigo, normalizadas para letras minúsculas |

### Exemplo de estrutura do arquivo de saída

```json
[
  {
    "titulo": "Startup XYZ capta R$ 50 milhões em rodada Série B",
    "url": "https://neofeed.com.br/startups/startup-xyz-capta-r-50-milhoes/",
    "tags": ["fintech", "startup", "investimento"]
  },
  {
    "titulo": "Como a empresa ABC está transformando o agronegócio com IA",
    "url": "https://neofeed.com.br/startups/empresa-abc-agronegocio-ia/",
    "tags": ["agronegócio", "inteligência artificial", "startup"]
  }
]
```

A extração dos campos é realizada via JavaScript executado no contexto do navegador, inspecionando a estrutura HTML de cada elemento `<article>`:
- **Título**: extraído do primeiro `<h2>` ou `<h3>` encontrado dentro do artigo
- **URL**: obtida do atributo `href` do elemento `<a>` contido no cabeçalho ou mais próximo a ele
- **Tags**: coletadas de elementos `<a>` com atributo `rel="tag"` ou pertencentes às classes `.tag-links` e `.cat-links`

---

## 7. Como Executar

### Via linha de comando

```bash
# Execução padrão (10 cliques em "Carregar mais", saída no caminho padrão)
python src/coleta_startups/coleta_neofeed.py

# Com número de cliques customizado
python src/coleta_startups/coleta_neofeed.py 5

# Com número de cliques e caminho de saída customizados
python src/coleta_startups/coleta_neofeed.py 5 data/jsons/minha_saida.json
```

### Via importação em outro módulo

```python
from src.coleta_startups.coleta_neofeed import coletar

artigos = coletar(cliques_max=5)
# artigos é uma lista de dicionários com os campos: titulo, url, tags
```

---

## 8. Considerações e Limitações

| Aspecto | Descrição |
|---|---|
| **Dependência de disponibilidade externa** | A coleta depende integralmente do Neofeed estar acessível. Qualquer instabilidade ou indisponibilidade do site resultará em falha ou coleta parcial. |
| **Fragilidade estrutural** | Alterações no HTML do Neofeed (mudança de classes CSS, reestruturação de elementos) podem quebrar a extração silenciosamente, gerando dados incompletos ou vazios. |
| **Compatibilidade de plataforma** | A função `_chromium_executable()` referencia a variável de ambiente `LOCALAPPDATA`, específica do Windows. Em sistemas macOS e Linux, o Playwright localiza o Chromium por seus próprios mecanismos, portanto essa função retornará `None` nesses ambientes sem impacto funcional. |
| **Volume de dados e desempenho** | O tempo de execução cresce proporcionalmente ao valor de `cliques_max`. Valores elevados (acima de 20) podem resultar em execuções longas e maior risco de timeout. |
| **Dados não filtrados** | O módulo salva todos os artigos encontrados sem qualquer critério de relevância. A filtragem e o enriquecimento dos dados são responsabilidade das etapas seguintes do pipeline. |