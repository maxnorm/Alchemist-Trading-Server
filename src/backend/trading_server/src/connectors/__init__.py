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
    # Connectors may not be available if dependencies not installed
    FREDConnector = None
    WorldBankConnector = None
    ECBConnector = None
    RSSFeedConnector = None
    WebScrapingConnector = None
    NewsAPIConnector = None

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
