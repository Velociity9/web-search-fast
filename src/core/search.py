"""Core search logic — framework-agnostic, used by both FastAPI and MCP server."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from src.api.schemas import (
    SearchMetadata,
    SearchRequest,
    SearchResponse,
)
from src.config import SearchEngine
from src.engine.base import BaseSearchEngine
from src.engine.bing import BingSearchEngine
from src.engine.duckduckgo import DuckDuckGoSearchEngine
from src.engine.google import GoogleSearchEngine
from src.scraper.browser import BrowserPool
from src.scraper.depth import crawl_results, fetch_page_content
from src.scraper.parser import extract_main_content_markdown

logger = logging.getLogger(__name__)


class SearchError(Exception):
    """Raised when a search cannot be performed."""


ENGINES: dict[SearchEngine, BaseSearchEngine] = {
    SearchEngine.GOOGLE: GoogleSearchEngine(),
    SearchEngine.BING: BingSearchEngine(),
    SearchEngine.DUCKDUCKGO: DuckDuckGoSearchEngine(),
}

FALLBACK_ORDER: dict[SearchEngine, list[SearchEngine]] = {
    SearchEngine.GOOGLE: [SearchEngine.DUCKDUCKGO, SearchEngine.BING],
    SearchEngine.BING: [SearchEngine.DUCKDUCKGO, SearchEngine.GOOGLE],
    SearchEngine.DUCKDUCKGO: [SearchEngine.BING, SearchEngine.GOOGLE],
}


async def do_search(pool: BrowserPool, req: SearchRequest) -> SearchResponse:
    """Execute a search with engine fallback and multi-depth crawling."""
    if not pool._started:
        raise SearchError("Browser pool not initialized")

    start = time.monotonic()
    used_engine = req.engine

    async with pool.acquire() as page:
        engine = ENGINES[req.engine]
        results = await engine.search(page, req.query, req.max_results)

        if not results:
            for fallback in FALLBACK_ORDER.get(req.engine, []):
                logger.info(
                    "Engine %s returned 0 results, falling back to %s",
                    req.engine.value,
                    fallback.value,
                )
                fb_engine = ENGINES[fallback]
                results = await fb_engine.search(page, req.query, req.max_results)
                if results:
                    used_engine = fallback
                    break

    results = await crawl_results(pool, results, depth=req.depth, timeout=req.timeout)
    elapsed = int((time.monotonic() - start) * 1000)

    return SearchResponse(
        query=req.query,
        engine=used_engine,
        depth=req.depth,
        total=len(results),
        results=results,
        metadata=SearchMetadata(
            elapsed_ms=elapsed,
            timestamp=datetime.now(timezone.utc).isoformat(),
            engine=used_engine,
            depth=req.depth,
        ),
    )


async def fetch_url_content(pool: BrowserPool, url: str, timeout: int = 30) -> str:
    """Fetch a single URL and return its main content as markdown."""
    async with pool.acquire() as page:
        html = await fetch_page_content(page, url, timeout)
        if not html:
            return ""
        return extract_main_content_markdown(html)
