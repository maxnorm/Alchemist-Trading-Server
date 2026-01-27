# Adding New Data Sources

This guide explains how to add new data sources to The Alchemist platform. The platform uses a plugin-based architecture where developers can add new data providers through code, and features are automatically discovered and made available in the dashboard.

## Overview

The data source plugin system enables:
- **Auto-discovery**: Features from new providers automatically appear in the dashboard
- **Extensibility**: Add new data sources in < 4 hours (developer task)
- **Type safety**: Features are declared with metadata (name, type, description)
- **Database integration**: Features are stored in the feature catalog for querying

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Your New Provider                                      │
│  - Implements DataProvider interface                    │
│  - Declares features via get_features()                │
│  - Registers with DataProviderRegistry                  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  DataProviderRegistry                                    │
│  - Auto-discovers features from all providers           │
│  - Provides health checks                               │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  FeatureCatalog                                         │
│  - Stores features in database                          │
│  - Enables querying by source/category                  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Dashboard (Phase 5)                                    │
│  - Displays all features for experiment builder         │
└─────────────────────────────────────────────────────────┘
```

## Step-by-Step Guide

### Step 1: Create Provider Class

Create a new file in `src/trading_server/src/data_providers/`:

```python
# src/trading_server/src/data_providers/sentiment_provider.py

import threading
import logging
from typing import List, Dict, Any
from data_providers.base_provider import DataProvider, Feature

logger = logging.getLogger(__name__)


class SentimentProvider(DataProvider):
    """Provider for market sentiment data"""
    
    def __init__(self):
        """Initialize sentiment provider"""
        self.subscribers = []
        self._subscriber_lock = threading.Lock()
        self.last_update_time = None
        # Initialize your data source connection here
        
    def get_features(self) -> List[Feature]:
        """
        Declare all features this provider offers.
        
        This method is called by the registry to discover features.
        Features declared here will automatically appear in the dashboard.
        
        :return: List of Feature objects with metadata
        """
        return [
            Feature(
                name="sentiment_bullish_pct",
                data_type=float,
                description="Percentage of bullish sentiment",
                source="sentiment",
                category="sentiment"
            ),
            Feature(
                name="sentiment_bearish_pct",
                data_type=float,
                description="Percentage of bearish sentiment",
                source="sentiment",
                category="sentiment"
            ),
            Feature(
                name="retail_long_pct",
                data_type=float,
                description="Retail traders long percentage",
                source="sentiment",
                category="sentiment"
            ),
        ]
    
    def get_current_data(self) -> Dict[str, Any]:
        """
        Return current data values for all declared features.
        
        Keys should match feature names from get_features().
        
        :return: Dictionary mapping feature names to current values
        """
        # Fetch real-time sentiment data from your source
        return {
            "sentiment_bullish_pct": 0.65,
            "sentiment_bearish_pct": 0.35,
            "retail_long_pct": 0.42,
        }
    
    def subscribe(self, callback):
        """
        Subscribe to data updates.
        
        When new data arrives, call the callback with the data dictionary.
        
        :param callback: Function to call with data updates
        """
        with self._subscriber_lock:
            self.subscribers.append(callback)
        
        # Subscribe to your data source updates
        # When data arrives, call: callback(self.get_current_data())
    
    def collect_historical(self, start, end):
        """
        Optional: Collect historical data for backtesting.
        
        :param start: Start timestamp/date
        :param end: End timestamp/date
        :return: DataFrame with historical data, or None if not supported
        """
        # Implement if you want to support historical backtesting
        return None
```

### Step 2: Register Provider in Server

Update `src/trading_server/src/server.py` to register your provider:

```python
# In Server.__init__() or appropriate initialization method

from data_providers.sentiment_provider import SentimentProvider

# Create and register provider
sentiment_provider = SentimentProvider()
self.__provider_registry.register_provider("sentiment", sentiment_provider)

