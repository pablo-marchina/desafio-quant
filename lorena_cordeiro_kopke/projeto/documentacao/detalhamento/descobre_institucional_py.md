# Documentação Técnica — `descobre_institucional.py`

## Visão Geral

O `descobre_institucional.py` é o módulo responsável pela **camada institucional** do pipeline de classificação de startups por uso de IA. Sua função é visitar os sites oficiais de cada empresa cadastrada no banco de dados e determinar, de forma automatizada, se aquela empresa utiliza Inteligência Artificial de forma técnica e substantiva — não apenas como linguagem de marketing.

O módulo implementa um sistema de pontuação baseado em dois conjuntos de sinais linguísticos: termos técnicos específicos de ML/IA (peso alto) e termos genéricos e amplos (peso baixo). Uma empresa só é marcada como positiva quando a pontuação acumulada nas páginas visitadas atinge um limiar mínimo, o que reduz falsos positivos causados por texto de marketing superficial.

Para acessar as páginas, o módulo opera com dois motores: requisições HTTP diretas via `requests` (modo leve, padrão) e renderização com browser real via `Playwright` (acionado apenas quando o site é detectado como dependente de JavaScript). Isso equilibra velocidade e capacidade de cobertura.

Os resultados são gravados simultaneamente no banco de dados Supabase (tabela `sinais_ia`) e em um arquivo JSON local de backup.

---

## Posição no Pipeline

```
Supabase — tabela empresas
    (empresas com dominio preenchido)
        → descobre_institucional.py     [raspagem dos sites institucionais]
            → Supabase (tabela sinais_ia, camada 'institucional')
            → data/jsons/institucional/institucional.json
```

O módulo é uma das quatro camadas de detecção de sinais de IA do projeto:

| Camada | Script | Fonte |
|---|---|---|
| `institucional` | **este script** | Site oficial da empresa |
| `imprensa` | `descobre_imprensa.py` | Notícias na internet |
| `gupy_vagas` | `descobre_gupy_vagas.py` | Vagas de emprego no Gupy |
| `neofeed` | `analisa_neofeed.py` | Notícias do portal NeoFeed |


---

## Tecnologias Utilizadas

### Linguagem

**Python 3.9+**
O uso de `from __future__ import annotations` ativa a avaliação lazy de type hints, permitindo anotações como `str | None` sem erros de runtime em versões anteriores ao 3.10.

---

### Biblioteca padrão do Python

| Módulo | Uso no código |
|---|---|
| `json` | Leitura e escrita do arquivo JSON local de backup |
| `os` | Acesso às variáveis de ambiente `SUPABASE_URL` e `SUPABASE_KEY` |
| `time` | Pausas entre requisições e medição de tempo total por domínio (timeout de 90s) |
| `datetime` / `timezone` | Marcação do timestamp UTC de coleta em cada registro |
| `pathlib.Path` | Manipulação de caminhos de arquivo de forma multiplataforma |

---

### Bibliotecas de terceiros

#### `requests`
Biblioteca HTTP para Python. Usada como motor principal de download de páginas. O módulo cria uma `Session` reutilizável (objeto `_SESSION`) com `User-Agent` configurado para imitar um browser Chrome real — prática necessária porque muitos servidores bloqueiam requisições com User-Agent padrão de bibliotecas HTTP. A sessão reutilizável mantém conexões TCP abertas entre requisições para o mesmo domínio, o que reduz a latência.

#### `BeautifulSoup` (`bs4`)
Biblioteca de análise e extração de conteúdo HTML. Após o download de cada página, o BeautifulSoup faz o parse do HTML e extrai apenas o texto visível, descartando tags `<script>`, `<style>`, `<nav>`, `<footer>` e `<header>`. O resultado é uma string de texto limpo e normalizado, sem marcação HTML, sobre a qual os sinais linguísticos são buscados.

#### `Playwright` (sync_api)
Framework de automação de browser. É acionado apenas quando o motor `requests` retorna uma página com menos de 200 caracteres de texto — indicativo de que o conteúdo é gerado dinamicamente por JavaScript (sites em React, Next.js, Vue etc.). O Playwright abre uma instância do Chromium em modo headless (sem interface gráfica), navega até a URL e retorna o HTML já renderizado com todo o JavaScript executado.

