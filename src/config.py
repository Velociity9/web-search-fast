from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class SearchEngine(str, Enum):
    GOOGLE = "google"
    BING = "bing"
    DUCKDUCKGO = "duckduckgo"


class OutputFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"


class BrowserConfig(BaseModel):
    pool_size: int = Field(default=5, ge=1, le=20, description="Number of browser instances in pool")
    headless: bool = Field(default=True)
    timeout: int = Field(default=30, ge=5, le=120, description="Page load timeout in seconds")
    geoip: bool = Field(default=True, description="Enable GeoIP spoofing based on real IP")
    humanize: float = Field(default=2.0, ge=0, description="Humanized cursor movement duration (0 to disable)")
    locale: str = Field(default="en-US", description="Browser locale")
    block_images: bool = Field(default=True, description="Block image loading for faster page loads")


class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    max_concurrent_searches: int = Field(default=10, ge=1)
    default_max_results: int = Field(default=10, ge=1, le=50)


def get_config() -> AppConfig:
    return AppConfig()
