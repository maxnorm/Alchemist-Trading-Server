"""
Website-specific scrapers for financial websites
Uses AI-assisted extraction for resilient scraping
"""

import requests  # type: ignore[import-untyped]
from typing import Dict, Any, Optional
from utils.logging_config import get_logger
from .ai_scraper import AIScraper, LLMScraper


class WebsiteScraper:
    """
    Base class for website-specific scrapers
    """

    def __init__(self, ai_scraper: Optional[AIScraper] = None):
        """
        Initialize website scraper

        :param ai_scraper: AI scraper instance (optional, will create if not provided)
        """
        self.logger = get_logger("website_scraper", "website_scraper.log")
        self.ai_scraper = ai_scraper

        if self.ai_scraper is None:
            try:
                # Try to create LLM scraper (will fail if API keys not set)
                self.ai_scraper = LLMScraper(provider="openai")
            except Exception as e:
                self.logger.warning(f"Could not initialize AI scraper: {e}")

    def fetch_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from URL

        :param url: URL to fetch
        :return: HTML content or None on error
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None

    def scrape(self, url: str) -> Dict[str, Any]:
        """
        Scrape data from URL

        :param url: URL to scrape
        :return: Extracted data dictionary
        """
        html = self.fetch_html(url)
        if not html:
            return {}

        if self.ai_scraper:
            return self.ai_scraper.extract(html, url)
        else:
            # Fallback to basic extraction
            return self._basic_extract(html, url)

    def _basic_extract(self, html: str, url: str) -> Dict[str, Any]:
        """
        Basic extraction without AI (fallback)

        :param html: HTML content
        :param url: Source URL
        :return: Extracted data dictionary
        """
        from bs4 import BeautifulSoup

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Extract title
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text().strip()

            # Extract content (try common article selectors)
            content = ""
            content_selectors = [
                "article",
                ".article-content",
                ".post-content",
                "main",
                ".content",
            ]
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text().strip()
                    break

            return {
                "title": title,
                "content": content,
                "url": url,
                "source": self._get_source_from_url(url),
            }
        except Exception as e:
            self.logger.error(f"Error in basic extraction: {e}")
            return {}

    def _get_source_from_url(self, url: str) -> str:
        """Extract source identifier from URL"""
        if "tradingeconomics.com" in url:
            return "tradingeconomics"
        elif "investing.com" in url:
            return "investing"
        elif "forexfactory.com" in url:
            return "forexfactory"
        elif "federalreserve.gov" in url:
            return "fed"
        elif "ecb.europa.eu" in url:
            return "ecb"
        elif "bankofengland.co.uk" in url:
            return "boe"
        elif "boj.or.jp" in url:
            return "boj"
        else:
            return "unknown"


class TradingEconomicsScraper(WebsiteScraper):
    """Scraper for TradingEconomics.com"""

    def __init__(self, ai_scraper: Optional[AIScraper] = None):
        super().__init__(ai_scraper)
        self.base_url = "https://tradingeconomics.com"


class InvestingScraper(WebsiteScraper):
    """Scraper for Investing.com"""

    def __init__(self, ai_scraper: Optional[AIScraper] = None):
        super().__init__(ai_scraper)
        self.base_url = "https://www.investing.com"


class ForexFactoryScraper(WebsiteScraper):
    """Scraper for ForexFactory.com"""

    def __init__(self, ai_scraper: Optional[AIScraper] = None):
        super().__init__(ai_scraper)
        self.base_url = "https://www.forexfactory.com"


class CentralBankScraper(WebsiteScraper):
    """Scraper for central bank websites"""

    def __init__(self, ai_scraper: Optional[AIScraper] = None):
        super().__init__(ai_scraper)


# Factory function to create appropriate scraper
def create_scraper(
    website: str, ai_scraper: Optional[AIScraper] = None
) -> WebsiteScraper:
    """
    Create appropriate scraper for website

    :param website: Website identifier
    :param ai_scraper: Optional AI scraper instance
    :return: Website scraper instance
    """
    scrapers = {
        "tradingeconomics": TradingEconomicsScraper,
        "investing": InvestingScraper,
        "forexfactory": ForexFactoryScraper,
        "central_bank": CentralBankScraper,
    }

    scraper_class = scrapers.get(website.lower(), WebsiteScraper)
    return scraper_class(ai_scraper)
