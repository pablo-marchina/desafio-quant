# Briefing V3 — Exportacao em PDF

Esta versao fecha o bloco 5 do `docs/frontend/roadmap_frontend.md`
(Frontend V3): exportar o briefing executivo como PDF real, preservando
as citacoes como links clicaveis.

## 1. Objetivo

```txt
briefing (Markdown persistido) -> PDF real, preservando citacoes
```

## 2. Decisao tecnica: Playwright+Jinja2 em vez de weasyprint

O roadmap original (`docs/frontend/roadmap_frontend.md`, bloco 5) previa
`weasyprint` + Jinja2. Essa troca foi feita durante a implementacao desta
entrega: `weasyprint` exige bibliotecas nativas (Pango/Cairo/GTK) sem
binario simples no Windows — risco real de instalacao no ambiente deste
projeto. `playwright` ja e' dependencia do projeto desde o Scraping V4
(`scraping/infrastructure/scrapers/playwright_scraper.py`) e ja funciona
comprovadamente neste ambiente Windows/WSL.

Resultado: mesmo objetivo (PDF real via motor de renderizacao real, nao
so HTML cru), motor diferente. Sem dependencia nativa nova.

## 3. Fluxo

```txt
GET /briefings/{briefing_id}/export
  -> ExportBriefingPdf.execute(briefing_id)
       busca o Briefing por id (repositorio existente)
       chama BriefingDocumentRenderer.render_pdf(view)
         -> markdown.markdown(content, extensions=["extra"])  (Markdown -> HTML)
         -> Jinja2 template (briefing.html.jinja)              (HTML completo)
         -> async_playwright() + chromium.launch(headless=True)
            + page.set_content(html) + page.pdf(format="A4")   (PDF real)
       devolve bytes + filename (briefing-{startup_id}.pdf)
  -> Response(media_type="application/pdf", Content-Disposition: attachment)
```

Links Markdown (`[texto](url)`) ja viram `<a href>` na conversao — isso e'
o que preserva as citacoes no PDF exportado, sem tratamento especial no
codigo.

## 4. Porta sem fallback (diferente do `NvidiaContextGrounder`)

```python
class BriefingDocumentRenderer(ABC):
    async def render_pdf(self, briefing: BriefingView) -> bytes: ...
```

`NvidiaContextGrounder` (Briefing V1, extensao RAG) e' best-effort —
implementacoes nunca levantam excecao, devolvem `None` quando a
fundamentacao falha. `BriefingDocumentRenderer` e' o oposto deliberado:
falha de renderizacao e' `BriefingRenderingError` real (mapeada para
HTTP 502), porque o usuario pediu um arquivo especifico e precisa saber
se ele nao foi gerado — nao ha "briefing sem PDF" silencioso que faca
sentido aqui.

## 5. Sem migration

Nao persiste nada novo — renderiza sob demanda a partir do `Briefing` ja
existente no Postgres. `briefings` continua com o mesmo schema desde a
V1.

## 6. Validacao

```txt
test_export_briefing_pdf.py        3 testes (sucesso, not found, erro do renderer)
test_jinja_playwright_pdf_renderer.py   1 teste (Chromium headless real,
                                    sem Postgres/Redis/Qdrant — adicionado
                                    a _NO_EXTERNAL_DEPS_INTEGRATION_TESTS
                                    em apps/api/src/modules/conftest.py)
```

Validado tambem fora da suite, via `httpx.AsyncClient` contra a app real
(criar startup -> recommendations -> briefing -> export): PDF de 28KB,
bytes comecam com `%PDF-1.4`.

Testes do modulo: 27 -> 30 unit, 1 -> 2 integracao.

## 6.1 Bug real encontrado e corrigido apos a entrega inicial

Testado pelo usuario via servidor `uvicorn` real (nao so pela suite de
testes): `GET /briefings/{id}/export` retornava 500 com
`NotImplementedError` em `asyncio.base_events.py::_make_subprocess_transport`.

Causa: no Windows, `ProactorEventLoop` suporta `create_subprocess_exec`
(usado pelo driver do Playwright para abrir o Chromium), mas o
`SelectorEventLoop` nao. O loop principal sob o `uvicorn` do usuario
estava rodando como `SelectorEventLoop` no momento da chamada — diferente
do loop usado pela suite de testes (pytest-anyio) e pelo script manual de
validacao usados antes da entrega, onde o loop principal por acaso ja era
`ProactorEventLoop` (padrao do `asyncio.run()` direto). Por isso o bug nao
apareceu na validacao original.

Corrigido tornando `JinjaPlaywrightPdfRenderer` independente da politica
de loop do processo principal: `render_pdf()` agora delega para
`loop.run_in_executor(None, ...)`, que roda o Playwright numa thread
dedicada com seu proprio `asyncio.ProactorEventLoop()` (Windows) criado
ali mesmo. Funciona com qualquer loop ambiente (Selector ou Proactor, com
ou sem `uvicorn --reload`). Validado reproduzindo a condicao exata do bug
(`asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`
+ chamada real ao renderer): PDF gerado normalmente.

## 7. Limites conhecidos

```txt
sem cache de PDF - cada chamada renderiza de novo (Chromium headless tem
custo de processo; aceitavel para o volume deste projeto, nao para alto trafego)

sem opcao de formato alternativo (so PDF; "HTML" do roadmap original nao
foi entregue separadamente - o Markdown ja e' visualizavel na propria
tela da startup)

template Jinja2 e' fixo (briefing.html.jinja) - sem opcao de tema/whitelabel
```

## 8. Proximo passo

```txt
Briefing V4 - revisao humana (aprovar/rejeitar, comentarios, trilha de
auditoria), ver Frontend V5 no roadmap_frontend.md
```
