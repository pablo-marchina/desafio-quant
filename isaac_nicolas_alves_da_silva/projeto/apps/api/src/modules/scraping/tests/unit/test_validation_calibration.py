"""Cenarios representativos usados para calibrar a validacao deterministica."""

import pytest

from apps.api.src.modules.scraping.application.dto import ScrapingOutput
from apps.api.src.modules.scraping.application.quality_scoring_service import (
    QualityScoringService,
)
from apps.api.src.modules.scraping.domain.enums import (
    ScrapingMethod,
    ValidationDecision,
)
from apps.api.src.modules.scraping.domain.policies import (
    ContentAcceptancePolicy,
    FallbackPolicy,
    ValidationDecisionPolicy,
)
from apps.api.src.modules.scraping.infrastructure.validators.composite_deterministic_validator import (
    CompositeDeterministicValidator,
)
from apps.api.src.modules.scraping.infrastructure.validators.evidence_validator import (
    EvidenceValidator,
)
from apps.api.src.modules.scraping.infrastructure.validators.technical_validator import (
    TechnicalValidator,
)
from apps.api.src.modules.scraping.infrastructure.validators.textual_validator import (
    TextualValidator,
)


def make_output(
    raw_html: str,
    raw_text: str,
    *,
    title: str = "Pagina",
    url: str = "https://example.com",
) -> ScrapingOutput:
    return ScrapingOutput(
        source_url=url,
        final_url=url,
        title=title,
        raw_html=raw_html,
        raw_text=raw_text,
        status_code=200,
        content_type="text/html",
        method=ScrapingMethod.BEAUTIFULSOUP,
    )


async def decide(
    output: ScrapingOutput,
    *,
    has_next_strategy: bool = True,
) -> tuple[ValidationDecision, set[str]]:
    """Executa a mesma cadeia de validacao e decisao usada pela pipeline."""

    validator = CompositeDeterministicValidator(
        TechnicalValidator(),
        TextualValidator(),
        EvidenceValidator(),
    )
    validation = QualityScoringService().calculate(await validator.validate(output))
    decision = ValidationDecisionPolicy(
        ContentAcceptancePolicy(),
        FallbackPolicy(),
    ).decide(validation.to_summary(), has_next_strategy=has_next_strategy)
    return decision, validation.problems


@pytest.mark.anyio
async def test_calibration_accepts_detailed_ai_product_landing_page() -> None:
    """Landing page detalhada de produto representa um resultado desejado."""

    description = (
        "Nossa plataforma de inteligencia artificial e machine learning "
        "analisa documentos empresariais, automatiza processos operacionais "
        "e ajuda equipes financeiras a detectar riscos antecipadamente. "
        "O produto permite integrar dados por API, classificar contratos, "
        "comparar indicadores, gerar relatorios auditaveis e otimizar decisoes. "
        "Clientes conectam fontes internas com seguranca, acompanham resultados "
        "em paineis personalizados e configuram fluxos para diferentes setores. "
        "Modelos de linguagem apoiam especialistas sem substituir revisoes "
        "humanas, oferecendo rastreabilidade, controle e produtividade."
    )
    text = f"{description} {description} {description}"

    decision, problems = await decide(
        make_output(f"<main><article>{text}</article></main>", text)
    )

    assert decision is ValidationDecision.ACCEPT
    assert problems == set()


@pytest.mark.anyio
async def test_calibration_rejects_article_that_only_mentions_ai() -> None:
    """Artigo geral sobre IA nao deve parecer uma empresa com produto de IA."""

    text = (
        "Este artigo discute artificial intelligence no mercado e apresenta "
        "contexto historico para leitores interessados no assunto. "
    ) * 15

    decision, _ = await decide(
        make_output(f"<article>{text}</article>", text, title="Artigo"),
        has_next_strategy=False,
    )

    assert decision is ValidationDecision.REJECT


@pytest.mark.anyio
async def test_calibration_accepts_independent_news_without_ai_pitch() -> None:
    """Noticia independente e valida para enriquecer fonte mesmo sem pitch de IA."""

    paragraph = (
        "A Acme Startup captou uma rodada seed para acelerar o produto de "
        "analise operacional usado por clientes dos setores financeiro e "
        "varejo. A empresa informou que vai ampliar o time tecnico, expandir "
        "integracoes por API e atender novas contas corporativas no Brasil. "
        "Fundadores e investidores afirmam que a solucao reduz tempo de "
        "processamento, organiza documentos e melhora decisoes de negocio."
    )
    text = f"{paragraph} {paragraph} {paragraph}"

    decision, problems = await decide(
        make_output(
            f"<article>{text}</article>",
            text,
            title="Acme Startup capta rodada seed",
            url="https://exame.com/negocios/acme-startup-capta-rodada",
        ),
        has_next_strategy=False,
    )

    assert decision is ValidationDecision.ACCEPT
    assert problems == set()


@pytest.mark.anyio
async def test_calibration_accepts_technical_hiring_page_without_ai_pitch() -> None:
    """Vagas e paginas tecnicas revelam stack/workload, mesmo sem texto de IA."""

    paragraph = (
        "A vaga de engenharia backend da Acme descreve servicos em Python, "
        "pipelines de dados, integracoes por API, observabilidade, Kubernetes, "
        "bancos relacionais e processamento em lote para produtos usados por "
        "clientes empresariais. O time trabalha com revisao de codigo, testes "
        "automatizados, deploy continuo e melhoria de performance."
    )
    text = f"{paragraph} {paragraph} {paragraph}"

    decision, problems = await decide(
        make_output(
            f"<main>{text}</main>",
            text,
            title="Backend Engineer - Acme",
            url="https://jobs.lever.co/acme/backend-engineer",
        ),
        has_next_strategy=False,
    )

    assert decision is ValidationDecision.ACCEPT
    assert problems == set()


@pytest.mark.anyio
async def test_calibration_rejects_link_directory_even_with_ai_terms() -> None:
    """Diretorio de links nao deve ser aceito pelo volume de palavras-chave."""

    links = " ".join(
        f"<a href='/{index}'>AI platform product analyzes data {index}</a>"
        for index in range(100)
    )
    text = " ".join(
        f"AI platform product analyzes data {index}" for index in range(100)
    )

    decision, problems = await decide(
        make_output(f"<main>{links}</main>", text),
        has_next_strategy=False,
    )

    assert decision is ValidationDecision.REJECT
    assert "link_farm" in problems


@pytest.mark.anyio
async def test_calibration_falls_back_for_javascript_shell() -> None:
    """Shell vazio deve solicitar uma estrategia que renderize JavaScript."""

    html = (
        "<div id='root'></div>"
        "<noscript>You need to enable JavaScript</noscript>"
    )

    decision, problems = await decide(make_output(html, "Enable JavaScript"))

    assert decision is ValidationDecision.FALLBACK
    assert "javascript_required" in problems


@pytest.mark.anyio
async def test_calibration_falls_back_for_short_page() -> None:
    """Pagina curta pode melhorar com outra estrategia antes de ser rejeitada."""

    text = "AI platform that analyzes documents."

    decision, problems = await decide(make_output(f"<main>{text}</main>", text))

    assert decision is ValidationDecision.FALLBACK
    assert "insufficient_text" in problems
