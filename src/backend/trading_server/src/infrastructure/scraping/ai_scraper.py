"""
AI-assisted web scraping framework
Uses LLM-based extraction for structured data extraction from financial websites
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from utils.logging_config import get_logger

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic = None  # type: ignore[assignment]


class AIScraper(ABC):
    """
    Abstract base class for AI-assisted web scrapers
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize AI scraper

        :param config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = get_logger("ai_scraper", "ai_scraper.log")

    @abstractmethod
    def extract(self, html: str, url: str) -> Dict[str, Any]:
        """
        Extract structured data from HTML

        :param html: HTML content
        :param url: Source URL
        :return: Extracted data dictionary
        """
        pass


class LLMScraper(AIScraper):
    """
    LLM-based scraper using OpenAI or Anthropic APIs
    """

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize LLM scraper

        :param provider: LLM provider ("openai" or "anthropic")
        :param model: Model name (defaults based on provider)
        :param config: Additional configuration
        """
        super().__init__(config)

        self.provider = provider.lower()
        self.model = model

        # Initialize client based on provider
        if self.provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("openai library not installed")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            self.client = OpenAI(api_key=api_key)
            self.model = model or "gpt-4"
        elif self.provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("anthropic library not installed")
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment")
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = model or "claude-3-opus-20240229"
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Rate limiting
        self._last_request_time = 0.0
        self._min_request_interval = 1.0  # 1 second between requests

        # Cost tracking
        self._request_count = 0
        self._total_tokens = 0

    def _rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def extract(self, html: str, url: str) -> Dict[str, Any]:
        """
        Extract structured data from HTML using LLM

        :param html: HTML content
        :param url: Source URL
        :return: Extracted data dictionary
        """
        self._rate_limit()

        # Create extraction prompt
        prompt = self._create_extraction_prompt(html, url)

        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a financial data extraction assistant. "
                                "Extract structured data from financial news articles "
                                "and economic data."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,  # Low temperature for consistent extraction
                )

                extracted_text = response.choices[0].message.content
                self._request_count += 1
                self._total_tokens += (
                    response.usage.total_tokens if hasattr(response, "usage") else 0
                )

            elif self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=[
                        {
                            "role": "user",
                            "content": f"{prompt}\n\nExtract the data in JSON format.",
                        }
                    ],
                )

                extracted_text = response.content[0].text
                self._request_count += 1
                self._total_tokens += (
                    response.usage.input_tokens + response.usage.output_tokens
                )

            # Parse extracted JSON
            import json

            try:
                extracted_data = json.loads(extracted_text)
            except json.JSONDecodeError:
                # Try to extract JSON from text if wrapped
                import re

                json_match = re.search(r"\{.*\}", extracted_text, re.DOTALL)
                if json_match:
                    extracted_data = json.loads(json_match.group())
                else:
                    self.logger.warning(
                        f"Could not parse JSON from LLM response: {extracted_text[:200]}"
                    )
                    extracted_data = {}

            return extracted_data

        except Exception as e:
            self.logger.error(f"Error extracting data with LLM: {e}", exc_info=True)
            return {}

    def _create_extraction_prompt(self, html: str, url: str) -> str:
        """
        Create extraction prompt for LLM

        :param html: HTML content
        :param url: Source URL
        :return: Prompt string
        """
        # Truncate HTML if too long (LLM context limits)
        max_html_length = 10000
        if len(html) > max_html_length:
            html = html[:max_html_length] + "... [truncated]"

        prompt = f"""
Extract structured financial data from the following HTML content.

URL: {url}

HTML Content:
{html}

Please extract the following information and return it as JSON:
- title: Article title or headline
- content: Main article content (full text)
- timestamp: Publication date/time (ISO 8601 format)
- source: Source identifier
- category: News category (if available)
- symbol: Trading symbol(s) mentioned (if any)
- entities: Currency pairs, economic events, or other relevant entities

Return only valid JSON, no additional text.
"""

        return prompt

    def get_stats(self) -> Dict[str, Any]:
        """
        Get scraper statistics (requests, tokens, costs)

        :return: Statistics dictionary
        """
        return {
            "request_count": self._request_count,
            "total_tokens": self._total_tokens,
            "provider": self.provider,
            "model": self.model,
        }
