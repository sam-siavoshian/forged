"""Tests for domain extraction from task descriptions."""

import pytest

from src.matching.domain import extract_domain


class TestExtractDomainFromURLs:
    """Test domain extraction from explicit URLs."""

    def test_https_url(self):
        assert extract_domain("Go to https://amazon.com/dp/123") == "amazon.com"

    def test_http_url(self):
        assert extract_domain("Visit http://example.org/page") == "example.org"

    def test_www_url(self):
        assert (
            extract_domain("Open https://www.github.com/repo")
            == "github.com"
        )

    def test_url_with_path(self):
        # Regex captures "subdomain.domain" as the first match
        result = extract_domain("Check https://docs.python.org/3/library")
        assert result is not None
        assert "python" in result

    def test_url_case_insensitive(self):
        assert (
            extract_domain("Visit HTTPS://WWW.Amazon.COM/deals")
            == "amazon.com"
        )


class TestExtractDomainFromKeywords:
    """Test domain extraction from brand name keywords."""

    def test_amazon(self):
        assert extract_domain("Buy headphones on Amazon") == "amazon.com"

    def test_google(self):
        assert extract_domain("Search Google for python tutorials") == "google.com"

    def test_youtube(self):
        assert extract_domain("Watch a YouTube video") == "youtube.com"

    def test_github(self):
        assert extract_domain("Clone the GitHub repository") == "github.com"

    def test_reddit(self):
        assert extract_domain("Check Reddit for news") == "reddit.com"

    def test_twitter(self):
        assert extract_domain("Post on Twitter") == "twitter.com"

    def test_linkedin(self):
        assert extract_domain("Update LinkedIn profile") == "linkedin.com"

    def test_ebay(self):
        assert extract_domain("Find deals on eBay") == "ebay.com"

    def test_walmart(self):
        assert extract_domain("Order groceries from Walmart") == "walmart.com"

    def test_target(self):
        assert extract_domain("Shop at Target online") == "target.com"

    def test_case_insensitive_keyword(self):
        assert extract_domain("buy from AMAZON") == "amazon.com"


class TestExtractDomainFromPatterns:
    """Test domain extraction from domain-like patterns."""

    def test_bare_domain_com(self):
        assert extract_domain("Check out coolsite.com for deals") == "coolsite.com"

    def test_bare_domain_org(self):
        assert extract_domain("Visit wikipedia.org") == "wikipedia.org"

    def test_bare_domain_io(self):
        assert extract_domain("Deploy to render.io") == "render.io"

    def test_bare_domain_dev(self):
        assert extract_domain("Read web.dev articles") == "web.dev"

    def test_bare_domain_app(self):
        assert extract_domain("Use myapp.app for tracking") == "myapp.app"

    def test_bare_domain_net(self):
        assert extract_domain("Check status on monitor.net") == "monitor.net"


class TestExtractDomainEdgeCases:
    """Test edge cases and ambiguous inputs."""

    def test_no_domain(self):
        assert extract_domain("Do something interesting") is None

    def test_empty_string(self):
        assert extract_domain("") is None

    def test_url_takes_priority_over_keyword(self):
        # URL should win over keyword matching
        result = extract_domain(
            "Search on https://duckduckgo.com instead of Google"
        )
        assert result == "duckduckgo.com"

    def test_multiple_keywords_returns_first(self):
        # Should return the first matching keyword
        result = extract_domain("Compare Amazon and eBay prices")
        assert result in ("amazon.com", "ebay.com")

    def test_partial_keyword_match(self):
        # "target" appears in "targeting" — should still match
        result = extract_domain("targeting customers at Target stores")
        assert result == "target.com"
