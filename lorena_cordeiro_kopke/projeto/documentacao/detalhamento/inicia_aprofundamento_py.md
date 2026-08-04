# Documentação Técnica — `inicia_aprofundamento.py`

## Visão Geral

O `inicia_aprofundamento.py` é o orquestrador central do pipeline de aprofundamento de startups do projeto. Sua responsabilidade é coordenar 12 passos sequenciais que transformam uma empresa pré-aprovada em um perfil completo e classificado, enriquecido com dados legais, descrições de produto, classificações de uso de IA e um score de maturidade tecnológica.

O módulo não realiza nenhuma coleta ou classificação por conta própria — ele atua exclusivamente como coordenador, chamando submodulos especializados em ordem e garantindo que cada passo opere apenas sobre os registros ainda pendentes. Ao final da execução, cada startup possui dezenas de campos preenchidos no banco de dados Supabase, além de backups locais em JSON.

O pipeline é idempotente por design: como cada passo consulta o banco antes de agir e só processa registros com campos ainda nulos, a execução pode ser interrompida e retomada sem duplicar ou sobrescrever dados já coletados.

---

## Posição no Pipeline

```
avaliacoes_ia (Supabase)
    → inicia_aprofundamento.py    [orquestrador]
        ├─ Passo 1:  seed de aprovadas
        ├─ Passo 2:  enriquecimento de identidade (CNPJ + BrasilAPI)
        ├─ Passo 3:  descoberta de produto
        ├─ Passo 4:  descoberta de uso de IA
        ├─ Passo 5:  classificação ia_e_core_product
        ├─ Passo 6:  classificação ia_tipo
        ├─ Passo 7:  classificação modelo_negocio
        ├─ Passo 8:  verificação produto_ia_lancado
        ├─ Passo 9:  classificação de setor
        ├─ Passo 10: classificação de mercado_alvo
        ├─ Passo 11: detecção de aceleradoras
        └─ Passo 12: classificação de maturidade
            → empresas_uso_ia (Supabase)
            → data/jsons/empresas_uso_ia/*.json (backups locais)
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
| `os` | Acesso às variáveis de ambiente `SUPABASE_URL` e `SUPABASE_KEY` |
| `re` | Compilação de expressões regulares para detecção de padrões nos textos raspados dos sites |
| `json` | Leitura e escrita dos arquivos de backup local em `data/jsons/` |
| `time` | Pausas (`sleep`) entre requisições HTTP para evitar bloqueio por rate limiting |
| `pathlib.Path` | Localização do `.env` e criação dos diretórios de saída de forma multiplataforma |
| `urllib.parse` | Composição de URLs com `urljoin` ao concatenar domínios com slugs de página |

---

### Bibliotecas de terceiros

#### `python-dotenv`
Carrega variáveis de ambiente a partir do arquivo `.env` na raiz do projeto. Provê as credenciais necessárias para conexão com o Supabase e as APIs externas sem expô-las no código-fonte.

#### `supabase-py`
Cliente Python oficial do **Supabase** (banco de dados PostgreSQL gerenciado em nuvem). Utilizado ao longo de todos os 12 passos para leitura e escrita na tabela `empresas_uso_ia`, além de consultas auxiliares às tabelas `empresas` e `avaliacoes_ia`.

#### `requests`
Biblioteca HTTP para realizar requisições GET aos sites das startups durante o scraping. Utilizada com uma `Session` compartilhada que mantém um `User-Agent` simulando o Chrome para reduzir bloqueios por anti-bot.

#### `urllib3`
Biblioteca HTTP de baixo nível que suporta a `requests`. Utilizada especificamente para desabilitar os avisos de SSL inválido (`InsecureRequestWarning`) que surgem quando `verify=False` é necessário para acessar sites com certificados mal configurados.

#### `BeautifulSoup4 (bs4)`
Parser de HTML que transforma o conteúdo bruto das páginas em uma estrutura navegável de tags. Utilizado para extrair meta descriptions, textos de H1, parágrafos, CTAs e atributos `alt` de imagens, dependendo do passo do pipeline.

#### `Playwright (Chromium)`
Navegador headless que executa JavaScript completo das páginas antes de entregar o HTML ao BeautifulSoup. Acionado como fallback quando o scraping estático com `requests` retorna vazio — situação comum em sites construídos com React, Vue ou Angular, onde o conteúdo só existe após a execução do JavaScript.

#### `google-genai` — via `src/agents/`
SDK oficial da Google para acesso à API Gemini. Encapsulado em módulos dedicados dentro de `src/agents/`, cada um responsável por uma classificação específica. O modelo utilizado em todos os agentes é o **`gemini-flash-lite-latest`**, versão otimizada para velocidade e custo. Todos os agentes implementam **retry com backoff exponencial** para erros HTTP 429 (rate limit): 5 segundos na primeira tentativa, 10 na segunda e 20 na terceira.

#### `httpx`
Cliente HTTP moderno utilizado dentro dos agentes Gemini para substituir o cliente padrão do SDK da Google por uma instância com `verify=False`, permitindo operação em redes com proxy de inspeção SSL.

#### BrasilAPI (API externa)
API pública REST que expõe dados da Receita Federal brasileira por CNPJ. Utilizada no Passo 2 para obter razão social, nome fantasia, CNAE, porte, capital social, natureza jurídica, município, UF e data de início de atividade.

#### minhareceita.org (API externa)
Serviço público de busca de CNPJs por nome ou domínio. Acionado como terceiro fallback no Passo 2, quando nem o Playwright nem o scraping estático encontram o CNPJ no próprio site da empresa.

---

## Funcionamento Detalhado

### 1. Inicialização

O módulo resolve a raiz do projeto subindo três níveis a partir de sua localização, carrega o `.env` e instancia o cliente Supabase. Todos os submodulos seguem o mesmo padrão de inicialização, criando seus próprios clientes Supabase e sessões HTTP de forma independente.

### 2. Controle de escopo

Todos os 12 passos aceitam o parâmetro `nome` (opcional). Quando fornecido, cada passo restringe sua atuação à empresa com aquele nome exato, ignorando todas as demais. Isso permite reprocessar ou testar uma empresa específica sem afetar o restante da base.

### 3. Idempotência por campo nulo

Cada passo consulta o banco filtrando apenas registros onde o campo alvo ainda é `NULL`. Empresas com o campo já preenchido são ignoradas automaticamente, tornando seguro reexecutar o pipeline quantas vezes forem necessárias.

### 4. Persistência dupla

Todos os passos que coletam dados textuais (Passos 2 a 11) salvam os resultados em dois destinos: o banco Supabase (via `upsert` com conflito em `empresa_id`) e um arquivo JSON local em `data/jsons/empresas_uso_ia/`. Os JSONs servem como backup e registro auditável da coleta.

---

## Os 12 Passos do Pipeline

### Passo 1 — Seed de aprovadas

Cria a "ficha em branco" de cada empresa aprovada na tabela `empresas_uso_ia`. O passo consulta a tabela `avaliacoes_ia` filtrando `veredito = True`, cruza com os registros já existentes em `empresas_uso_ia` e insere apenas as empresas ainda ausentes, já preenchendo `dominio`, `gupy_subdominio` e `situacao_coleta = "informação pendente"`.

---

### Passo 2 — Enriquecimento de identidade

Descobre o CNPJ de cada empresa e busca seus dados legais na Receita Federal via BrasilAPI.

**Busca do CNPJ — três estratégias em cascata:**

```
Estratégia 1: Playwright
    ↓ CNPJ não encontrado no DOM renderizado
