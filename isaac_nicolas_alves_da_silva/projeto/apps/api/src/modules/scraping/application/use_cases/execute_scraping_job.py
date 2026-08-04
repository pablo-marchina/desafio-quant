"""Caso de uso responsavel por executar um job de scraping existente."""

from collections.abc import Callable
from uuid import UUID

from apps.api.src.modules.scraping.application.content_deduplication_service import (
    ContentDeduplicationService,
)
from apps.api.src.modules.scraping.application.scraping_pipeline import (
    ScrapingPipeline,
)
from apps.api.src.modules.scraping.application.unit_of_work import (
    ScrapingUnitOfWorkFactory,
)
from apps.api.src.modules.scraping.domain.entities import ScrapingJob
from apps.api.src.modules.scraping.domain.enums import JobStatus
from apps.api.src.modules.scraping.domain.exceptions import (
    DuplicateScrapingContentError,
    ScrapingError,
    ScrapingJobNotFoundError,
)
from apps.api.src.modules.scraping.domain.repositories import ScrapingAttemptRepository


# A pipeline precisa do repositorio de tentativas pertencente a transacao
# atual. Esta factory permite cria-la somente depois que a Unit of Work abrir.
ScrapingPipelineFactory = Callable[[ScrapingAttemptRepository], ScrapingPipeline]


class ExecuteScrapingJob:
    """Controla o ciclo de vida do job ao redor da pipeline."""

    def __init__(
        self,
        unit_of_work_factory: ScrapingUnitOfWorkFactory,
        pipeline_factory: ScrapingPipelineFactory,
    ) -> None:
        self.unit_of_work_factory = unit_of_work_factory
        self.pipeline_factory = pipeline_factory

    async def execute(self, job_id: UUID) -> ScrapingJob:
        """Executa o job identificado e retorna seu estado final."""

        async with self.unit_of_work_factory() as unit_of_work:
            job = await unit_of_work.job_repository.get_by_id(job_id)
            if job is None:
                raise ScrapingJobNotFoundError(
                    f"O job de scraping {job_id} nao foi encontrado."
                )

            # Filas trabalham com entrega "pelo menos uma vez", portanto a
            # mesma mensagem pode chegar novamente. Somente jobs pending podem
            # iniciar; os demais estados retornam sem repetir o scraping.
            if job.status is not JobStatus.PENDING:
                return job

            # Confirmamos running antes da operacao demorada. Assim, outras
            # sessoes conseguem consultar que o processamento ja comecou.
            job.start()
            await unit_of_work.job_repository.save(job)
            await unit_of_work.commit()

            pipeline = self.pipeline_factory(unit_of_work.attempt_repository)

            try:
                result = await pipeline.execute(
                    job.id, job.url, source_type=job.source_type
                )

                # A validacao garante qualidade. Esta consulta separada garante
                # que o conteudo aprovado tambem seja novo para o banco.
                deduplication_service = ContentDeduplicationService(
                    unit_of_work.result_repository
                )
                duplicate = await deduplication_service.find_duplicate(result)
                if duplicate is not None:
                    raise DuplicateScrapingContentError(
                        "O conteudo coletado ja foi persistido pelo resultado "
                        f"{duplicate.id}."
                    )

                # Resultado, tentativas e estado final compartilham a mesma
                # sessao e serao confirmados juntos no commit final.
                await unit_of_work.result_repository.save(result)
                job.complete(result.id)
            except ScrapingError as error:
                # Falhas conhecidas fazem parte do funcionamento esperado.
                job.fail(str(error))
            except Exception:
                # Registramos a falha antes de propagar bugs inesperados.
                job.fail("Ocorreu um erro interno inesperado durante o scraping.")
                await unit_of_work.job_repository.save(job)
                await unit_of_work.commit()
                raise

            await unit_of_work.job_repository.save(job)
            await unit_of_work.commit()
            return job
