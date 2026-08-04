# Scraper V4 - Playwright como Fallback Real

## 1. Objetivo

A V4 adiciona uma segunda tecnologia real de coleta.

```txt
BeautifulSoup
-> primeira estrategia, mais simples e barata

Playwright
-> fallback para paginas que precisam de navegador e JavaScript
```

Antes desta versao, a pipeline ja suportava varias estrategias, mas somente
BeautifulSoup possuia uma implementacao concreta.

---

## 2. Fluxo atual

```txt
BeautifulSoup coleta
-> validacao aceita?
   -> sim: produz resultado
   -> nao, mas problema permite fallback: tenta Playwright

Playwright abre Chromium
-> executa JavaScript
-> extrai DOM e texto renderizados
-> validacao aceita ou rejeita
```

Cada tecnologia gera sua propria `ScrapingAttempt`.

Exemplo validado:

```txt
tentativa 1
method = beautifulsoup
status = failed

tentativa 2
method = playwright
status = accepted
decision = accept
```

---

## 3. Componente adicionado

Arquivo:

```txt
apps/api/src/modules/scraping/infrastructure/scrapers/playwright_scraper.py
```

O `PlaywrightScraper` implementa a mesma porta `Scraper` usada pelo
`BeautifulSoupScraper`.

Entrada:

```txt
ScrapingInput
```

Saida:

```txt
ScrapingOutput
```

Isso permite que a pipeline utilize ambas as tecnologias sem conhecer seus
detalhes internos.

---

## 4. Navegador e renderizacao

O scraper utiliza:

```txt
Playwright async API
Chromium headless
```

Fluxo interno:

```txt
valida URL inicial
-> inicia Chromium
-> cria contexto isolado
-> intercepta requisicoes
-> navega ate a pagina
-> aguarda DOMContentLoaded
-> aguarda body existir
-> extrai HTML, texto, titulo e URL final
-> fecha navegador
```

`DOMContentLoaded` foi escolhido em vez de `networkidle`.

Paginas modernas frequentemente mantem analytics e conexoes abertas. Esperar
rede totalmente ociosa pode causar timeout mesmo quando o conteudo ja esta
pronto.

---

## 5. Seguranca SSRF

Playwright possui uma superficie de rede maior que uma requisicao HTTP comum.

JavaScript da pagina pode tentar carregar:

```txt
redirects
imagens
scripts
iframes
chamadas fetch/XHR
enderecos internos
```

Por isso, validar somente a URL inicial seria insuficiente.

O `PlaywrightScraper` intercepta todas as requisicoes HTTP/HTTPS do navegador:

```txt
requisicao criada pelo navegador
-> UrlGuard valida destino
-> destino publico: continua
-> destino privado ou inseguro: aborta
```

Recursos sem acesso de rede, como `data:` e `blob:`, podem continuar.

---

## 6. Limites e erros

Configuracao atual na factory:

```txt
BeautifulSoup timeout = 15 segundos
Playwright timeout = 30 segundos
Pipeline timeout total = 90 segundos
```

Playwright possui timeout maior porque iniciar e renderizar um navegador custa
mais que baixar HTML estatico.

Erros conhecidos sao traduzidos para excecoes do dominio:

```txt
Playwright timeout
-> ScrapingLimitExceededError

erro de navegador ou navegacao
-> ScrapingRequestError

destino inseguro
-> UnsafeUrlError

DOM renderizado grande demais
-> ScrapingLimitExceededError
```

Erros recuperaveis sao registrados na tentativa e permitem que a pipeline
continue quando existir outra estrategia.

---

## 7. Metadados do resultado

Resultados produzidos pelo Playwright incluem:

```json
{
  "browser": "chromium",
  "javascript_rendered": true,
  "response_bytes": 318485
}
```

O campo `method` recebe:

```txt
playwright
```

Isso permite identificar qual tecnologia produziu o conteudo aceito.

---

## 8. Factory

A ordem configurada pela `ScrapingFactory` e:

```txt
1. BeautifulSoupScraper
2. PlaywrightScraper
```

Motivo:

```txt
BeautifulSoup e mais leve e barato
Playwright consome mais CPU, memoria e tempo
```

Playwright somente executa quando:

```txt
BeautifulSoup gera erro recuperavel
ou
validacao decide FALLBACK
```

---

## 9. Instalacao

Instalar dependencias Python:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Instalar Chromium:

```powershell
.\venv\Scripts\python.exe -m playwright install chromium
```

Essa segunda etapa e obrigatoria em toda maquina ou container que executa o
scraper worker.

Instalar somente o pacote Python nao instala automaticamente o executavel do
navegador.

---

## 10. Testes

Testes unitarios adicionados:

```txt
Playwright devolve ScrapingOutput padronizado
subrequest insegura e bloqueada
DOM renderizado respeita limite de tamanho
factory configura BeautifulSoup antes de Playwright
```

Os testes unitarios usam um Playwright falso e nao abrem navegador real.

Tambem foi executada validacao manual com Chromium real:

```txt
URL:
https://www.ibm.com/think/topics/artificial-intelligence

status = 200
method = playwright
texto renderizado = 28620 caracteres
```

Fallback real validado:

```txt
BeautifulSoup = failed
Playwright = accepted
quality_score = 0.9798
```

---

## 11. Como executar

Subir infraestrutura:

```powershell
docker compose -f infra\docker-compose.yml up -d postgres redis
```

Iniciar API:

```powershell
.\venv\Scripts\python.exe -m uvicorn apps.api.src.main:app --reload --port 8000
```

Iniciar worker com Chromium instalado:

```powershell
.\venv\Scripts\python.exe workers\scraper_worker\run.py
```

O worker utilizara Playwright automaticamente quando a pipeline decidir pelo
fallback.

---

## 12. Limitacoes conhecidas

```txt
Chromium aumenta consumo de memoria e CPU
cada tentativa inicia um novo navegador
nao existe pool de browsers
nao existe bloqueio seletivo de imagens, fontes ou analytics
nao existe espera especifica por seletor de cada fonte
nao existe configuracao de proxy
nao existe tratamento especializado de captcha
selector ainda usa uma ordem fixa para todas as URLs
```

O Chromium ainda nao esta configurado em um container dedicado para o worker.

---

## 13. Proximos passos recomendados

### Otimizar Playwright

```txt
reutilizar browser entre jobs com isolamento por contexto
bloquear recursos desnecessarios
medir memoria e tempo por tentativa
definir concorrencia segura do worker
```

### Melhorar StrategySelector

```txt
detectar dominios conhecidos por depender de JavaScript
selecionar Playwright primeiro apenas quando fizer sentido
usar historico de sucesso por dominio
```

### Adicionar Trafilatura

```txt
melhorar extracao de artigos e noticias
```

### Melhorar validacao deterministica

```txt
detectar javascript_required automaticamente
detectar boilerplate
calibrar thresholds com paginas reais
```

---

## 14. Criterio de conclusao da V4

A V4 pode ser considerada concluida porque demonstra:

```txt
PlaywrightScraper real implementando a porta Scraper
Chromium assincrono e headless
execucao de JavaScript
protecao SSRF para requisicoes do navegador
limites e erros traduzidos
factory com BeautifulSoup e Playwright
fallback real entre tecnologias
tentativas separadas por estrategia
teste com navegador real
```

Resumo:

```txt
V1 provou o comportamento.
V2 tornou o estado duravel.
V3 separou API e worker.
V4 adicionou fallback real com navegador.
```