Estratégia 2: requests estático
    ↓ CNPJ não encontrado no HTML bruto
Estratégia 3: minhareceita.org
    ↓ nenhuma estratégia retornou resultado
    → cnpj_pendente = True (preenchimento manual necessário)
```

O CNPJ encontrado é validado por dois critérios: formato correto de 14 dígitos e correspondência fuzzy entre a razão social ou nome fantasia retornados pela BrasilAPI e o nome da empresa no banco — verificação que elimina CNPJs de infraestrutura pública (Banco do Brasil, SERPRO, Petrobras) que frequentemente aparecem em rodapés de sites.

**Dados coletados via BrasilAPI:**

| Campo | Descrição |
|---|---|
| `cnpj` | CNPJ com 14 dígitos sem formatação |
| `razao_social` | Razão social oficial |
| `nome_fantasia` | Nome fantasia, se existir |
| `situacao_rf` | Situação cadastral (ex: ATIVA, BAIXADA) |
| `municipio` / `uf` | Localização da sede |
| `cnae_principal` | Código CNAE + descrição do ramo de atividade |
| `porte` | MEI / ME / EPP / DEMAIS |
| `capital_social` | Capital social declarado |
| `natureza_juridica` | Natureza jurídica (ex: Sociedade Empresária Limitada) |
| `ano_fundacao` | Ano de início de atividade, extraído da data completa |

---

### Passo 3 — Descoberta de produto

Descobre o produto ou serviço principal da startup em 1-2 frases, a partir do conteúdo do site institucional.

**Estratégia em cascata:**

```
Camada 1: scraping com requests + BeautifulSoup
    Páginas visitadas: /, /sobre, /produto, /solucoes, /plataforma, /about, /product, /solutions
    Extratores (em ordem de prioridade):
      → meta description / og:description / twitter:description
      → H1 + subtítulo/tagline imediata
      → parágrafos abaixo de headings com keywords de produto
    ↓ todas as páginas retornaram vazio
