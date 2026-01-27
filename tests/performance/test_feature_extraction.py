"""
Performance benchmarks for feature extraction
"""
import pytest
import time
import sys
import os
from unittest.mock import Mock

# Add source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/backend/trading_server/src'))


class TestFeatureExtractionBenchmark:
    """Benchmark feature extraction performance"""
    
    def test_feature_extraction_benchmark(self):
        """Benchmark feature extraction performance"""
        from data_providers.price_provider import PriceDataProvider
        from models.currency_pair import CurrencyPair
        
        # Create currency pair
        pair = CurrencyPair("EURUSD", 5)
        
        # Simulate 1000 ticks
        start_time = time.time()
        
        for i in range(1000):
            # Update price
            price = 1.1000 + (i * 0.0001)
            pair.update(price, price + 0.0002)
            
            # Get features
            provider = PriceDataProvider(pair)
            features = provider.get_features()
            
            # Get current data
            data = provider.get_current_data()
        
        elapsed_time = time.time() - start_time
        time_per_tick = elapsed_time / 1000
        
        # Verify meets performance target: < 50ms per tick
        assert time_per_tick < 0.05, f"Feature extraction too slow: {time_per_tick*1000:.2f}ms per tick"
        
        print(f"Feature extraction: {time_per_tick*1000:.2f}ms per tick (target: <50ms)")
    
    def test_indicator_calculation_benchmark(self):
        """Benchmark indicator calculation performance"""
        from data_providers.indicator_provider import IndicatorProvider
        from models.currency_pair import CurrencyPair
        
        pair = CurrencyPair("EURUSD", 5)
        provider = IndicatorProvider(pair, window_size=50)
        
        # Simulate 100 ticks with indicator calculation
        start_time = time.time()
        
        for i in range(100):
            price = 1.1000 + (i * 0.0001)
            pair.update(price, price + 0.0002)
            
            # Get indicator features
            features = provider.get_features()
            data = provider.get_current_data()
        
        elapsed_time = time.time() - start_time
        time_per_tick = elapsed_time / 100
        
        # Verify meets performance target: < 10ms per feature
        assert time_per_tick < 0.01, f"Indicator calculation too slow: {time_per_tick*1000:.2f}ms per tick"
        
        print(f"Indicator calculation: {time_per_tick*1000:.2f}ms per tick (target: <10ms)")


class TestDatabaseQueryBenchmark:
    """Benchmark database query performance"""
    
    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        db.get_connection = Mock(return_value=mock_conn)
        mock_conn.cursor.return_value = mock_cursor
        return db, mock_conn, mock_cursor
    
    def test_feature_catalog_query_benchmark(self, mock_db):
        """Benchmark feature catalog query performance"""
        db, mock_conn, mock_cursor = mock_db
        
        # Mock query result
        mock_cursor.fetchall.return_value = [
            ("feature1", "float", "source1", "desc1", "cat1", True) for _ in range(100)
        ]
        
        from features.catalog import FeatureCatalog
        
        catalog = FeatureCatalog(db)
        
        start_time = time.time()
        features = catalog.get_all_features()
        elapsed_time = time.time() - start_time
        
        # Verify meets performance target: < 100ms
        assert elapsed_time < 0.1, f"Feature catalog query too slow: {elapsed_time*1000:.2f}ms"
        
        print(f"Feature catalog query: {elapsed_time*1000:.2f}ms (target: <100ms)")
    
    def test_trade_history_query_benchmark(self, mock_db):
        """Benchmark trade history query performance"""
        db, mock_conn, mock_cursor = mock_db
        
        # Mock query result
        from datetime import datetime
        mock_cursor.fetchall.return_value = [
            (1, 1, "uuid-1", "EURUSD", "BUY", 1.1000, 1.1050, 50.0, "closed", datetime.utcnow())
            for _ in range(1000)
        ]
        
        from performance.trade_logger import TradeLogger
        
        logger = TradeLogger(db=db)
        
        start_time = time.time()
        trades = logger.get_trade_history(model_id=1, limit=1000)
        elapsed_time = time.time() - start_time
        
        # Verify meets performance target: < 200ms
        assert elapsed_time < 0.2, f"Trade history query too slow: {elapsed_time*1000:.2f}ms"
        
        print(f"Trade history query: {elapsed_time*1000:.2f}ms (target: <200ms)")
