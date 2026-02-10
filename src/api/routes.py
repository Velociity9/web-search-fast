from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from src.api.schemas import (
    ErrorResponse,
    SearchMetadata,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from src.config import OutputFormat, SearchEngine
from src.engine.base import BaseSearchEngine
from src.engine.google import GoogleSearchEngine
from src.engine.bing import BingSearchEngine
from src.engine.duckduckgo import DuckDuckGoSearchEngine
from src.formatter.json_fmt import format_json
from src.formatter.markdown_fmt import format_markdown
from src.scraper.browser import BrowserPool
from src.scraper.depth import crawl_results

router = APIRouter()

_engines: dict[SearchEngine, BaseSearchEngine] = {
    SearchEngine.GOOGLE: GoogleSearchEngine(),
    SearchEngine.BING: BingSearchEngine(),
    SearchEngine.DUCKDUCKGO: DuckDuckGoSearchEngine(),
}

_pool: BrowserPool | None = None


def set_browser_pool(pool: BrowserPool) -> None:
    global _pool
    _pool = pool


def get_engine(engine: SearchEngine) -> BaseSearchEngine:
    return _engines[engine]


logger = logging.getLogger(__name__)

# Fallback order when primary engine returns no results
_fallback_order: dict[SearchEngine, list[SearchEngine]] = {
    SearchEngine.GOOGLE: [SearchEngine.DUCKDUCKGO, SearchEngine.BING],
    SearchEngine.BING: [SearchEngine.DUCKDUCKGO, SearchEngine.GOOGLE],
    SearchEngine.DUCKDUCKGO: [SearchEngine.BING, SearchEngine.GOOGLE],
}


async def _do_search(req: SearchRequest) -> SearchResponse:
    if _pool is None:
        raise HTTPException(status_code=503, detail="Browser pool not initialized")

    start = time.monotonic()
    used_engine = req.engine

    # Try primary engine, fallback if no results
    async with _pool.acquire() as page:
        engine = get_engine(req.engine)
        results = await engine.search(page, req.query, req.max_results)

        if not results:
            for fallback in _fallback_order.get(req.engine, []):
                logger.info(f"Engine {req.engine.value} returned 0 results, falling back to {fallback.value}")
                fb_engine = get_engine(fallback)
                results = await fb_engine.search(page, req.query, req.max_results)
                if results:
                    used_engine = fallback
                    break

    # Step 2+3: depth crawling
    results = await crawl_results(_pool, results, depth=req.depth, timeout=req.timeout)

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


@router.post("/search", response_model=SearchResponse)
async def search_post(req: SearchRequest):
    response = await _do_search(req)
    if req.format == OutputFormat.MARKDOWN:
        return PlainTextResponse(format_markdown(response), media_type="text/markdown")
    return format_json(response)


@router.get("/search")
async def search_get(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    engine: SearchEngine = Query(default=SearchEngine.GOOGLE),
    depth: int = Query(default=1, ge=1, le=3),
    format: OutputFormat = Query(default=OutputFormat.JSON),
    max_results: int = Query(default=10, ge=1, le=50),
    timeout: int = Query(default=30, ge=5, le=120),
):
    req = SearchRequest(
        query=q,
        engine=engine,
        depth=depth,
        format=format,
        max_results=max_results,
        timeout=timeout,
    )
    response = await _do_search(req)
    if req.format == OutputFormat.MARKDOWN:
        return PlainTextResponse(format_markdown(response), media_type="text/markdown")
    return format_json(response)


@router.get("/health")
async def health():
    return {"status": "ok", "pool_ready": _pool is not None and _pool._started}
