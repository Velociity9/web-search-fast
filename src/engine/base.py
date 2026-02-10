from __future__ import annotations

import abc

from playwright.async_api import Page

from src.api.schemas import SearchResult


class BaseSearchEngine(abc.ABC):
    """Abstract base class for search engines."""

    name: str = ""

    @abc.abstractmethod
    def build_search_url(self, query: str, page: int = 1) -> str:
        """Build the search URL for the given query."""
        ...

    @abc.abstractmethod
    async def parse_results(self, page: Page, max_results: int = 10) -> list[SearchResult]:
        """Parse search results from the SERP page."""
        ...

    async def search(self, page: Page, query: str, max_results: int = 10) -> list[SearchResult]:
        """Execute search: navigate to URL and parse results."""
        url = self.build_search_url(query)
        await page.goto(url, timeout=30000)
        # Wait for JS rendering to complete
        await page.wait_for_load_state("networkidle", timeout=15000)
        return await self.parse_results(page, max_results)
