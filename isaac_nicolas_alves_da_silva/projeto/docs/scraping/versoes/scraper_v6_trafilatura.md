# Scraper V6 - Trafilatura

## 1. Objetivo

A V6 adiciona uma estrategia especializada em extrair o conteudo principal de:

```txt
artigos
noticias
blogs
paginas editoriais
```

BeautifulSoup extrai todo o texto visivel. Trafilatura tenta separar o artigo
de menus, rodapes, barras laterais e outros elementos repetitivos.

---

## 2. Ordem das estrategias

A factory configura:

```txt
1. BeautifulSoup
2. Trafilatura
3. Playwright
```

Motivo:

```txt
BeautifulSoup
-> coleta simples e barata

Trafilatura
-> melhora HTML estatico com excesso de boilerplate

Playwright
-> navegador mais caro para paginas dependentes de JavaScript
```

Trafilatura somente executa quando a validacao da tentativa anterior pede
fallback ou quando ocorre uma falha recuperavel.

---

## 3. Arquitetura

Arquivo principal:

```txt
infrastructure/scrapers/trafilatura_scraper.py
```

`TrafilaturaScraper` implementa a porta `Scraper` e devolve `ScrapingOutput`,
como as outras estrategias.

Ela recebe outro scraper como fonte:

```txt
TrafilaturaScraper
-> source_scraper baixa HTML
-> Trafilatura extrai texto principal
-> devolve ScrapingOutput com method=trafilatura
```

Na factory, o `source_scraper` e o `BeautifulSoupScraper`.

Essa composicao reutiliza:

```txt
UrlGuard
protecao SSRF
redirects seguros
timeout HTTP
limite de resposta
User-Agent
```

Trafilatura nao realiza downloads diretamente.

---

## 4. Execucao assincrona

`trafilatura.extract` e uma funcao sincrona.

Ela e executada com:

```python
await asyncio.to_thread(...)
```

Assim, a extracao nao bloqueia o event loop da API ou do worker.

---

## 5. Opcoes de extracao

Configuracao atual:

```txt
output_format = txt
include_comments = false
include_tables = true
favor_precision = true
```

`favor_precision` foi escolhido porque o scraper deve evitar incorporar menus
e textos laterais ao conteudo aprovado.

Se nenhum conteudo principal for encontrado:

```txt
ContentExtractionError
-> erro recuperavel
-> pipeline pode tentar Playwright
```

---

## 6. HTML original e texto extraido

O resultado preserva:

```txt
raw_html = HTML original para auditoria
raw_text = conteudo principal extraido
```

Metadados adicionados:

```json
{
  "extraction_engine": "trafilatura",
  "main_content_extracted": true
}
```

Quando `main_content_extracted` e verdadeiro, o `TextualValidator` nao penaliza
o texto pelos menus presentes no HTML original. A estrutura ja foi tratada pelo
extrator especializado.

---

## 7. Dominio

Novo metodo reconhecido:

```txt
ScrapingMethod.TRAFILATURA = "trafilatura"
```

Nova excecao:

```txt
ContentExtractionError
```

Ela herda de `RecoverableScrapingError`, permitindo fallback.

---

## 8. Dependencia

Adicionada ao `requirements.txt`:

```txt
trafilatura>=2.0,<3
```

Instalacao:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 9. Testes

Os testes verificam:

```txt
extracao do conteudo principal com a biblioteca real
preservacao dos dados da coleta original
metadados de extracao
falha recuperavel quando nenhum texto e encontrado
validador nao penaliza HTML original depois da extracao
ordem BeautifulSoup -> Trafilatura -> Playwright
```

Estado da suite ao concluir a V6:

```txt
100 testes passando
```

---

## 10. Limitacoes conhecidas

```txt
Trafilatura baixa novamente o HTML durante o fallback
nao existe cache de ScrapingOutput entre tentativas
nao existe StrategySelector por tipo de fonte
Trafilatura pode remover conteudo util de paginas que nao sao editoriais
nao existe comparacao historica de qualidade por dominio
```

---

## 11. Proximos passos

Melhorias recomendadas:

```txt
reutilizar HTML entre BeautifulSoup e Trafilatura
detectar URLs de artigos e noticias no StrategySelector
comparar scores por estrategia e dominio
adicionar fixtures reais anonimizadas de fontes diferentes
```

Depois da extracao:

```txt
validacao semantica com LLM para casos ambiguos
integracao com ingestion
chunking
embeddings e banco vetorial
```

---

## 12. Criterio de conclusao da V6

A V6 esta concluida quando:

```txt
Trafilatura implementa a porta Scraper
download continua protegido pelas regras existentes
extracao sincrona nao bloqueia o event loop
falhas permitem fallback
texto principal e validado sem perder o HTML original
factory e testes incluem a nova estrategia
```
