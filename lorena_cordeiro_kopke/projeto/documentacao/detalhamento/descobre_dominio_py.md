# Documentação Técnica — `descobre_dominio.py`

## Visão Geral

O `descobre_dominio.py` é um módulo de enriquecimento de dados do projeto. Sua responsabilidade é descobrir automaticamente o domínio web de startups cujo registro na tabela `empresas` do Supabase ainda não possui esse campo preenchido.

O módulo opera em três etapas: geração de URLs candidatas a partir do nome da empresa, validação de cada candidato via requisição HTTP real e persistência do resultado encontrado tanto no Supabase quanto em um arquivo JSON local. A geração de candidatos aplica múltiplas heurísticas linguísticas (slugificação, extração de TLD embutido no nome, variações de slug e sigla) para cobrir os padrões mais comuns de nomenclatura de domínios de startups brasileiras. A validação checa o status HTTP, o tipo de conteúdo da resposta e se a URL final não redireciona para uma página de estacionamento de domínio.

O script é executado de forma autônoma via linha de comando e pode ser restringido a uma única empresa por nome, o que facilita testes e reprocessamentos pontuais.

---

## Posição no Pipeline

```
Supabase (tabela empresas — sem campo domínio)
    → descobre_dominio.py     [geração de candidatos + validação HTTP]
        → Supabase (campo domínio atualizado)
        → data/jsons/dominio_empresas/dominios_encontrados.json
            → (módulos posteriores de scraping e coleta de dados da empresa)
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
| `json` | Leitura e escrita do arquivo JSON de saída local acumulativo |
| `os` | Acesso às variáveis de ambiente `SUPABASE_URL` e `SUPABASE_KEY` |
| `time` | Pausa de 0,4 segundos entre requisições HTTP para não sobrecarregar servidores |
| `unicodedata` | Normalização NFKD para remoção de acentos e caracteres compostos |
| `datetime` / `timezone` | Registro do timestamp UTC de quando o domínio foi descoberto |
| `pathlib.Path` | Manipulação de caminhos de arquivo de forma orientada a objetos e multiplataforma |
| `urllib.parse.urlparse` | Extração do host a partir da URL final após redirecionamentos HTTP |
| `sys` | Leitura do argumento `--debug` via `sys.argv` na execução direta |

**Sobre `unicodedata` e NFKD:**
NFKD (*Normalization Form Compatibility Decomposition*) é uma forma de normalização Unicode que decompõe caracteres compostos em seus componentes base. Por exemplo, `"á"` é decomposto em `"a"` + acento combinado. Com `.encode("ascii", "ignore")`, os acentos são então descartados, resultando em texto ASCII puro — necessário para gerar slugs de domínio válidos.

---

### Bibliotecas de terceiros

#### `requests`
Biblioteca HTTP para Python, utilizada para realizar as requisições GET que validam os domínios candidatos. O módulo cria uma `requests.Session()` reutilizável, o que mantém conexões TCP abertas entre requisições consecutivas e define o cabeçalho `User-Agent` uma única vez para toda a sessão. O `User-Agent` configurado — `"Mozilla/5.0 (compatible; pesquisa-academica/1.0)"` — identifica o cliente como ferramenta de pesquisa acadêmica. As requisições seguem redirecionamentos automaticamente via `allow_redirects=True`, o que permite capturar a URL final real (ex.: `http://empresa.com` pode redirecionar para `https://www.empresa.com.br`).

#### `python-dotenv`
Carrega variáveis de ambiente a partir do arquivo `.env` localizado na raiz do projeto. Provê as credenciais necessárias para conexão com o Supabase sem expô-las no código-fonte.

#### `supabase-py`
Cliente Python oficial do **Supabase** (banco de dados PostgreSQL gerenciado). Utilizado em dois momentos: na leitura inicial das empresas sem domínio registrado e na atualização do campo `dominio` quando um candidato válido é encontrado.

---

## Funcionamento Detalhado

### 1. Inicialização

