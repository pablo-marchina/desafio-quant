from scraper.api.services.job_manager import JobManager
from scraper.api.services.nvidia_recommendation_service import (
    NvidiaRecommendationService,
)
from scraper.api.services.competitive_analysis_service import (
    CompetitiveAnalysisService,
)
from scraper.api.services.action_report_service import ActionReportService
from scraper.api.services.pipeline_runner import PipelineRunner
from scraper.api.services.startup_service import StartupService
from scraper.api.services.technology_intelligence_service import (
    TechnologyIntelligenceService,
)

job_manager = JobManager()
pipeline_runner = PipelineRunner()
supabase_service = StartupService()
technology_intelligence_service = TechnologyIntelligenceService(
    supabase_service
)
nvidia_recommendation_service = NvidiaRecommendationService(supabase_service)
competitive_analysis_service = CompetitiveAnalysisService(supabase_service)
action_report_service = ActionReportService(supabase_service)
