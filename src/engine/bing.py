from __future__ import annotations

import logging
from urllib.parse import quote_plus

from playwright.async_api import Page

from src.api.schemas import SearchResult
from src.engine.base import BaseSearchEngine

logger = logging.getLogger(__name__)


class BingSearchEngine(BaseSearchEngine):
    """Bing search engine implementation."""

    name: str = "bing"

    def build_search_url(self, query: str, page: int = 1) -> str:
        """Build Bing search URL."""
        encoded_query = quote_plus(query)
        url = f"https://www.bing.com/search?q={encoded_query}&count=10"
        if page > 1:
            first = (page - 1) * 10 + 1
            url += f"&first={first}"
        return url

    async def parse_results(self, page: Page, max_results: int = 10) -> list[SearchResult]:
        """Parse search results from Bing SERP."""
        results: list[SearchResult] = []

        elements = await page.query_selector_all("li.b_algo")
        if not elements:
            logger.warning("No Bing result elements found on page")
            return results

        for element in elements:
            if len(results) >= max_results:
                break
            try:
                # Extract title and URL from h2 > a
                link_el = await element.query_selector("h2 a")
                if not link_el:
                    continue
                title = (await link_el.inner_text()).strip()
                url = await link_el.get_attribute("href")
                if not title or not url or not url.startswith("http"):
                    continue

                # Extract snippet
                snippet = ""
                snippet_el = await element.query_selector("div.b_caption p")
                if not snippet_el:
                    snippet_el = await element.query_selector("p")
                if snippet_el:
                    snippet = (await snippet_el.inner_text()).strip()

                results.append(SearchResult(title=title, url=url, snippet=snippet))
            except Exception:
                logger.debug("Failed to parse a Bing result element, skipping", exc_info=True)
                continue

        return results
