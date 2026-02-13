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
        proxy: str = "",
        os_target: str = "",
        fonts: list[str] | None = None,
        block_webgl: bool = False,
        addons: list[str] | None = None,
    ):
        self._pool_size = pool_size
        self._headless = headless
        self._geoip = geoip
        self._humanize = humanize
        self._locale = locale
        self._block_images = block_images
        self._proxy = proxy
        self._os_target = os_target
        self._fonts = fonts or []
        self._block_webgl = block_webgl
        self._addons = addons or []
        self._browser: Browser | None = None
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
        if self._proxy:
            camoufox_kwargs["proxy"] = {"server": self._proxy}
        if self._os_target:
            camoufox_kwargs["os"] = self._os_target
        if self._fonts:
            camoufox_kwargs["fonts"] = self._fonts
        if self._block_webgl:
            camoufox_kwargs["block_webgl"] = True
        if self._addons:
            camoufox_kwargs["addons"] = self._addons
        self._camoufox = AsyncCamoufox(**camoufox_kwargs)
        self._browser = await self._camoufox.__aenter__()
        self._started = True
        logger.info(
            "BrowserPool started (tab-per-search): pool_size=%d, "
            "geoip=%s, humanize=%s, locale=%s, block_images=%s, "
            "proxy=%s, os=%s, block_webgl=%s",
            self._pool_size, self._geoip, self._humanize,
            self._locale, self._block_images,
            bool(self._proxy), self._os_target or "auto", self._block_webgl,
        )

    async def stop(self) -> None:
        if not self._started:
            return
        await self._camoufox.__aexit__(None, None, None)
        self._started = False
        self._browser = None
        logger.info("BrowserPool stopped")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Page, None]:
        async with self._semaphore:
            page = await self._browser.new_page()
            logger.debug("New tab opened for search")
            try:
                yield page
            finally:
                try:
                    await page.close()
                    logger.debug("Tab closed after search")
                except Exception:
                    pass
