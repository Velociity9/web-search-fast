from __future__ import annotations

import logging
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from playwright.async_api import Page

from src.api.schemas import SearchResult
from src.engine.base import BaseSearchEngine

logger = logging.getLogger(__name__)


def _resolve_ddg_url(raw_url: str) -> str | None:
    """Extract the real destination URL from a DuckDuckGo redirect link.

    DDG HTML-lite hrefs look like:
      //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com&rut=...
    We need to pull the actual URL from the ``uddg`` query parameter.
    Protocol-relative URLs (``//...``) are also normalised.
    """
    if not raw_url:
        return None

    # Normalise protocol-relative URLs
    if raw_url.startswith("//"):
        raw_url = "https:" + raw_url

    # Already a direct http(s) link — return as-is
    if raw_url.startswith("http") and "duckduckgo.com/l/" not in raw_url:
        return raw_url

    # Extract uddg parameter from DDG redirect
    try:
        parsed = urlparse(raw_url)
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg", [None])[0]
        if uddg:
            return unquote(uddg)
    except Exception:
        pass

    # Fallback: if it's a valid http URL, return it
    if raw_url.startswith("http"):
        return raw_url

    return None


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
            logger.warning("[duckduckgo] no result elements found on page")
            await self._dump_page_diagnostics(page)
            return results

        logger.info("[duckduckgo] found %d result elements", len(elements))

        for idx, element in enumerate(elements):
            if len(results) >= max_results:
                break
            try:
                # html.duckduckgo.com selectors
                link_el = await element.query_selector("a.result__a")
                if not link_el:
                    link_el = await element.query_selector('a[data-testid="result-title-a"]')
                if not link_el:
                    link_el = await element.query_selector("h2 a")
                if not link_el:
                    logger.debug("[duckduckgo] element #%d: no link found, skipping", idx)
                    continue

                title = (await link_el.inner_text()).strip()
                raw_href = await link_el.get_attribute("href")
                url = _resolve_ddg_url(raw_href)

                if not title or not url:
                    logger.debug("[duckduckgo] element #%d: empty title=%r or url=%r (raw=%r), skipping",
                                 idx, title[:30] if title else None, url, raw_href[:80] if raw_href else None)
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
                    "[duckduckgo] element #%d: parse failed, skipping", idx, exc_info=True
                )
                continue

        logger.info("[duckduckgo] extracted %d valid results from %d elements", len(results), len(elements))
        return results