**Sobre o executável Chromium:**
A função `_chromium_executable()` localiza o browser instalado pelo Playwright. Ela tenta primeiro o `chrome-headless-shell.exe` (versão mais leve, sem interface gráfica completa) e, se não encontrar, usa o `chrome.exe` completo como fallback — necessário porque algumas ferramentas de antivírus removem o headless shell por engano.

#### `python-dotenv`
Carrega variáveis de ambiente a partir do arquivo `.env` na raiz do projeto. Provê as credenciais de conexão com o Supabase (`SUPABASE_URL` e `SUPABASE_KEY`) sem expô-las no código-fonte.

#### `supabase-py`
Cliente Python oficial do Supabase (banco de dados PostgreSQL gerenciado na nuvem). Utilizado para três operações:
1. **Leitura** — busca as empresas com domínio cadastrado na tabela `empresas`
2. **Escrita** — insere o resultado da análise na tabela `sinais_ia`
3. **Update** — marca empresas bloqueadas por Cloudflare com `revisao_manual = true` na tabela `empresas`

---

## Funcionamento Detalhado

### 1. Inicialização

O módulo resolve a raiz do projeto subindo três níveis a partir de sua localização (`Path(__file__).resolve().parent.parent.parent`) e carrega o `.env`. Em seguida, cria imediatamente a conexão com o Supabase e a sessão HTTP — ambas ficam disponíveis como variáveis globais do módulo durante toda a execução.

### 2. Ponto de entrada — `pesquisar()`

A função principal realiza o seguinte fluxo:

1. **Consulta o Supabase** buscando todas as empresas com campo `dominio` preenchido. Aceita o parâmetro opcional `nome` para analisar uma única empresa específica (útil para testes ou reprocessamento pontual).
2. **Verifica idempotência**: para cada empresa, consulta a tabela `sinais_ia` e verifica se já existe um registro com `camada = 'institucional'` para aquele `empresa_id`. Se sim, pula. Se a empresa estiver marcada com `revisao_manual = true`, também pula.
3. **Chama `_analisar(dominio)`** para cada empresa elegível.
4. **Persiste o resultado** no Supabase e no JSON local.

### 3. Decisão de motor — `_analisar()`

Esta função decide qual estratégia de acesso usar antes de iniciar o loop de páginas:

```
_analisar("exemplo.com.br")
│
├─ Baixa a home com requests
│
├─ Detectou Cloudflare?
│   └─ Marca revisao_manual=true → encerra
│
├─ Texto da home ≥ 200 caracteres?
│   └─ Usa só requests no loop de páginas
│
└─ Texto da home < 200 caracteres (site JS)?
    └─ Abre Playwright (browser real)
        ├─ Detectou Cloudflare na home renderizada?
        │   └─ Marca revisao_manual=true → encerra
        └─ Usa Playwright no loop de páginas
```

A detecção de Cloudflare verifica se pelo menos 2 dos seguintes marcadores estão presentes no texto da página: `"ray id:"`, `"performing security verification"`, `"just a moment"`, `"cloudflare"`.

### 4. Loop de páginas — `_analisar_loop()`

Este é o núcleo da análise. O módulo percorre uma lista de 33 caminhos pré-definidos (`_PATHS`) montando a URL completa para cada um:

```
/, /produto, /product, /platform, /plataforma, /sobre, /about,
/tecnologia, /technology, /como-funciona, /cases, /clientes,
/blog, /ia, /ai, /saude, /logistica, /inovacao, ...
```

Para cada caminho:
1. Verifica se o tempo total decorrido ultrapassou 90 segundos — se sim, encerra o loop para aquele domínio.
2. Baixa a página (via `requests` ou `Playwright`, conforme decisão anterior).
3. Extrai o texto limpo com BeautifulSoup.
4. Pontua a página com `_pontuar_pagina()`.
5. Acumula a pontuação total.
6. **Se a pontuação acumulada atingir 4 pontos, encerra o loop imediatamente** — evidência suficiente encontrada.
7. Aguarda 1 segundo entre páginas para não sobrecarregar o servidor.

