from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Browser, Page

logger = logging.getLogger(__name__)


class BrowserPool:
    def __init__(
        self,
        pool_size: int = 5,
        headless: bool = True,
        geoip: bool = True,
        humanize: float = 2.0,
        locale: str = "en-US",
        block_images: bool = True,
    ):
        self._pool_size = pool_size
        self._headless = headless
        self._geoip = geoip
        self._humanize = humanize
        self._locale = locale
        self._block_images = block_images
        self._browser: Browser | None = None
        self._pages: asyncio.Queue[Page] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(pool_size)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        camoufox_kwargs: dict = {
            "headless": self._headless,
            "geoip": self._geoip,
            "humanize": self._humanize if self._humanize > 0 else False,
            "locale": self._locale,
        }
        if self._block_images:
            camoufox_kwargs["block_images"] = True
            camoufox_kwargs["i_know_what_im_doing"] = True
        self._camoufox = AsyncCamoufox(**camoufox_kwargs)
        self._browser = await self._camoufox.__aenter__()
        for _ in range(self._pool_size):
            page = await self._browser.new_page()
            await self._pages.put(page)
        self._started = True
        logger.info(
            f"BrowserPool started: pool_size={self._pool_size}, "
            f"geoip={self._geoip}, humanize={self._humanize}, "
            f"locale={self._locale}, block_images={self._block_images}"
        )

    async def stop(self) -> None:
        if not self._started:
            return
        while not self._pages.empty():
            page = await self._pages.get()
            await page.close()
        await self._camoufox.__aexit__(None, None, None)
        self._started = False
        self._browser = None
        logger.info("BrowserPool stopped")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Page, None]:
        async with self._semaphore:
            page = await self._pages.get()
            try:
                yield page
            finally:
                try:
                    await page.goto("about:blank")
                except Exception:
                    pass
                await self._pages.put(page)
