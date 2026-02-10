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
