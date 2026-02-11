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

    async def _navigate(self, page: Page, url: str, retries: int = 2) -> None:
        """Navigate with retry logic for transient failures."""
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                if resp and resp.status >= 400:
                    logger.warning("[%s] HTTP %d for %s", self.name, resp.status, url)
                # networkidle is best-effort — don't fail if it times out
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
                return
            except Exception as exc:
                last_err = exc
                if attempt < retries:
                    logger.warning(
                        "[%s] nav attempt %d/%d failed (%s), retrying …",
                        self.name, attempt + 1, retries + 1, type(exc).__name__,
                    )
                    # reset page before retry
                    try:
                        await page.goto("about:blank", timeout=5000)
                    except Exception:
                        pass
                    continue
        raise last_err  # type: ignore[misc]

    async def search(self, page: Page, query: str, max_results: int = 10) -> list[SearchResult]:
        """Execute search: navigate to URL and parse results."""
        url = self.build_search_url(query)
        await self._navigate(page, url)
        return await self.parse_results(page, max_results)