# Sync catalog to store features in database
self.__feature_catalog.sync_with_registry(self.__provider_registry)
```

### Step 3: Feature Declaration Patterns

#### Basic Feature

```python
Feature(
    name="feature_name",           # Unique identifier
    data_type=float,               # Python type (float, int, str, bool)
    source="provider_name",         # Provider identifier
    description="Human readable description",
    category="category_name"       # Optional: price, technical, sentiment, etc.
)
```

#### Feature Naming Conventions

- Use snake_case for feature names
- Include symbol suffix for pair-specific features: `rsi_14_EURUSD`
- Be descriptive: `sentiment_bullish_pct` not `bullish`

#### Feature Categories

Common categories:
- `price` - Price data (bid, ask, mid, spread)
- `technical` - Technical indicators (RSI, MACD, Bollinger Bands)
- `sentiment` - Market sentiment data
- `economic` - Economic calendar events
- `news` - News/social media data

### Step 4: Testing Your Provider

Create a test file `tests/unit/test_sentiment_provider.py`:

```python
import unittest
from data_providers.sentiment_provider import SentimentProvider

class TestSentimentProvider(unittest.TestCase):
    def setUp(self):
        self.provider = SentimentProvider()
    
    def test_get_features(self):
        """Test that provider declares features correctly"""
        features = self.provider.get_features()
        self.assertIsInstance(features, list)
        self.assertGreater(len(features), 0)
        
        # Check feature structure
        for feature in features:
            self.assertIsNotNone(feature.name)
            self.assertIsNotNone(feature.data_type)
            self.assertIsNotNone(feature.source)
    
    def test_get_current_data(self):
        """Test that provider returns current data"""
        data = self.provider.get_current_data()
        self.assertIsInstance(data, dict)
        
        # Check that all declared features have values
        features = self.provider.get_features()
        for feature in features:
            self.assertIn(feature.name, data)
```

## Best Practices

### Error Handling

```python
def get_current_data(self) -> Dict[str, Any]:
    """Handle errors gracefully"""
    try:
        # Fetch data
        return data
    except Exception as e:
        logger.error(f"Error fetching data: {e}", exc_info=True)
        # Return default/NaN values instead of raising
        return {
            "feature1": 0.0,
            "feature2": 0.0,
        }
```

### Thread Safety

```python
class MyProvider(DataProvider):
    def __init__(self):
        self._lock = threading.Lock()
        self.subscribers = []
        self._subscriber_lock = threading.Lock()
    
    def subscribe(self, callback):
        with self._subscriber_lock:
            self.subscribers.append(callback)
```

### Data Validation

```python
def get_current_data(self) -> Dict[str, Any]:
    """Validate data before returning"""
    data = self._fetch_raw_data()
    
    # Validate types match declared features
    features = self.get_features()
    for feature in features:
        value = data.get(feature.name)
        if value is not None:
            # Ensure type matches
            if not isinstance(value, feature.data_type):
                logger.warning(f"Type mismatch for {feature.name}")
                data[feature.name] = feature.data_type(value)  # Convert
    
    return data
```

### Performance

- Cache expensive calculations
- Use async/background threads for data fetching
- Batch updates when possible

## Example: Complete Provider

See `src/trading_server/src/data_providers/price_provider.py` and `indicator_provider.py` for complete examples.

## Integration Checklist

- [ ] Provider class inherits from `DataProvider`
- [ ] Implements `get_features()` returning `List[Feature]`
- [ ] Implements `get_current_data()` returning `Dict[str, Any]`
- [ ] Implements `subscribe(callback)` for updates
- [ ] Feature names match keys in `get_current_data()`
- [ ] Provider registered in `Server.__init__()` or startup
- [ ] Features synced to catalog after registration
- [ ] Unit tests written
- [ ] Error handling implemented
- [ ] Thread-safe if needed

## Troubleshooting

### Features Not Appearing in Dashboard

1. Check provider is registered: `registry.get_provider("provider_name")`
2. Check features discovered: `registry.discover_features()`
3. Check catalog sync: `catalog.sync_with_registry(registry)`
4. Check database: Query `features` table directly

### Type Mismatches

- Ensure `get_current_data()` returns values matching declared types
- Use type conversion if needed: `float(value)`

### Performance Issues

- Use caching for expensive calculations
- Batch database updates
- Consider async data fetching

## Next Steps

After adding your provider:
1. Features will appear in the Feature Catalog page (Phase 5)
2. Users can select your features in Experiment Builder
3. Features will be included in training data automatically

## Support

For questions or issues:
- Check existing providers for patterns
- Review `DataProviderRegistry` and `FeatureCatalog` code
- See PRD Section 7 for requirements