O loop também controla falhas consecutivas: se 10 páginas seguidas falharem no carregamento (erros de rede, 404, 403 etc.), o domínio é abandonado.

### 5. Download de páginas — `_buscar_pagina()` e variantes

O download segue uma hierarquia de tentativas:

```
_buscar_pagina_requests()
    ├─ Tenta até 3 vezes com backoff (espera 2s, depois 4s)
    ├─ Aceita apenas respostas 200 com Content-Type "text/html"
    └─ Se https:// falhar, tenta http:// como fallback

_buscar_pagina()
    ├─ Chama _buscar_pagina_requests() primeiro
    └─ Se o texto extraído tiver < 200 chars e Playwright estiver disponível
        └─ Chama _buscar_pagina_playwright() como complemento
```

O `_buscar_pagina_playwright()` navega com `wait_until="domcontentloaded"` e aguarda 1,5 segundo após o carregamento para garantir que scripts de inicialização terminem de executar.

---

## Sistema de Pontuação

### Sinais fortes — peso 3 por ocorrência

Termos técnicos específicos que raramente aparecem em sites de empresas que não utilizam IA de forma real. Organizados em cinco categorias:

| Categoria | Exemplos |
|---|---|
| Frameworks e bibliotecas de ML | `tensorflow`, `pytorch`, `keras`, `scikit-learn`, `hugging face`, `langchain` |
| LLMs e modelos conhecidos | `gpt`, `claude`, `gemini`, `llama`, `mistral`, `llm`, `foundation model` |
| Infraestrutura de ML | `vertex ai`, `sagemaker`, `azure ml`, `databricks`, `mlflow`, `kubeflow`, `wandb` |
| Conceitos técnicos de ML | `embeddings`, `fine-tuning`, `feature store`, `retrieval augmented`, `vector database`, `mlops` |
| Tarefas de ML aplicadas | `fraud detection`, `demand forecasting`, `credit scoring`, `dynamic pricing`, `churn prediction` |

### Sinais fracos — peso 1 por ocorrência

Termos amplos e genéricos de marketing que podem aparecer em qualquer site sem que a empresa de fato utilize IA. Exemplos: `inteligência artificial`, `machine learning`, `data driven`, `preditivo`, `big data`, `insights automáticos`, `automação inteligente`.

### Limiar de aprovação

Uma empresa é marcada como positiva (`encontrado = true`) quando a **pontuação acumulada total atinge 4 ou mais pontos**. Exemplos de combinações que atingem o limiar:

- 1 sinal forte (3) + 1 sinal fraco (1) = **4 pontos** → positivo
- 2 sinais fortes (6) = **6 pontos** → positivo
- 4 sinais fracos (4) = **4 pontos** → positivo
- 3 sinais fracos (3) = 3 pontos → **negativo**

A pontuação é acumulada entre páginas diferentes. Uma página com 2 pontos e outra com 2 pontos produzem 4 pontos no total.

---

## Blocklist — Filtro de Contexto

Para evitar falsos positivos, o módulo mantém um dicionário `_BLOCKLIST` que descarta um termo quando ele aparece **no mesmo trecho de texto** junto com frases que indicam um uso diferente do esperado.

| Termo detectado | Descartado se acompanhado de |
|---|---|
| `analytics` | "google analytics", "cookie", "facebook pixel", "gtag" |
| `modelos` | "modelos de negócio", "modelo comercial", "modelo de franquia" |
| `treinamento` | "treinamento de equipe", "curso", "capacitação", "onboarding" |
| `pipeline` | "pipeline de vendas", "pipeline comercial", "funil de vendas" |
| `personalização` | "personalização de cookies", "preferências de personalização" |
| `otimização` | "otimização de campanhas", "otimização de seo" |
| `previsão` | "previsão do tempo", "previsão climática" |
| `recomendação` | "carta de recomendação", "recomendação de uso" |
| `" ai "` | "portfólio", "invested" — VC com IA no portfólio, não usuário de IA |
| `mistral` | "portfólio", "investimento" — mesmo caso |

A lógica de verificação (`_termo_bloqueado()`) extrai um trecho de 200 caracteres em torno da ocorrência do termo e verifica se alguma frase proibida está presente nesse trecho.

