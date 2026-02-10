from __future__ import annotations

import logging
from urllib.parse import quote_plus

from playwright.async_api import Page

from src.api.schemas import SearchResult
from src.engine.base import BaseSearchEngine

logger = logging.getLogger(__name__)


class GoogleSearchEngine(BaseSearchEngine):
    """Google search engine implementation."""

    name: str = "google"

    def build_search_url(self, query: str, page: int = 1) -> str:
        """Build Google search URL."""
        encoded_query = quote_plus(query)
        start = (page - 1) * 10
        url = f"https://www.google.com/search?q={encoded_query}&num=10"
        if start > 0:
            url += f"&start={start}"
        return url

    async def parse_results(self, page: Page, max_results: int = 10) -> list[SearchResult]:
        """Parse search results from Google SERP."""
        results: list[SearchResult] = []

        # Detect if blocked by Google
        current_url = page.url
        if "/sorry/" in current_url or "captcha" in current_url.lower():
            logger.warning("Google blocked the request (captcha/sorry page), returning empty results")
            return results

        # Try multiple selectors for result containers
        elements = await page.query_selector_all("div#rso div.g")
        if not elements:
            elements = await page.query_selector_all("div#search div.g")
        if not elements:
            elements = await page.query_selector_all("div.g")
        if not elements:
            logger.warning("No Google result elements found on page")
            return results

        for element in elements:
            if len(results) >= max_results:
                break
            try:
                # Extract title
                title_el = await element.query_selector("h3")
                if not title_el:
                    continue
                title = (await title_el.inner_text()).strip()
                if not title:
                    continue

                # Extract URL
                link_el = await element.query_selector("a")
                if not link_el:
                    continue
                url = await link_el.get_attribute("href")
                if not url or not url.startswith("http"):
                    continue

                # Extract snippet via multiple selectors
                snippet = ""
                for selector in ("div[data-sncf]", "div.VwiC3b", "div.IsZvec"):
                    snippet_el = await element.query_selector(selector)
                    if snippet_el:
                        snippet = (await snippet_el.inner_text()).strip()
                        break

                results.append(SearchResult(title=title, url=url, snippet=snippet))
            except Exception:
                logger.debug("Failed to parse a Google result element, skipping", exc_info=True)
                continue

        return results
