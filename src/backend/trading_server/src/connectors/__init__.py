"""Data source connector interface for modular data sources"""

from .base import IDataSourceConnector, ConnectorConfig
from .mt5_tick_connector import MT5TickConnector

# Phase 3: Alternative data connectors
try:
    from .fred_connector import FREDConnector
    from .world_bank_connector import WorldBankConnector
    from .ecb_connector import ECBConnector
    from .rss_feed_connector import RSSFeedConnector
    from .web_scraping_connector import WebScrapingConnector
    from .news_api_connector import NewsAPIConnector
except ImportError:
    # Connectors may not be available if dependencies not installed.
    # Use loose typing here to keep optional dependency pattern without impacting runtime behaviour.
    from typing import Any, cast

    FREDConnector = cast(Any, None)  # type: ignore[misc]
    WorldBankConnector = cast(Any, None)  # type: ignore[misc]
    ECBConnector = cast(Any, None)  # type: ignore[misc]
    RSSFeedConnector = cast(Any, None)  # type: ignore[misc]
    WebScrapingConnector = cast(Any, None)  # type: ignore[misc]
    NewsAPIConnector = cast(Any, None)  # type: ignore[misc]

__all__ = [
    "IDataSourceConnector",
    "ConnectorConfig",
    "MT5TickConnector",
    "FREDConnector",
    "WorldBankConnector",
    "ECBConnector",
    "RSSFeedConnector",
    "WebScrapingConnector",
    "NewsAPIConnector",
]