---

## Estrutura dos Dados de Saída

### Tabela `sinais_ia` no Supabase

Cada empresa analisada gera exatamente um registro:

```json
{
  "empresa_id": 42,
  "camada": "institucional",
  "encontrado": true,
  "evidencia": "...nossa stack utiliza embeddings e fine-tuning de modelos...",
  "fonte_url": "https://exemplo.com.br/tecnologia"
}
```

| Campo | Descrição |
|---|---|
| `empresa_id` | Chave estrangeira para a tabela `empresas` |
| `camada` | Sempre `"institucional"` — distingue esta fonte das camadas `imprensa`, `gupy_vagas`, `neofeed` |
| `encontrado` | `true` se pontuação ≥ 4, `false` caso contrário |
| `evidencia` | Trecho de ~200 caracteres do texto onde o termo determinante foi encontrado |
| `fonte_url` | URL exata da página onde a evidência foi encontrada |
| `checado_em` | Timestamp UTC preenchido automaticamente pelo banco |

### Arquivo JSON local — `data/jsons/institucional/institucional.json`

O arquivo local é um backup acumulativo dos resultados. Cada execução **adiciona** apenas os registros novos (empresas não presentes no arquivo anterior), sem sobrescrever os já existentes. O arquivo contém uma lista de objetos, cada um com todos os campos do banco mais os campos adicionais `nome_empresa`, `dominio`, `tipo_sinal`, `pontuacao` e `coletado_em`.

---

## Pontos de Atenção

**Sites protegidos por Cloudflare**
Sites com Cloudflare ativo respondem com uma página de desafio JavaScript que o `requests` não consegue resolver e que o `Playwright` frequentemente também não consegue contornar. Esses casos são marcados com `revisao_manual = true` na tabela `empresas` e ficam fora da análise automática, aguardando verificação humana. É um comportamento esperado e controlado.

**Sites com conteúdo técnico fora dos paths listados**
O módulo visita apenas os 33 caminhos definidos em `_PATHS`. Se uma empresa mantém seu conteúdo técnico em caminhos não listados (como `/engenharia`, `/tech-blog`, `/dev`), esses caminhos não serão visitados e a empresa pode ser classificada como negativa mesmo tendo conteúdo relevante. O conjunto de paths pode ser expandido conforme novos padrões sejam identificados.

**Conteúdo em formatos não textuais**
O módulo analisa apenas texto HTML visível. Conteúdo técnico publicado em PDFs, imagens, vídeos ou documentações embarcadas como iframes não é capturado. Empresas que publicam whitepapers técnicos em PDF, por exemplo, não terão esse conteúdo avaliado.

**Timeout de 90 segundos por domínio**
Sites com muitas páginas lentas podem ter a análise encerrada antes que todos os caminhos sejam visitados. O timeout existe para garantir que o processamento do lote como um todo não trave em um único domínio problemático. Em casos onde isso ocorrer, reprocessar a empresa isoladamente (via parâmetro `nome=`) pode ser suficiente.

**Termos técnicos com grafia não convencional**
O matching de sinais é feito por busca exata de substring em texto minúsculo. Variações de grafia como `"PyTorch"` (com espaço ou hífen diferente), termos dentro de código JavaScript, ou termos concatenados sem espaço podem não ser detectados. A lista de sinais pode ser expandida conforme casos sejam identificados.

**Listas de sinais e blocklist são mantidas manualmente**
Novos frameworks, LLMs, infraestruturas de ML, ou novas formas de uso falso-positivo de termos não são detectados automaticamente. A expansão e curadoria das listas `_SINAIS_FORTES`, `_SINAIS_FRACOS` e `_BLOCKLIST` é um processo manual que deve acompanhar a evolução do ecossistema.

**Executável Chromium — caminho Windows**
A função `_chromium_executable()` usa o caminho `LOCALAPPDATA/ms-playwright`, que é específico do Windows. Em macOS e Linux, a função retorna `None` e o Playwright localiza o executável pelo seu próprio mecanismo padrão. O comportamento é correto em ambas as plataformas, mas a função em si só tem efeito prático no Windows.