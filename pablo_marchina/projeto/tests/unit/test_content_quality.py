"""Unit tests for src.scraping.content_quality."""

import pytest

from src.scraping.content_quality import ContentQualityValidator, QualityIssue


@pytest.fixture
def validator():
    return ContentQualityValidator()


def test_valid_content_passes(validator):
    html = "<html><body>" + "Startup de inteligência artificial focada em visão computacional para agronegócio." * 30 + "</body></html>"
    result = validator.validate(html)
    assert result.is_valid is True
    assert len(result.issues) == 0


def test_too_short_detected(validator):
    short = "<html>hi</html>"
    result = validator.validate(short)
    assert QualityIssue.TOO_SHORT in result.issues


def test_boilerplate_detected_access_denied(validator):
    html = "<html>Access Denied</html>" + " " * 500
    result = validator.validate(html)
    assert QualityIssue.BOILERPLATE in result.issues


def test_boilerplate_detected_404(validator):
    html = "<html>404 Not Found</html>" + " " * 500
    result = validator.validate(html)
    assert QualityIssue.BOILERPLATE in result.issues


def test_boilerplate_detected_cloudflare_check(validator):
    html = "<html>Checking your browser</html>" + " " * 500
    result = validator.validate(html)
    assert QualityIssue.BOILERPLATE in result.issues


def test_login_wall_detected(validator):
    text = "login sign in entrar log in authentication " * 5
    result = validator.validate(text)
    assert QualityIssue.LOGIN_WALL in result.issues


def test_paywall_detected(validator):
    text = "subscribe premium assine assinatura continue reading" * 5
    result = validator.validate(text)
    assert QualityIssue.PAYWALL in result.issues


def test_cloudflare_detected(validator):
    html = "<html>Cloudflare</html>" + " " * 500
    result = validator.validate(html)
    assert QualityIssue.CLOUDFLARE in result.issues


def test_cloudflare_detected_via_cf_ray(validator):
    html = "<html>cf-ray: abc123</html>" + " " * 500
    result = validator.validate(html)
    assert QualityIssue.CLOUDFLARE in result.issues


def test_empty_content(validator):
    result = validator.validate("")
    assert not result.is_valid


def test_mixed_issues(validator):
    text = "Access Denied login sign in entrar subscribe premium" + " A" * 300
    result = validator.validate(text)
    assert QualityIssue.BOILERPLATE in result.issues
    assert QualityIssue.LOGIN_WALL in result.issues
    assert QualityIssue.PAYWALL in result.issues
