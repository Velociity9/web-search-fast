from __future__ import annotations

import logging
from urllib.parse import quote_plus

from playwright.async_api import Page

from src.api.schemas import SearchResult
from src.engine.base import BaseSearchEngine

logger = logging.getLogger(__name__)


class DuckDuckGoSearchEngine(BaseSearchEngine):
    """DuckDuckGo search engine implementation."""

    name: str = "duckduckgo"

    def build_search_url(self, query: str, page: int = 1) -> str:
        """Build DuckDuckGo search URL."""
        encoded_query = quote_plus(query)
        # Use HTML-only mode to avoid JS-heavy SPA rendering issues
        return f"https://html.duckduckgo.com/html/?q={encoded_query}"

    async def search(self, page: Page, query: str, max_results: int = 10) -> list[SearchResult]:
        """Override to use HTML-lite version which is more reliable."""
        url = self.build_search_url(query)
        await self._navigate(page, url, retries=1, timeout=10_000)
        await page.wait_for_timeout(300)
        return await self.parse_results(page, max_results)

    async def parse_results(self, page: Page, max_results: int = 10) -> list[SearchResult]:
        """Parse search results from DuckDuckGo SERP."""
        results: list[SearchResult] = []

        # html.duckduckgo.com selectors
        elements = await page.query_selector_all("div.result")
        if not elements:
            # Fallback: JS version selectors
            elements = await page.query_selector_all('article[data-testid="result"]')
        if not elements:
            elements = await page.query_selector_all("div.results div.result__body")
        if not elements:
            logger.warning("No DuckDuckGo result elements found on page")
            await self._dump_page_diagnostics(page)
            return results

        for element in elements:
            if len(results) >= max_results:
                break
            try:
                # html.duckduckgo.com selectors
                link_el = await element.query_selector("a.result__a")
                if not link_el:
                    # JS version selectors
                    link_el = await element.query_selector('a[data-testid="result-title-a"]')
                if not link_el:
                    link_el = await element.query_selector("h2 a")
                if not link_el:
                    continue

                title = (await link_el.inner_text()).strip()
                url = await link_el.get_attribute("href")
                if not title or not url or not url.startswith("http"):
                    continue

                # Extract snippet
                snippet = ""
                snippet_el = await element.query_selector("a.result__snippet")
                if not snippet_el:
                    snippet_el = await element.query_selector('div[data-result="snippet"] span')
                if not snippet_el:
                    snippet_el = await element.query_selector(
                        'span[data-testid="result-snippet"]'
                    )
                if not snippet_el:
                    snippet_el = await element.query_selector("span.result__snippet")
                if snippet_el:
                    snippet = (await snippet_el.inner_text()).strip()

                results.append(SearchResult(title=title, url=url, snippet=snippet))
            except Exception:
                logger.debug(
                    "Failed to parse a DuckDuckGo result element, skipping", exc_info=True
                )
                continue

        return results
