#!/usr/bin/env python
"""
Quick test script for refactored connector and broker adapter system
Run from project root: python scripts/test_refactoring.py
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'mt5-python_server', 'src'))

def test_connector_imports():
    """Test that connector modules can be imported"""
    print("Testing connector imports...")
    try:
        from connectors.base import IDataSourceConnector, ConnectorConfig
        from connectors.mt5_price_connector import MT5PriceConnector
        from connectors.registry import ConnectorRegistry
        print("✅ Connector imports successful")
        return True
    except ImportError as e:
        print(f"❌ Connector import failed: {e}")
        return False

def test_broker_adapter_imports():
    """Test that broker adapter modules can be imported"""
    print("Testing broker adapter imports...")
    try:
        from trading.brokers.base import IBrokerAdapter, OrderStatus
        from trading.brokers.mt5_adapter import MT5BrokerAdapter
        from trading.brokers.factory import BrokerFactory
        print("✅ Broker adapter imports successful")
        return True
    except ImportError as e:
        print(f"❌ Broker adapter import failed: {e}")
        return False

def test_connector_registry():
    """Test connector registry functionality"""
    print("Testing connector registry...")
    try:
        from connectors.registry import ConnectorRegistry
        from connectors.base import ConnectorConfig
        from models.currency_pair import CurrencyPair
        
        registry = ConnectorRegistry()
        assert registry.get_connector_count() == 0
        
        # Create mock connector
        pair = CurrencyPair("EURUSD", 5)
        config = ConnectorConfig(source="mt5", symbol="EURUSD")
        
        from connectors.mt5_price_connector import MT5PriceConnector
        connector = MT5PriceConnector(currency_pair=pair, config=config)
        
        registry.register_connector("test_eurusd", connector)
        assert registry.get_connector_count() == 1
        
        # Test discovery
        features = registry.discover_features()
        print(f"✅ Connector registry test passed (discovered {len(features)} features)")
        return True
    except Exception as e:
        print(f"❌ Connector registry test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_broker_factory():
    """Test broker factory"""
    print("Testing broker factory...")
    try:
        from trading.brokers.factory import BrokerFactory
        from unittest.mock import Mock
        from mt5_connection.terminal import MT5Terminal
        
        # Create mock terminal
        mock_terminal = Mock(spec=MT5Terminal)
        
        # Test factory
        config = {"broker_type": "mt5"}
        adapter = BrokerFactory.create_from_config(config, terminal=mock_terminal)
        
        assert adapter is not None
        print("✅ Broker factory test passed")
        return True
    except Exception as e:
        print(f"❌ Broker factory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_account_with_adapter():
    """Test Account class with broker adapter"""
    print("Testing Account with broker adapter...")
    try:
        from models.account import Account
        from trading.brokers.mt5_adapter import MT5BrokerAdapter
        from unittest.mock import Mock, AsyncMock
        from mt5_connection.terminal import MT5Terminal
        
        # Create mock terminal and adapter
        mock_terminal = Mock(spec=MT5Terminal)
        mock_terminal.get_all_infos = AsyncMock(return_value={
            "login": 12345,
            "currency": "USD",
            "leverage": 100,
            "balance": 10000.0,
            "equity": 10000.0,
            "profit": 0.0,
            "margin": 0.0,
            "margin_free": 10000.0,
        })
        
        adapter = MT5BrokerAdapter.from_terminal(mock_terminal)
        account = Account(login=12345, broker_adapter=adapter)
        
        assert account.login == 12345
        assert account.broker_adapter is not None
        print("✅ Account with adapter test passed")
        return True
    except Exception as e:
        print(f"❌ Account with adapter test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all quick tests"""
    print("=" * 60)
    print("Testing Refactored System")
    print("=" * 60)
    print()
    
    results = []
    
    # Run tests
    results.append(("Imports (Connectors)", test_connector_imports()))
    results.append(("Imports (Brokers)", test_broker_adapter_imports()))
    results.append(("Connector Registry", test_connector_registry()))
    results.append(("Broker Factory", test_broker_factory()))
    results.append(("Account with Adapter", test_account_with_adapter()))
    
    # Summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All quick tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Run full test suite for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
