from __future__ import annotations

import abc
import logging

from playwright.async_api import Page

from src.api.schemas import SearchResult

logger = logging.getLogger(__name__)


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

    async def _dump_page_diagnostics(self, page: Page) -> None:
        """Log diagnostic info when no results are found — helps debug selector/rendering issues."""
        try:
            url = page.url
            title = await page.title()
            html = await page.content()
            body_len = len(html)
            # Log key identifiers to help debug
            logger.warning(
                "[%s] DIAGNOSTIC — url=%s title=%r body_len=%d",
                self.name, url, title, body_len,
            )
            # Check for common blocking indicators
            lower_html = html[:10000].lower()
            if "captcha" in lower_html or "/sorry/" in url:
                logger.warning("[%s] DIAGNOSTIC — CAPTCHA/block detected", self.name)
            if "consent" in lower_html or "cookie" in lower_html[:3000]:
                logger.warning("[%s] DIAGNOSTIC — consent/cookie page may be blocking", self.name)
            # Log a sample of the body around result areas
            for marker in ["id=\"rso\"", "class=\"g\"", "b_algo", "result__a", "data-testid"]:
                pos = html.find(marker)
                if pos >= 0:
                    logger.warning(
                        "[%s] DIAGNOSTIC — found '%s' at pos %d: ...%s...",
                        self.name, marker, pos, html[max(0, pos - 50):pos + 200].replace("\n", " "),
                    )
        except Exception as exc:
            logger.warning("[%s] DIAGNOSTIC dump failed: %s", self.name, exc)

    async def _navigate(self, page: Page, url: str, retries: int = 1, timeout: int = 10_000) -> None:
        """Navigate with retry logic for transient failures."""
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                if resp and resp.status >= 400:
                    logger.warning("[%s] HTTP %d for %s", self.name, resp.status, url)
                return
            except Exception as exc:
                last_err = exc
                if attempt < retries:
                    logger.warning(
                        "[%s] nav attempt %d/%d failed (%s), retrying …",
                        self.name, attempt + 1, retries + 1, type(exc).__name__,
                    )
                    try:
                        await page.goto("about:blank", timeout=3000)
                    except Exception:
                        pass
                    continue
        raise last_err  # type: ignore[misc]

    async def search(self, page: Page, query: str, max_results: int = 10) -> list[SearchResult]:
        """Execute search: navigate to URL and parse results."""
        url = self.build_search_url(query)
        await self._navigate(page, url)
        # Wait for JS rendering — most SERPs need this
        await page.wait_for_timeout(1000)
        return await self.parse_results(page, max_results)
