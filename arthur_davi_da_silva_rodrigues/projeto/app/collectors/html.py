from bs4 import BeautifulSoup
from trafilatura import extract


def extract_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title")
    if title and title.get_text(strip=True):
        return title.get_text(strip=True)

    heading = soup.find("h1")
    if heading and heading.get_text(strip=True):
        return heading.get_text(strip=True)

    return None


def extract_main_text(html: str) -> str:
    extracted_text = extract(html, include_comments=False, include_tables=False)
    if extracted_text:
        return _normalize_text(extracted_text)

    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    return _normalize_text(soup.get_text(" "))


def _normalize_text(text: str) -> str:
    return " ".join(text.split())
