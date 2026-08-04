"""Exceções conhecidas pelo domínio de scraping.

Essas exceções descrevem situações esperadas pelo negócio. Por exemplo:
solicitar um job inexistente ou tentar iniciar um job já concluído.

Elas não sabem como o erro será apresentado ao usuário. Posteriormente, a
camada ``presentation`` decidirá qual status HTTP corresponde a cada exceção.
"""


class ScrapingError(Exception):
    """Classe base para todos os erros conhecidos do módulo.

    Ter uma classe base permite capturar qualquer erro esperado do módulo sem
    esconder erros inesperados de programação.
    """


class InvalidJobTransitionError(ScrapingError):
    """O job tentou mudar para um estado que não é permitido.

    Exemplo: tentar mudar diretamente de ``pending`` para ``completed`` sem
    antes iniciar a execução.
    """


class ScrapingJobNotFoundError(ScrapingError):
    """O job de scraping solicitado não existe."""


class ScrapingResultNotFoundError(ScrapingError):
    """O resultado de scraping solicitado não existe."""


class TaskDispatchError(ScrapingError):
    """O job foi persistido, mas nao foi possivel publica-lo na fila."""


class ScrapingFailedError(ScrapingError):
    """Nenhuma estratégia conseguiu produzir conteúdo válido."""


class DuplicateScrapingContentError(ScrapingError):
    """O conteudo aprovado ja foi persistido por outro job de scraping."""


class RecoverableScrapingError(ScrapingError):
    """Falha técnica que permite tentar outra estratégia de coleta.

    Exemplo: BeautifulSoup recebeu timeout, mas Playwright ainda pode conseguir
    abrir a mesma página.
    """


class ScrapingLimitExceededError(RecoverableScrapingError):
    """Uma estratégia individual excedeu um de seus limites operacionais."""


class ScrapingRequestError(RecoverableScrapingError):
    """A requisição HTTP falhou por timeout, conexão ou protocolo."""


class ContentExtractionError(RecoverableScrapingError):
    """A coleta funcionou, mas a estrategia nao extraiu conteudo utilizavel."""


class SemanticValidationError(ScrapingError):
    """O provedor semantico falhou ou devolveu uma resposta invalida."""


class GlobalScrapingLimitExceededError(ScrapingError):
    """O job inteiro excedeu um limite e nenhuma estratégia deve continuar."""


class UnsafeUrlError(ScrapingError):
    """A URL foi recusada por ser inválida ou apresentar risco de SSRF."""


class ContentRejectedError(ScrapingFailedError):
    """O conteudo foi rejeitado apos revisao semantica ou investigacao do agente.

    Herda de ``ScrapingFailedError`` porque, do ponto de vista da pipeline,
    rejeitar o conteudo apos a investigacao do agente tambem significa que
    esta tentativa nao produziu um resultado aproveitavel. A pipeline ja
    sabe tratar ``ScrapingFailedError`` (nao tenta outra estrategia, pois
    rejeicao e uma decisao de negocio, nao uma falha tecnica recuperavel).
    """


class MoreSourcesRequiredError(ScrapingFailedError):
    """O agente concluiu que o conteudo atual nao basta; faltam mais fontes.

    Tambem herda de ``ScrapingFailedError`` pelo mesmo motivo: esta tentativa
    nao produz um ``ScrapingResult``. A diferenca fica registrada no
    ``AttemptStatus`` (``NEEDS_MORE_SOURCES``) e no motivo guardado na
    tentativa, permitindo que o fluxo global decida criar novos jobs de
    scraping para a mesma startup.
    """