Camada 2: Playwright
    Mesmo conjunto de extratores aplicado ao HTML renderizado com JS
    ↓ ainda sem resultado
Camada 3: Gemini (inferência pelo conhecimento do modelo)
    Prompt: "Qual é o produto principal de [nome] (domínio: [x])?"
```

Quando as Camadas 1 ou 2 coletam textos com sucesso, o Gemini é acionado para **resumir** os fragmentos em 1-2 frases objetivas, eliminando slogans e linguagem de marketing. Somente na Camada 3 o Gemini atua sem conteúdo de site.

---

### Passo 4 — Descoberta de uso de IA

Descobre como a startup utiliza inteligência artificial no seu produto, seguindo exatamente a mesma arquitetura de cascata do Passo 3.

**Diferenças em relação ao Passo 3:**
- Páginas priorizadas: `/tecnologia`, `/como-funciona`, `/how-it-works`, `/technology`
- A extração busca parágrafos que contenham termos como `inteligência artificial`, `machine learning`, `deep learning`, `LLM`, `NLP`, `visão computacional`, `generativ`, `predict`
- O prompt ao Gemini pede especificamente o uso de IA, não a descrição do produto em geral

---

### Passo 5 — Classificação `ia_e_core_product`

Responde à pergunta: **"A IA é o produto principal da empresa, ou apenas uma ferramenta interna?"**

Um empresa que usa IA para otimizar sua logística internamente recebe `FALSE`. Uma empresa que vende uma plataforma de IA generativa recebe `TRUE`. Essa distinção é o principal determinante do nível máximo de maturidade que uma empresa pode atingir.

**Estratégia:**

```
Se produto ou uso_ia_descricao já existem no banco:
    → Gemini classifica diretamente (sem scraping)
Se não:
    → scraping buscando sinais fortes: "plataforma de IA", "AI-powered",
      "LLM", "copilot", "built on AI", "visão computacional"
    ↓ scraping vazio
    → Playwright
    ↓ ainda sem resultado
    → Gemini infere pelo conhecimento do modelo
