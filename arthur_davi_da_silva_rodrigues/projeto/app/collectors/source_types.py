from urllib.parse import urlparse

from app.models.enums import SourceType

DIRECTORY_DOMAINS = (
    "startse.com",
    "distrito.me",
    "latitud.com",
    "cubo.network",
    "acestartups.com.br",
    "endeavor.org.br",
    "abstartups.com.br",
    "bossainvest.com",
    "anjosdobrasil.net",
    "darwinstartups.com",
    "liga.ventures",
    "wow.ac",
    "inovativabrasil.com.br",
    "openstartups.net",
)

NEWS_DOMAINS = (
    "braziljournal.com",
    "neofeed.com.br",
    "exame.com",
    "startups.com.br",
    "revistapegn.globo.com",
    "valor.globo.com",
    "meioemensagem.com.br",
    "mobiletime.com.br",
)

FOUNDER_PROFILE_DOMAINS = ("linkedin.com", "github.com", "x.com", "twitter.com")


def classify_source_type(url: str) -> SourceType:
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname or ""
    normalized_host = hostname.removeprefix("www.")
    path = parsed_url.path.lower()

    if _host_matches(normalized_host, NEWS_DOMAINS):
        return SourceType.NEWS
    if _host_matches(normalized_host, DIRECTORY_DOMAINS):
        return SourceType.DIRECTORY
    if _host_matches(normalized_host, FOUNDER_PROFILE_DOMAINS):
        return SourceType.FOUNDER_PROFILE
    if "blog" in path:
        return SourceType.BLOG
    if "career" in path or "carreira" in path or "jobs" in path or "vagas" in path:
        return SourceType.CAREERS

    return SourceType.OFFICIAL_SITE


def _host_matches(hostname: str, domains: tuple[str, ...]) -> bool:
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)
