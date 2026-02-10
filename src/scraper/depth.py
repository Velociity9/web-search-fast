from __future__ import annotations
import asyncio
from playwright.async_api import Page

from src.api.schemas import SearchResult, SubLink
from src.scraper.browser import BrowserPool
from src.scraper.parser import extract_main_content, extract_links


async def fetch_page_content(page: Page, url: str, timeout: int = 30) -> str:
    """Fetch a single page and return its HTML content."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        return await page.content()
    except Exception:
        return ""


async def enrich_with_content(pool: BrowserPool, result: SearchResult, timeout: int = 30) -> SearchResult:
    """Depth 2: fetch the result URL and extract main content."""
    async with pool.acquire() as page:
        html = await fetch_page_content(page, result.url, timeout)
        if html:
            result.content = extract_main_content(html)
    return result


async def enrich_with_sub_links(pool: BrowserPool, result: SearchResult, timeout: int = 30, max_sub: int = 5) -> SearchResult:
    """Depth 3: fetch content + extract and follow sub-links."""
    async with pool.acquire() as page:
        html = await fetch_page_content(page, result.url, timeout)
        if not html:
            return result
        result.content = extract_main_content(html)
        links = extract_links(html, result.url)[:max_sub]

    async def fetch_sub(link: dict[str, str]) -> SubLink:
        async with pool.acquire() as p:
            sub_html = await fetch_page_content(p, link["url"], timeout)
            content = extract_main_content(sub_html) if sub_html else ""
            return SubLink(url=link["url"], title=link.get("title", ""), content=content[:5000])

    if links:
        sub_results = await asyncio.gather(*[fetch_sub(lnk) for lnk in links], return_exceptions=True)
        result.sub_links = [s for s in sub_results if isinstance(s, SubLink)]

    return result


async def crawl_results(
    pool: BrowserPool,
    results: list[SearchResult],
    depth: int = 1,
    timeout: int = 30,
) -> list[SearchResult]:
    """Orchestrate multi-depth crawling with concurrency."""
    if depth <= 1:
        return results

    if depth == 2:
        tasks = [enrich_with_content(pool, r, timeout) for r in results]
    else:  # depth == 3
        tasks = [enrich_with_sub_links(pool, r, timeout) for r in results]

    enriched = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in enriched if isinstance(r, SearchResult)]
