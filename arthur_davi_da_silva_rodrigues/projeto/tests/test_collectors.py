import httpx

from app.collectors.html import extract_main_text, extract_title
from app.collectors.source_types import classify_source_type
from app.collectors.url import collect_url, normalize_public_url, plan_url_collection
from app.models.enums import SourceType


def test_classify_source_type_for_known_public_sources() -> None:
    assert classify_source_type("https://neofeed.com.br/startups/example") == SourceType.NEWS
    assert classify_source_type("https://distrito.me/startups/example") == SourceType.DIRECTORY
    assert classify_source_type("https://startup.com/careers") == SourceType.CAREERS
    assert classify_source_type("https://startup.com/blog/ai") == SourceType.BLOG
    assert classify_source_type("https://startup.com") == SourceType.OFFICIAL_SITE


def test_normalize_public_url_adds_https_when_scheme_is_missing() -> None:
    assert normalize_public_url("startup.com") == "https://startup.com"
    assert normalize_public_url("http://startup.com") == "http://startup.com"


def test_plan_url_collection_marks_fetch_intent() -> None:
    plan = plan_url_collection("startup.com/blog", should_fetch=True)

    assert plan.url == "https://startup.com/blog"
    assert plan.source_type == SourceType.BLOG
    assert plan.should_fetch is True


def test_extract_title_and_main_text_from_html() -> None:
    html = """
    <html>
      <head><title>Example Startup</title><script>bad()</script></head>
      <body>
        <main>
          <h1>Example Startup</h1>
          <p>We automate healthcare workflows with AI agents.</p>
        </main>
      </body>
    </html>
    """

    assert extract_title(html) == "Example Startup"
    assert "healthcare workflows" in extract_main_text(html)
    assert "bad()" not in extract_main_text(html)


def test_collect_url_with_mocked_http_client() -> None:
    html = (
        "<html><head><title>AI Co</title></head>"
        "<body><p>AI support automation.</p></body></html>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == "test-agent"
        return httpx.Response(200, text=html, request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        collected_document = collect_url(
            "https://aico.example",
            user_agent="test-agent",
            client=client,
        )

    assert collected_document.scrape_status == "succeeded"
    assert collected_document.title == "AI Co"
    assert collected_document.source_type == SourceType.OFFICIAL_SITE
    assert "AI support automation" in collected_document.extracted_text
