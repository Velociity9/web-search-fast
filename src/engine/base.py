from __future__ import annotations

import abc
import logging
import time

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
            # Dump first 2000 chars of HTML for structure inspection
            logger.warning(
                "[%s] DIAGNOSTIC — HTML head (2000 chars):\n%s",
                self.name, html[:2000],
            )
            # List body's direct children tags + classes via JS
            try:
                children_info = await page.evaluate("""() => {
                    const body = document.body;
                    if (!body) return 'NO BODY';
                    return Array.from(body.children).slice(0, 20).map(el => {
                        const tag = el.tagName.toLowerCase();
                        const cls = el.className ? '.' + el.className.split(' ').join('.') : '';
                        const id = el.id ? '#' + el.id : '';
                        const childCount = el.children.length;
                        return `${tag}${id}${cls} (${childCount} children)`;
                    }).join('\\n');
                }""")
                logger.warning(
                    "[%s] DIAGNOSTIC — body children:\n%s",
                    self.name, children_info,
                )
            except Exception as js_exc:
                logger.warning("[%s] DIAGNOSTIC — JS eval failed: %s", self.name, js_exc)
            # Check for common blocking indicators
            lower_html = html[:10000].lower()
            if "captcha" in lower_html or "/sorry/" in url:
                logger.warning("[%s] DIAGNOSTIC — CAPTCHA/block detected", self.name)
            if "consent" in lower_html or "cookie" in lower_html[:3000]:
                logger.warning("[%s] DIAGNOSTIC — consent/cookie page may be blocking", self.name)
            # Log a sample of the body around result areas
            for marker in ["id=\"rso\"", "class=\"g\"", "b_algo", "result__a", "data-testid",
                           "web_regular_results", "results--main", "div.result"]:
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
            t0 = time.monotonic()
            try:
                logger.info("[%s] nav attempt %d/%d → %s (timeout=%dms)",
                            self.name, attempt + 1, retries + 1, url[:120], timeout)
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                elapsed = (time.monotonic() - t0) * 1000
                status = resp.status if resp else "no-response"
                logger.info("[%s] nav done in %.0fms — HTTP %s", self.name, elapsed, status)
                if resp and resp.status >= 400:
                    logger.warning("[%s] HTTP %d for %s", self.name, resp.status, url)
                return
            except Exception as exc:
                elapsed = (time.monotonic() - t0) * 1000
                last_err = exc
                logger.warning(
                    "[%s] nav attempt %d/%d failed after %.0fms (%s: %s)",
                    self.name, attempt + 1, retries + 1, elapsed,
                    type(exc).__name__, str(exc)[:200],
                )
                if attempt < retries:
                    try:
                        await page.goto("about:blank", timeout=3000)
                    except Exception:
                        pass
                    continue
        raise last_err  # type: ignore[misc]

    async def search(self, page: Page, query: str, max_results: int = 10) -> list[SearchResult]:
        """Execute search: navigate to URL and parse results."""
        t0 = time.monotonic()
        url = self.build_search_url(query)
        logger.info("[%s] search start: query=%r max_results=%d", self.name, query[:80], max_results)
        await self._navigate(page, url)
        await page.wait_for_timeout(1000)
        results = await self.parse_results(page, max_results)
        elapsed = (time.monotonic() - t0) * 1000
        logger.info("[%s] search done in %.0fms — %d results", self.name, elapsed, len(results))
        if not results:
            await self._dump_page_diagnostics(page)
        return results
