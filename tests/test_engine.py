from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.engine.google import GoogleSearchEngine
from src.engine.bing import BingSearchEngine
from src.engine.duckduckgo import DuckDuckGoSearchEngine


class TestGoogleEngine:
    def test_build_url(self):
        engine = GoogleSearchEngine()
        url = engine.build_search_url("hello world")
        assert "google.com/search" in url
        assert "hello+world" in url or "hello%20world" in url

    def test_name(self):
        assert GoogleSearchEngine().name == "google"


class TestBingEngine:
    def test_build_url(self):
        engine = BingSearchEngine()
        url = engine.build_search_url("test query")
        assert "bing.com/search" in url
        assert "test" in url

    def test_name(self):
        assert BingSearchEngine().name == "bing"


class TestDuckDuckGoEngine:
    def test_build_url(self):
        engine = DuckDuckGoSearchEngine()
        url = engine.build_search_url("test query")
        assert "duckduckgo.com" in url
        assert "test" in url

    def test_name(self):
        assert DuckDuckGoSearchEngine().name == "duckduckgo"


class TestDDGUrlResolver:
    """Test _resolve_ddg_url which extracts real URLs from DDG redirect links."""

    def test_redirect_url_with_uddg(self):
        from src.engine.duckduckgo import _resolve_ddg_url
        raw = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage&rut=abc123"
        assert _resolve_ddg_url(raw) == "https://example.com/page"

    def test_protocol_relative_non_redirect(self):
        from src.engine.duckduckgo import _resolve_ddg_url
        raw = "//example.com/page"
        assert _resolve_ddg_url(raw) == "https://example.com/page"

    def test_direct_http_url(self):
        from src.engine.duckduckgo import _resolve_ddg_url
        assert _resolve_ddg_url("https://example.com") == "https://example.com"

    def test_empty_url(self):
        from src.engine.duckduckgo import _resolve_ddg_url
        assert _resolve_ddg_url("") is None
        assert _resolve_ddg_url(None) is None

    def test_redirect_with_encoded_uddg(self):
        from src.engine.duckduckgo import _resolve_ddg_url
        raw = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FHello&rut=x"
        assert _resolve_ddg_url(raw) == "https://en.wikipedia.org/wiki/Hello"

    def test_no_uddg_param(self):
        from src.engine.duckduckgo import _resolve_ddg_url
        raw = "https://duckduckgo.com/l/?foo=bar"
        # Falls back to returning the URL itself since it starts with http
        assert _resolve_ddg_url(raw) == "https://duckduckgo.com/l/?foo=bar"
