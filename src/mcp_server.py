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
        logger.debug("[pool] already started, returning singleton")
        return _pool_instance
    logger.info("[pool] cold start — initializing BrowserPool ...")
    import time as _t
    t0 = _t.monotonic()
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
    logger.info("[pool] BrowserPool ready (size=%d) in %.1fms", config.browser.pool_size, (_t.monotonic() - t0) * 1000)
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
    logger.info("[lifespan] session starting — acquiring pool")
    pool = await _ensure_pool()
    logger.info("[lifespan] session ready — pool._started=%s", pool._started)
    yield {"pool": pool}
    logger.info("[lifespan] session ending")


mcp = FastMCP(
    "web-search-fast",
    instructions=(
        "Real-time web search and page reading service using a stealth browser. "
        "Use this when you need CURRENT information that may be beyond your training data, including: "
        "latest documentation, recent news/events, up-to-date API references, "
        "package versions, changelogs, bug reports, security advisories, "
        "pricing, availability, or any fact that changes over time. "
        "Also use this to verify uncertain claims or find authoritative sources. "
        "Prefer engine='duckduckgo' for speed and reliability. "
        "Use depth=1 for quick lookups, depth=2 when you need full page content."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="web_search",
    description=(
        "Search the web for current information. Use this when you need to find "
        "up-to-date facts, documentation, tutorials, news, package info, error solutions, "
        "or anything that may have changed after your training cutoff. "
        "Returns titles, URLs, and snippets in markdown. "
        "Set depth=2 to also fetch full page content for each result (slower but more detailed). "
        "Prefer engine='duckduckgo' for speed; use 'google' for broader coverage."
    ),
)
async def web_search(
    query: str,
    engine: str = "duckduckgo",
    depth: int = 1,
    max_results: int = 5,
    ctx: Context = None,
) -> str:
    """Search the web and return results as markdown."""
    import time as _t
    t0 = _t.monotonic()
    logger.info("[web_search] called: query=%r engine=%s depth=%d max_results=%d", query, engine, depth, max_results)

    from src.api.schemas import SearchRequest
    from src.config import SearchEngine
    from src.core.search import SearchError, do_search
    from src.formatter.markdown_fmt import format_markdown

    pool: BrowserPool = ctx.request_context.lifespan_context["pool"]
    logger.debug("[web_search] pool acquired, _started=%s", pool._started)

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
        logger.info("[web_search] starting search ...")
        response = await do_search(pool, req)
        result = format_markdown(response)
        logger.info("[web_search] done in %.0fms, %d results", (_t.monotonic() - t0) * 1000, response.total)
        return result
    except SearchError as e:
        logger.error("[web_search] SearchError: %s", e)
        return f"Search error: {e}"
    except Exception as e:
        logger.exception("[web_search] unexpected error")
        return f"Error: {e}"


@mcp.tool(
    name="get_page_content",
    description=(
        "Fetch and read a single web page, extracting its main content as clean markdown. "
        "Use this to read full articles, documentation pages, blog posts, or any URL "
        "you already know. Ideal after web_search when you need the complete content "
        "of a specific result, or when the user provides a URL to read."
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
    description="List available search engines and check browser pool health status.",
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
        choices=["stdio", "sse", "http"],
        default="http",
        help="Transport protocol (default: http)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8897, help="Bind port (default: 8897)")
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

    if args.transport in ("sse", "http"):
        mcp.settings.host = args.host
        mcp.settings.port = args.port

        import uvicorn

        if args.transport == "http":
            starlette_app = mcp.streamable_http_app()
            endpoint_path = "/mcp"
        else:
            starlette_app = mcp.sse_app()
            endpoint_path = "/sse"

        async def serve() -> None:
            await _ensure_pool()
            logger.info("%s server starting on %s:%d", args.transport.upper(), args.host, args.port)
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