O módulo resolve a raiz do projeto subindo três níveis a partir de sua localização e carrega as variáveis de ambiente do `.env`. Em seguida, instancia o cliente Supabase e a sessão HTTP — ambos são criados uma única vez e reutilizados durante toda a execução.

### 2. Listas de controle estático

Antes de qualquer processamento, três estruturas estáticas são definidas no nível do módulo:

**`_TLDS`**: lista ordenada dos seis sufixos de domínio testados para cada empresa, em ordem de prioridade: `.com.br`, `.com`, `.io`, `.ai`, `.tech`, `.co`.

**`_PARKING`**: conjunto de hosts conhecidos de estacionamento e registro de domínios — empresas que hospedam páginas genéricas de venda quando o domínio não possui site real associado. Se a URL final de uma requisição redirecionar para qualquer um desses hosts, o candidato é rejeitado.

**`_DOMINIOS_ERRADOS`**: lista curada manualmente de domínios que existem, respondem com status 200 e servem HTML válido, mas pertencem a outra empresa com nome coincidente. Cada entrada é acompanhada de um comentário explicando o conflito. Candidatos presentes nessa lista são rejeitados imediatamente, antes mesmo de qualquer requisição HTTP.

### 3. Consulta ao Supabase

A função `descobrir()` consulta a tabela `empresas` selecionando os campos `id`, `nome` e `dominio`. Registros que já possuem o campo `dominio` preenchido são filtrados em memória, restando apenas as empresas que precisam de descoberta.

### 4. Geração de candidatos

Para cada empresa pendente, a função `_candidatos(nome)` produz uma lista ordenada de URLs a testar. O processo é:

1. **Detecção de TLD embutido** — verifica se o nome já termina com um TLD conhecido (ex: `"Segura.ai"` → `segura.ai`). Se sim, esse domínio é inserido no início da lista como candidato prioritário.
2. **Slugificação** — o nome é normalizado via `_slugify()`: remoção de acentos, conversão para minúsculas, substituição de `&` por `"e"` e de `/` por espaço, remoção de caracteres especiais.
3. **Geração de slugs** — a partir das palavras normalizadas, gera variações: palavras unidas com hífen, palavras coladas sem separador, primeira palavra isolada, sigla (iniciais de palavras com 3+ letras), e combinações das duas primeiras palavras (para nomes com 3+ palavras).
4. **Cruzamento com TLDs** — cada slug é combinado com cada TLD da lista `_TLDS`, produzindo a lista final de candidatos.

### 5. Validação dos candidatos

Para cada URL candidata, `_provar_dominio()` executa a validação em sequência:

1. Rejeita imediatamente se o domínio estiver em `_DOMINIOS_ERRADOS`
2. Realiza requisição GET HTTPS com timeout de 6 segundos, seguindo redirecionamentos
3. Rejeita se o status HTTP não for 200
4. Rejeita se o `Content-Type` não contiver `text/html`
5. Rejeita se a URL final redirecionar para um host presente em `_PARKING`
6. Aceita o domínio se todas as condições forem satisfeitas

Uma pausa de 0,4 segundos é aplicada antes de cada requisição.

### 6. Persistência

Ao encontrar o primeiro candidato válido para uma empresa, o módulo:
- Atualiza o campo `dominio` na tabela `empresas` do Supabase (se `_APENAS_JSON = False`)
- Adiciona o registro ao arquivo JSON local de forma acumulativa (sem sobrescrever entradas anteriores)
- Interrompe o teste dos demais candidatos para aquela empresa com `break`

Empresas para as quais nenhum candidato foi confirmado são listadas ao final da execução como itens que requerem revisão manual.

---

## Geração de Slugs — Exemplo Prático

