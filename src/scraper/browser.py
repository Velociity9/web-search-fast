from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from playwright.async_api import Page, Browser
from camoufox.async_api import AsyncCamoufox


class BrowserPool:
    def __init__(self, pool_size: int = 5, headless: bool = True):
        self._pool_size = pool_size
        self._headless = headless
        self._browser: Browser | None = None
        self._pages: asyncio.Queue[Page] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(pool_size)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._camoufox = AsyncCamoufox(headless=self._headless)
        self._browser = await self._camoufox.__aenter__()
        for _ in range(self._pool_size):
            page = await self._browser.new_page()
            await self._pages.put(page)
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        while not self._pages.empty():
            page = await self._pages.get()
            await page.close()
        await self._camoufox.__aexit__(None, None, None)
        self._started = False
        self._browser = None

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Page, None]:
        async with self._semaphore:
            page = await self._pages.get()
            try:
                yield page
            finally:
                # Reset page state for reuse
                try:
                    await page.goto("about:blank")
                except Exception:
                    pass
                await self._pages.put(page)
