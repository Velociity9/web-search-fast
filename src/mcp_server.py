"""MCP server mode — exposes web search as MCP tools for LLM clients."""
from __future__ import annotations

import argparse
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from mcp.server.fastmcp import Context, FastMCP

if TYPE_CHECKING:
    from src.scraper.browser import BrowserPool

logger = logging.getLogger(__name__)


class LazyBrowserPool:
    """Lazy-init wrapper: BrowserPool starts on first tool call, not at MCP handshake."""

    def __init__(self) -> None:
        self._pool: BrowserPool | None = None
        self._started = False

    async def get(self) -> BrowserPool:
        if self._pool is not None and self._started:
            return self._pool
        from src.config import get_config
        from src.scraper.browser import BrowserPool

        config = get_config()
        self._pool = BrowserPool(
            pool_size=config.browser.pool_size,
            headless=config.browser.headless,
            geoip=config.browser.geoip,
            humanize=config.browser.humanize,
            locale=config.browser.locale,
            block_images=config.browser.block_images,
        )
        await self._pool.start()
        self._started = True
        logger.info("MCP server: BrowserPool started (size=%d)", config.browser.pool_size)
        return self._pool

    async def stop(self) -> None:
        if self._pool and self._started:
            await self._pool.stop()
            self._started = False
            logger.info("MCP server: BrowserPool stopped")


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage lazy BrowserPool lifecycle for MCP server."""
    lazy_pool = LazyBrowserPool()
    try:
        yield {"lazy_pool": lazy_pool}
    finally:
        await lazy_pool.stop()


mcp = FastMCP(
    "web-search-fast",
    instructions=(
        "Web search service powered by Camoufox anti-detect browser. "
        "Search Google, Bing, or DuckDuckGo and get structured results. "
        "Supports multi-depth crawling: depth=1 for SERP snippets, "
        "depth=2 to also fetch page content, depth=3 to also follow sub-links."
    ),
    lifespan=lifespan,
)


@mcp.tool(
    name="web_search",
    description=(
        "Search the web using Google, Bing, or DuckDuckGo. "
        "Returns search results with titles, URLs, and snippets in markdown. "
        "Use depth=2 to also fetch full page content for each result. "
        "Use depth=3 to additionally follow and fetch sub-links from each page."
    ),
)
async def web_search(
    query: str,
    engine: str = "google",
    depth: int = 1,
    max_results: int = 5,
    ctx: Context = None,
) -> str:
    """Search the web and return results as markdown."""
    from src.api.schemas import SearchRequest
    from src.config import SearchEngine
    from src.core.search import SearchError, do_search
    from src.formatter.markdown_fmt import format_markdown

    lazy_pool: LazyBrowserPool = ctx.request_context.lifespan_context["lazy_pool"]
    pool = await lazy_pool.get()

    try:
        search_engine = SearchEngine(engine.lower())
    except ValueError:
        return f"Error: Unknown engine '{engine}'. Available: google, bing, duckduckgo"

    depth = max(1, min(3, depth))
    max_results = max(1, min(20, max_results))

    try:
        req = SearchRequest(
            query=query,
            engine=search_engine,
            depth=depth,
            max_results=max_results,
            timeout=60,
        )
        response = await do_search(pool, req)
        return format_markdown(response)
    except SearchError as e:
        return f"Search error: {e}"
    except Exception as e:
        logger.exception("Unexpected error in web_search tool")
        return f"Error: {e}"


@mcp.tool(
    name="get_page_content",
    description=(
        "Fetch a single web page and extract its main content as markdown. "
        "Useful for reading a specific URL in detail after seeing it in search results."
    ),
)
async def get_page_content(
    url: str,
    ctx: Context = None,
) -> str:
    """Fetch and extract content from a specific URL."""
    from src.core.search import fetch_url_content

    lazy_pool: LazyBrowserPool = ctx.request_context.lifespan_context["lazy_pool"]
    pool = await lazy_pool.get()

    try:
        content = await fetch_url_content(pool, url, timeout=30)
        if not content:
            return f"Could not extract content from {url}"
        return f"# Content from {url}\n\n{content}"
    except Exception as e:
        logger.exception("Error fetching page content")
        return f"Error fetching {url}: {e}"


@mcp.tool(
    name="list_search_engines",
    description="List available search engines and browser pool status.",
)
async def list_search_engines(
    ctx: Context = None,
) -> str:
    """List available search engines."""
    from src.core.search import ENGINES

    lazy_pool: LazyBrowserPool = ctx.request_context.lifespan_context["lazy_pool"]
    pool = await lazy_pool.get()
    lines = [
        "# Available Search Engines",
        "",
        f"- **Browser pool active:** {pool._started}",
        f"- **Pool size:** {pool._pool_size}",
        "",
        "## Engines",
        "",
    ]
    for engine_enum, engine_impl in ENGINES.items():
        lines.append(f"- **{engine_enum.value}** ({engine_impl.__class__.__name__})")
    lines.extend([
        "",
        "## Notes",
        "",
        "- **DuckDuckGo**: Most reliable, recommended as default",
        "- **Google**: May trigger captcha on some IPs, auto-falls back to DuckDuckGo",
        "- **Bing**: Uses global.bing.com to avoid geo-redirect",
    ])
    return "\n".join(lines)


def main() -> None:
    """CLI entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="Web Search MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            filename="/tmp/web-search-mcp.log",
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