```

Resposta esperada do Gemini: `VERDADEIRO` ou `FALSO`.

---

### Passo 6 — Classificação `ia_tipo`

Categoriza o tipo de IA predominante no produto da empresa. Não realiza scraping — usa os campos `produto` e `uso_ia_descricao` já coletados como contexto para o Gemini.

**Categorias e seus pesos no score de maturidade:**

| Categoria | Peso |
|---|---|
| IA Generativa | 2.0 |
| NLP / LLM | 2.0 |
| Visão Computacional | 2.0 |
| Automação Inteligente | 1.0 |
| Análise Preditiva | 1.0 |
| Dados e Analytics | 0.5 |

---

### Passo 7 — Classificação `modelo_negocio`

Classifica a empresa como B2B, B2C ou B2B2C com base em sinais estruturais do site.

**Sistema de pontuação por sinais:**

| Sinal | Tipo | Peso |
|---|---|---|
| "Fale com vendas", "Agendar demo", "Book a demo" | CTA B2B | +2 por ocorrência |
| "para empresas", "enterprise", "for teams" | Keyword B2B | +1 por ocorrência |
| "Criar conta", "Começar grátis", "Sign up free" | CTA B2C | +2 por ocorrência |
| "para você", "plano individual", "for individuals" | Keyword B2C | +1 por ocorrência |
| "sob consulta", "enterprise pricing" | Pricing B2B | +3 |
| Preços fixos visíveis (R$ XX/mês) | Pricing B2C | +2 |

**Regra de decisão automática (sem LLM):**

```
ratio_b2b = pontos_B2B / (pontos_B2B + pontos_B2C)

ratio_b2b ≥ 0.75  →  B2B  (decisão automática)
ratio_b2b ≤ 0.25  →  B2C  (decisão automática)
b2b ≥ 2 e b2c ≥ 2 →  B2B2C (decisão automática)
caso contrário     →  Gemini decide com textos + pontuação como contexto
```

---

### Passo 8 — Verificação `produto_ia_lancado`

Verifica se a empresa já tem um produto acessível ao público, sem uso de LLM.

**Método:** faz requisições HTTP para URLs que só existem quando há produto ativo. Se qualquer URL retornar HTTP 200 com Content-Type HTML, o campo é marcado `TRUE`.

```
Rotas verificadas no domínio principal:
  /login, /app, /dashboard, /demo, /demonstracao,
  /pricing, /precos, /planos, /plans,
  /signup, /cadastro, /register, /trial, /assinar, /subscribe,
  /solucoes, /solutions

Subdomínios verificados:
  app.*, platform.*, portal.*, console.*, dashboard.*
```

Se nenhuma rota responder, o Gemini é consultado com `produto`, `uso_ia_descricao`, `modelo_negocio` e `ano_fundacao` como contexto para inferir se a empresa já tem produto no mercado.

---

### Passo 9 — Classificação de `setor`

Classifica o setor de mercado da empresa (ex: Saúde, Educação, Finanças, RH). Sem scraping — usa `cnae_principal`, `produto` e `uso_ia_descricao` como contexto para o Gemini.

---

### Passo 10 — Classificação de `mercado_alvo`

Classifica se a empresa atende ao mercado brasileiro, latino-americano ou global.

**Estratégia em três camadas progressivas (da mais barata para a mais custosa):**

```
Camada 1: TLD .com.br sem menção a LATAM/global nos textos coletados
    → retorna "Brasil" diretamente, sem chamar o LLM nem fazer scraping

Camada 2: TLD neutro (.com, .io, etc.) com produto ou uso_ia_descricao disponíveis
    → Gemini classifica com TLD + textos como contexto

Camada 3: textos ainda vazios
    → scraping apenas do atributo lang da tag <html> da homepage
      (ex: "pt-BR" → Português, "en" → Inglês, "es" → Espanhol)
    → Gemini classifica com TLD + idioma detectado