```
Nome: "Minha Startup Brasil"
  palavras normalizadas: ["minha", "startup", "brasil"]

Slugs gerados (em ordem):
  1. "minha-startup-brasil"   (todas as palavras com hífen)
  2. "minhastartupbrasil"     (todas as palavras coladas)
  3. "minha"                  (primeira palavra isolada)
  4. "msb"                    (sigla — iniciais de palavras com 3+ letras)
  5. "minha-startup"          (duas primeiras palavras com hífen)
  6. "minhastartup"           (duas primeiras palavras coladas)

Cruzamento com TLDs:
  minha-startup-brasil.com.br
  minha-startup-brasil.com
  minha-startup-brasil.io
  ...
  minhastartup.co             (último da lista)
```

---

## Estrutura dos Dados de Saída

### Supabase — tabela `empresas`

O campo `dominio` da linha correspondente à empresa é atualizado com o domínio confirmado (ex: `"minhaempresa.com.br"`).

### JSON local — `data/jsons/dominio_empresas/dominios_encontrados.json`

```json
[
  {
    "empresa_id": "uuid-da-empresa",
    "nome": "Nome da Empresa",
    "dominio": "nomeempresa.com.br",
    "descoberto_em": "2026-07-02T14:30:00+00:00"
  }
]
```

| Campo | Descrição |
|---|---|
| `empresa_id` | UUID da linha na tabela `empresas` do Supabase |
| `nome` | Nome original da empresa conforme registrado no banco |
| `dominio` | Domínio confirmado pela validação HTTP |
| `descoberto_em` | Timestamp UTC do momento da descoberta em formato ISO 8601 |

O arquivo é acumulativo: novas execuções adicionam registros sem remover os anteriores. Deduplicação é feita por `empresa_id` para evitar entradas duplicadas.

---

## Flag de Modo Seguro — `_APENAS_JSON`

A constante `_APENAS_JSON = False` na linha 153 do módulo controla se o Supabase é atualizado:

| Valor | Comportamento |
|---|---|
| `False` (padrão) | Atualiza o Supabase **e** salva no JSON local |
| `True` | Salva **apenas** no JSON local, sem tocar no banco |

Trocar para `True` é útil para validar o comportamento do script em um novo conjunto de empresas sem modificar o banco de produção.

---

## Modo Debug

Executando com `--debug`:

```
python descobre_dominio.py --debug
```

Cada requisição imprime uma linha detalhada:

```
[debug] https://nomeempresa.com.br → https://www.nomeempresa.com.br
  status=200  html=True  parking=False
```

Domínios rejeitados pela lista `_DOMINIOS_ERRADOS` também são reportados:

```
[debug] segura.com.br → bloqueado (domínio errado conhecido)
```

---

## Pontos de Atenção

**Manutenção da lista `_DOMINIOS_ERRADOS`**
A lista de domínios conflitantes é mantida manualmente no código-fonte. Novos casos de colisão de nome — empresas diferentes que compartilham um domínio plausível — não serão detectados automaticamente e precisam ser adicionados à lista quando identificados.

**Cobertura limitada de TLDs**
O script testa seis TLDs fixos. Domínios com extensões não listadas, como `.net`, `.app`, `.dev` ou `.company`, nunca serão candidatos.

**Apenas HTTPS**
Todos os candidatos são testados exclusivamente via `https://`. Sites que operam somente em `http://` (sem certificado SSL válido) não serão reconhecidos como válidos.

**Validação por comportamento HTTP, não por conteúdo**
O módulo confirma que um domínio responde com status 200 e entrega HTML. Não verifica se o conteúdo da página menciona o nome da empresa. Um domínio de terceiro que casualmente coincida com o slug gerado, mas que pertença a outra entidade, pode ser aceito caso não esteja listado em `_DOMINIOS_ERRADOS`.

**Sem consulta DNS prévia**
O script não realiza lookup DNS antes de tentar a requisição HTTP. 

**Sem retry em falhas de rede**
Se uma requisição falhar por timeout ou instabilidade momentânea de rede, o candidato é descartado sem nova tentativa.

**Aceitação do primeiro candidato válido**
O script interrompe o teste assim que o primeiro candidato é confirmado.
