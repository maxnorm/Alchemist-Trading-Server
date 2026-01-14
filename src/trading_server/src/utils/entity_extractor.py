"""
Entity Extractor for financial news
Extracts currency pairs, economic events, and other entities from news text
Uses spaCy NER (free, open-source)
"""

import re
from typing import Dict, List
from utils.logging_config import get_logger

try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None


class EntityExtractor:
    """
    Entity extractor for financial news
    Extracts currency pairs, economic events, and other relevant entities
    """

    # Currency codes (ISO 4217)
    CURRENCY_CODES = {
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "CHF",
        "AUD",
        "CAD",
        "NZD",
        "CNY",
        "HKD",
        "SGD",
        "SEK",
        "NOK",
        "DKK",
        "PLN",
        "ZAR",
        "BRL",
        "MXN",
        "INR",
        "KRW",
    }

    # Currency names
    CURRENCY_NAMES = {
        "dollar": "USD",
        "euro": "EUR",
        "pound": "GBP",
        "sterling": "GBP",
        "yen": "JPY",
        "franc": "CHF",
        "yuan": "CNY",
        "won": "KRW",
        "rupee": "INR",
        "real": "BRL",
        "peso": "MXN",
    }

    # Common currency pairs
    CURRENCY_PAIRS = {
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "USDCHF",
        "AUDUSD",
        "USDCAD",
        "NZDUSD",
        "EURGBP",
        "EURJPY",
        "GBPJPY",
        "AUDNZD",
        "EURAUD",
        "EURCHF",
        "GBPCHF",
        "AUDJPY",
        "CADJPY",
        "CHFJPY",
        "EURCAD",
        "GBPCAD",
        "AUDCAD",
        "NZDCAD",
    }

    # Economic event keywords
    ECONOMIC_EVENTS = {
        "GDP",
        "CPI",
        "inflation",
        "unemployment",
        "employment",
        "interest rate",
        "central bank",
        "federal reserve",
        "ECB",
        "BoE",
        "BoJ",
        "rate decision",
        "nonfarm payrolls",
        "NFP",
        "retail sales",
        "industrial production",
        "trade balance",
        "current account",
        "PMI",
        "consumer confidence",
        "housing starts",
        "building permits",
        "durable goods",
        "factory orders",
    }

    _instance = None
    _nlp = None

    def __new__(cls):
        """Singleton pattern to cache spaCy model loading"""
        if cls._instance is None:
            cls._instance = super(EntityExtractor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize entity extractor (only once due to singleton)"""
        if self._initialized:
            return

        self.logger = get_logger("entity_extractor", "entity_extractor.log")

        if not SPACY_AVAILABLE:
            self.logger.error(
                "spacy library not installed. Install with: "
                "pip install spacy && python -m spacy download en_core_web_sm"
            )
            self._available = False
            self._initialized = True
            return

        self._available = False

        try:
            # Load spaCy model (lazy loading)
            self._load_model()

            self._available = True
            self._initialized = True
            self.logger.info("Entity extractor initialized successfully")

        except Exception as e:
            self.logger.error(
                f"Failed to initialize entity extractor: {e}", exc_info=True
            )
            self._available = False
            self._initialized = True

    def _load_model(self):
        """Load spaCy model (cached)"""
        if EntityExtractor._nlp is not None:
            return

        try:
            self.logger.info("Loading spaCy model: en_core_web_sm")
            EntityExtractor._nlp = spacy.load("en_core_web_sm")
            self.logger.info("spaCy model loaded successfully")
        except OSError:
            # Model not found, try to download
            self.logger.warning("spaCy model not found. Attempting to download...")
            import subprocess

            subprocess.run(
                ["python", "-m", "spacy", "download", "en_core_web_sm"], check=False
            )
            try:
                EntityExtractor._nlp = spacy.load("en_core_web_sm")
                self.logger.info("spaCy model downloaded and loaded successfully")
            except Exception as e:
                self.logger.error(f"Failed to load spaCy model: {e}")
                raise
        except Exception as e:
            self.logger.error(f"Failed to load spaCy model: {e}", exc_info=True)
            raise

    def is_available(self) -> bool:
        """Check if entity extractor is available"""
        return self._available and EntityExtractor._nlp is not None

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract all entities from text

        :param text: Text to extract entities from
        :return: Dictionary with entity types and values
        """
        if not self.is_available():
            return {
                "currency_pairs": [],
                "events": [],
                "currencies": [],
            }

        if not text or not text.strip():
            return {
                "currency_pairs": [],
                "events": [],
                "currencies": [],
            }

        try:
            # Use spaCy NER
            if EntityExtractor._nlp is None:
                raise RuntimeError("spaCy model not initialized")
            doc = EntityExtractor._nlp(text)

            # Extract currency pairs
            currency_pairs = self.extract_currency_pairs(text)

            # Extract economic events
            events = self.extract_events(text)

            # Extract individual currencies
            currencies = self._extract_currencies(text, doc)

            return {
                "currency_pairs": currency_pairs,
                "events": events,
                "currencies": currencies,
            }

        except Exception as e:
            self.logger.error(f"Error extracting entities: {e}", exc_info=True)
            return {
                "currency_pairs": [],
                "events": [],
                "currencies": [],
            }

    def extract_currency_pairs(self, text: str) -> List[str]:
        """
        Extract currency pairs from text

        :param text: Text to search
        :return: List of currency pair symbols found
        """
        if not text:
            return []

        text_upper = text.upper()
        found_pairs = set()

        # Direct currency pair mentions (e.g., "EURUSD", "EUR/USD", "EUR-USD")
        for pair in self.CURRENCY_PAIRS:
            # Check various formats
            patterns = [
                pair,  # EURUSD
                f"{pair[:3]}/{pair[3:]}",  # EUR/USD
                f"{pair[:3]}-{pair[3:]}",  # EUR-USD
                f"{pair[:3]} {pair[3:]}",  # EUR USD
            ]
            for pattern in patterns:
                if pattern in text_upper:
                    found_pairs.add(pair)
                    break

        # Extract pairs from currency mentions (e.g., "EUR against USD")
        # This is a simplified extraction - could be enhanced with NLP
        currency_codes = list(self.CURRENCY_CODES)
        for i, curr1 in enumerate(currency_codes):
            for curr2 in currency_codes[i + 1 :]:
                pair1 = curr1 + curr2
                pair2 = curr2 + curr1
                if (
                    pair1 in self.CURRENCY_PAIRS
                    and curr1 in text_upper
                    and curr2 in text_upper
                ):
                    found_pairs.add(pair1)
                elif (
                    pair2 in self.CURRENCY_PAIRS
                    and curr1 in text_upper
                    and curr2 in text_upper
                ):
                    found_pairs.add(pair2)

        return sorted(list(found_pairs))

    def extract_events(self, text: str) -> List[str]:
        """
        Extract economic event types from text

        :param text: Text to search
        :return: List of economic event types found
        """
        if not text:
            return []

        text_lower = text.lower()
        found_events = set()

        # Check for economic event keywords
        for event in self.ECONOMIC_EVENTS:
            if event.lower() in text_lower:
                found_events.add(event)

        # Check for common patterns
        patterns = [
            (r"\bGDP\b", "GDP"),
            (r"\bCPI\b", "CPI"),
            (r"\bNFP\b", "Nonfarm Payrolls"),
            (r"\bPMI\b", "PMI"),
            (r"interest\s+rate", "Interest Rate"),
            (r"rate\s+decision", "Rate Decision"),
            (r"central\s+bank", "Central Bank"),
            (r"federal\s+reserve", "Federal Reserve"),
        ]

        for pattern, event_name in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                found_events.add(event_name)

        return sorted(list(found_events))

    def _extract_currencies(self, text: str, doc) -> List[str]:
        """
        Extract individual currency mentions from text

        :param text: Text to search
        :param doc: spaCy doc object (optional, will create if not provided)
        :return: List of currency codes found
        """
        if not text:
            return []

        found_currencies = set()
        text_upper = text.upper()

        # Check for currency codes
        for code in self.CURRENCY_CODES:
            if code in text_upper:
                found_currencies.add(code)

        # Check for currency names
        text_lower = text.lower()
        for name, code in self.CURRENCY_NAMES.items():
            if name in text_lower:
                found_currencies.add(code)

        return sorted(list(found_currencies))

    def match_symbols(self, currency_pairs: List[str]) -> List[str]:
        """
        Map currency pairs to trading symbols (validate and normalize)

        :param currency_pairs: List of currency pair strings
        :return: List of valid trading symbols
        """
        valid_symbols = []

        for pair in currency_pairs:
            # Normalize pair (remove separators, uppercase)
            pair_clean = pair.upper().replace("/", "").replace("-", "").replace(" ", "")

            # Check if it's a valid pair
            if pair_clean in self.CURRENCY_PAIRS:
                valid_symbols.append(pair_clean)
            elif len(pair_clean) == 6:
                # Check if it's a valid 6-character pair (even if not in our list)
                base = pair_clean[:3]
                quote = pair_clean[3:]
                if base in self.CURRENCY_CODES and quote in self.CURRENCY_CODES:
                    valid_symbols.append(pair_clean)

        return sorted(list(set(valid_symbols)))
