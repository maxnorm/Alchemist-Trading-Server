"""
Sentiment Analyzer using FinBERT model
Analyzes financial text sentiment using ProsusAI/finbert model (free, open-source)
"""

from typing import Dict, List, Any
from utils.logging_config import get_logger

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    AutoTokenizer = None
    AutoModelForSequenceClassification = None
    torch = None


class SentimentAnalyzer:
    """
    Sentiment analyzer using FinBERT model
    FinBERT is a financial domain-specific BERT model fine-tuned on financial news
    """

    MODEL_NAME = "ProsusAI/finbert"
    MAX_LENGTH = 512  # BERT max sequence length

    # FinBERT label mapping
    LABEL_MAP = {
        0: "positive",
        1: "negative",
        2: "neutral",
    }

    # Score mapping (convert to -1 to 1 scale)
    SCORE_MAP = {
        "positive": 1.0,
        "negative": -1.0,
        "neutral": 0.0,
    }

    _instance = None
    _model = None
    _tokenizer = None

    def __new__(cls):
        """Singleton pattern to cache model loading"""
        if cls._instance is None:
            cls._instance = super(SentimentAnalyzer, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize sentiment analyzer (only once due to singleton)"""
        if self._initialized:
            return

        self.logger = get_logger("sentiment_analyzer", "sentiment_analyzer.log")

        if not TRANSFORMERS_AVAILABLE:
            self.logger.error(
                "transformers library not installed. Install with: pip install transformers torch"
            )
            self._available = False
            self._initialized = True
            return

        self._available = False
        self._device = None

        try:
            # Check for GPU
            if torch and torch.cuda.is_available():
                self._device = torch.device("cuda")
                self.logger.info("Using GPU for sentiment analysis")
            else:
                self._device = torch.device("cpu")
                self.logger.info("Using CPU for sentiment analysis")

            # Load model and tokenizer (lazy loading)
            self._load_model()

            self._available = True
            self._initialized = True
            self.logger.info("Sentiment analyzer initialized successfully")

        except Exception as e:
            self.logger.error(
                f"Failed to initialize sentiment analyzer: {e}", exc_info=True
            )
            self._available = False
            self._initialized = True

    def _load_model(self):
        """Load FinBERT model and tokenizer (cached)"""
        if SentimentAnalyzer._model is not None:
            return

        try:
            self.logger.info(f"Loading FinBERT model: {self.MODEL_NAME}")
            SentimentAnalyzer._tokenizer = AutoTokenizer.from_pretrained(
                self.MODEL_NAME
            )
            SentimentAnalyzer._model = (
                AutoModelForSequenceClassification.from_pretrained(self.MODEL_NAME)
            )
            SentimentAnalyzer._model.to(self._device)
            SentimentAnalyzer._model.eval()  # Set to evaluation mode
            self.logger.info("FinBERT model loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load FinBERT model: {e}", exc_info=True)
            raise

    def is_available(self) -> bool:
        """Check if sentiment analyzer is available"""
        return self._available and SentimentAnalyzer._model is not None

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of a single text

        :param text: Text to analyze
        :return: Dictionary with score, label, and confidence
        """
        if not self.is_available():
            raise RuntimeError("Sentiment analyzer not available")

        if not text or not text.strip():
            return {
                "score": 0.0,
                "label": "neutral",
                "confidence": 0.0,
            }

        try:
            # Truncate text if too long
            text = text.strip()
            if len(text) > self.MAX_LENGTH * 4:  # Rough character estimate
                text = text[: self.MAX_LENGTH * 4]

            # Tokenize
            if SentimentAnalyzer._tokenizer is None or SentimentAnalyzer._model is None:
                raise RuntimeError("Model not initialized")
            inputs = SentimentAnalyzer._tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=self.MAX_LENGTH,
                padding=True,
            )
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            # Get predictions
            with torch.no_grad():
                outputs = SentimentAnalyzer._model(**inputs)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=-1)

            # Get predicted label and confidence
            predicted_class = torch.argmax(probabilities, dim=-1).item()
            confidence = probabilities[0][predicted_class].item()

            label = self.LABEL_MAP.get(predicted_class, "neutral")
            score = self.SCORE_MAP.get(label, 0.0)

            return {
                "score": score,
                "label": label,
                "confidence": confidence,
            }

        except Exception as e:
            self.logger.error(f"Error analyzing sentiment: {e}", exc_info=True)
            # Return neutral on error
            return {
                "score": 0.0,
                "label": "neutral",
                "confidence": 0.0,
            }

    def analyze_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Analyze sentiment of multiple texts in batch (more efficient)

        :param texts: List of texts to analyze
        :return: List of sentiment dictionaries
        """
        if not self.is_available():
            raise RuntimeError("Sentiment analyzer not available")

        if not texts:
            return []

        try:
            # Filter empty texts
            valid_texts = []
            text_indices = []
            for i, text in enumerate(texts):
                if text and text.strip():
                    # Truncate if too long
                    text = text.strip()
                    if len(text) > self.MAX_LENGTH * 4:
                        text = text[: self.MAX_LENGTH * 4]
                    valid_texts.append(text)
                    text_indices.append(i)

            if not valid_texts:
                return [
                    {"score": 0.0, "label": "neutral", "confidence": 0.0} for _ in texts
                ]

            # Tokenize batch
            if SentimentAnalyzer._tokenizer is None or SentimentAnalyzer._model is None:
                raise RuntimeError("Model not initialized")
            inputs = SentimentAnalyzer._tokenizer(
                valid_texts,
                return_tensors="pt",
                truncation=True,
                max_length=self.MAX_LENGTH,
                padding=True,
            )
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            # Get predictions
            with torch.no_grad():
                outputs = SentimentAnalyzer._model(**inputs)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=-1)

            # Process results
            results = []
            result_idx = 0

            for i in range(len(texts)):
                if i in text_indices:
                    # Valid text - get prediction
                    predicted_class = torch.argmax(
                        probabilities[result_idx], dim=-1
                    ).item()
                    confidence = probabilities[result_idx][predicted_class].item()

                    label = self.LABEL_MAP.get(predicted_class, "neutral")
                    score = self.SCORE_MAP.get(label, 0.0)

                    results.append(
                        {
                            "score": score,
                            "label": label,
                            "confidence": confidence,
                        }
                    )
                    result_idx += 1
                else:
                    # Empty text - return neutral
                    results.append(
                        {
                            "score": 0.0,
                            "label": "neutral",
                            "confidence": 0.0,
                        }
                    )

            return results

        except Exception as e:
            self.logger.error(f"Error in batch sentiment analysis: {e}", exc_info=True)
            # Return neutral for all on error
            return [
                {"score": 0.0, "label": "neutral", "confidence": 0.0} for _ in texts
            ]

    def get_sentiment_label(self, score: float) -> str:
        """
        Map sentiment score to label

        :param score: Sentiment score (-1 to 1)
        :return: Sentiment label (positive/negative/neutral)
        """
        if score > 0.1:
            return "positive"
        elif score < -0.1:
            return "negative"
        else:
            return "neutral"
