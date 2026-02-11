"""MCP server mode — exposes web search as MCP tools for LLM clients."""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator

from mcp.server.fastmcp import Context, FastMCP

if TYPE_CHECKING:
    from src.scraper.browser import BrowserPool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton browser pool — shared across all SSE sessions
# ---------------------------------------------------------------------------

_pool_instance: BrowserPool | None = None
_pool_started: bool = False


async def _ensure_pool() -> BrowserPool:
    """Return the global BrowserPool, starting it on first call."""
    global _pool_instance, _pool_started
    if _pool_instance is not None and _pool_started:
        return _pool_instance
    from src.config import get_config
    from src.scraper.browser import BrowserPool

    config = get_config()
    _pool_instance = BrowserPool(
        pool_size=config.browser.pool_size,
        headless=config.browser.headless,
        geoip=config.browser.geoip,
        humanize=config.browser.humanize,
        locale=config.browser.locale,
        block_images=config.browser.block_images,
    )
    await _pool_instance.start()
    _pool_started = True
    logger.info("BrowserPool ready (size=%d)", config.browser.pool_size)
    return _pool_instance


async def _shutdown_pool() -> None:
    """Stop the global BrowserPool."""
    global _pool_instance, _pool_started
    if _pool_instance and _pool_started:
        await _pool_instance.stop()
        _pool_started = False
        logger.info("BrowserPool stopped")


# ---------------------------------------------------------------------------
# Lifespan — per-session, but pool is singleton so startup is instant
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Each MCP session gets a ref to the shared pool."""
    pool = await _ensure_pool()
    yield {"pool": pool}


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


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


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

    pool: BrowserPool = ctx.request_context.lifespan_context["pool"]

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

    pool: BrowserPool = ctx.request_context.lifespan_context["pool"]

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

    pool: BrowserPool = ctx.request_context.lifespan_context["pool"]
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


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="Web Search MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="sse",
        help="Transport protocol (default: sse)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="SSE bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8897, help="SSE bind port (default: 8897)")
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

    if args.transport == "sse":
        # SSE: pre-warm browser pool before accepting connections
        mcp.settings.host = args.host
        mcp.settings.port = args.port

        import uvicorn

        starlette_app = mcp.sse_app()

        async def serve() -> None:
            await _ensure_pool()
            logger.info("SSE server starting on %s:%d", args.host, args.port)
            config = uvicorn.Config(starlette_app, host=args.host, port=args.port, log_level="info")
            server = uvicorn.Server(config)
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.ensure_future(_shutdown_and_exit(server)))
            loop.add_signal_handler(signal.SIGINT, lambda: asyncio.ensure_future(_shutdown_and_exit(server)))
            try:
                await server.serve()
            finally:
                await _shutdown_pool()

        async def _shutdown_and_exit(server: uvicorn.Server) -> None:
            await _shutdown_pool()
            server.should_exit = True

        asyncio.run(serve())
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