```

---

### Passo 11 — Detecção de aceleradoras

Detecta se a startup participa de programas de aceleração reconhecidos via scraping de texto e atributos `alt` de imagens (onde ficam os badges/logos dos programas).

**Programas mapeados:**

| Programa | Padrão de detecção |
|---|---|
| NVIDIA Inception | `nvidia inception`, `inception program` |
| Google for Startups | `google for startups` |
| Microsoft for Startups | `microsoft for startups` |
| AWS Activate | `aws activate` |
| Intel Ignite | `intel ignite`, `intel startup program` |
| Y Combinator | `y combinator`, `ycombinator` |
| Endeavor | `endeavor`, `endeavour` |
| Sequoia Arc | `sequoia arc` |

Páginas visitadas: `/`, `/sobre`, `/about`, `/parceiros`, `/partners`, `/aceleradoras`, `/ecosystem`. Fallback: Playwright se o scraping estático retornar vazio.

---

### Passo 12 — Classificação de maturidade

Calcula um score numérico (0 a 10) e classifica o nível de maturidade em IA de cada empresa com base nos dados já coletados nos passos anteriores.

**Fórmula — quatro pilares:**

| Pilar | Campo | Pontos |
|---|---|---|
| Centralidade | `ia_e_core_product = TRUE` | +4.0 |
| Sofisticação técnica | `ia_tipo` (ver tabela do Passo 6) | +0.5 a +2.0 |
| Execução de mercado | `produto_ia_lancado = TRUE` | +2.0 |
| DNA Temporal | `ano_fundacao` | +0.0 a +2.0 |

**Faixas de DNA Temporal por ano de fundação:**

| Ano de fundação | Pontos | Era tecnológica |
|---|---|---|
| 2022 ou posterior | +2.0 | Era ChatGPT / LLM generativo |
| 2020 – 2021 | +1.5 | Era GPT-3 / IA moderna acessível |
| 2017 – 2019 | +1.0 | Era Transformers / deep learning mainstream |
| 2012 – 2016 | +0.5 | Era Big Data / early deep learning |
| Anterior a 2012 | +0.0 | Pré-IA moderna |

**Mapeamento de score para nível:**

| Score | Condição adicional | Nível |
|---|---|---|
| ≥ 8.0 | `ia_e_core = TRUE` | `ai-native` |
| ≥ 5.0 | `ia_e_core = TRUE` | `ai-first` |
| ≥ 2.0 | qualquer | `ai-enabled` |
| < 2.0 | qualquer | `ai-adjacent` |

**Hard cap:** se `ia_e_core_product = FALSE`, o nível máximo possível é `ai-enabled`, independentemente do score acumulado nos demais pilares. Empresas que não vendem IA como produto principal não podem ser classificadas como `ai-native` ou `ai-first`.

Ao final do Passo 12, o módulo `atualizar_situacao_coleta` é acionado para atualizar o status geral da coleta na tabela.

---

## Dados Coletados ao Final do Pipeline

Cada registro em `empresas_uso_ia` termina com os seguintes campos preenchidos:

| Campo | Tipo | Origem |
|---|---|---|
| `cnpj` | string | Playwright / requests / minhareceita.org |
| `razao_social` | string | BrasilAPI |
| `nome_fantasia` | string | BrasilAPI |
| `situacao_rf` | string | BrasilAPI |
| `municipio` / `uf` | string | BrasilAPI |
| `cnae_principal` | string | BrasilAPI |
| `porte` | string | BrasilAPI |
| `capital_social` | número | BrasilAPI |
| `natureza_juridica` | string | BrasilAPI |
| `ano_fundacao` | número | BrasilAPI |
| `produto` | string | Scraping + Gemini |
| `uso_ia_descricao` | string | Scraping + Gemini |
| `ia_e_core_product` | boolean | Scraping + Gemini |
| `ia_tipo` | string | Gemini |
| `modelo_negocio` | string | Scraping + Gemini |
| `produto_ia_lancado` | boolean | HTTP probing + Gemini |
| `setor` | string | Gemini |
| `mercado_alvo` | string | TLD + Scraping + Gemini |
| `programa_aceleracao` | lista | Scraping |
| `score_maturidade_ia` | número (0–10) | Calculado localmente |
| `nivel_maturidade_ia` | string | Calculado localmente |

---

## Parâmetros de Execução

```python
atualizar(atualizar_banco=True, nome=None)
```

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `atualizar_banco` | `True` | Quando `False`, calcula e exibe tudo mas não escreve no banco — útil para validar resultados antes de persistir |
| `nome` | `None` | Quando informado, restringe todos os 12 passos a uma única empresa pelo nome exato — útil para testes ou reprocessamento pontual |