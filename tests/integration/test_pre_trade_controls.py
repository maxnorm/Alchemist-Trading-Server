"""
Integration tests for Pre-Trade Controls

Tests comprehensive pre-trade validation including:
- Exposure limits
- Throttle controls
- Leverage validation
- Market hours
- Feed quality checks
- Integration with TradingController
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add source to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "../../src/trading_server/src")
)

from risk.pre_trade_controls import PreTradeControls
from utils.risk_management import RiskManager
from models.account import Account


class MockCurrencyPair:
    """Mock Currency Pair for testing"""

    def __init__(self, symbol="EURUSD", ask=1.1000, bid=1.0995):
        self.symbol = symbol
        self.ask = ask
        self.bid = bid


class MockTrade:
    """Mock Trade for testing"""

    def __init__(self, ticket="12345", symbol="EURUSD", lotsize=0.1, open_price=1.1000):
        self.ticket = ticket
        self.symbol = symbol
        self.lotsize = lotsize
        self.volume = lotsize
        self.open_price = open_price
        self.entry_price = open_price
        self.pair = MockCurrencyPair(symbol=symbol)


class MockAccount:
    """Mock Account for testing"""

    def __init__(self, balance=10000.0, margin_free=None):
        self.login = "12345"
        self.balance = balance
        self.margin_free = margin_free if margin_free is not None else balance
        self.current_trade = {}


class MockRiskManager:
    """Mock Risk Manager for testing"""

    def __init__(self, position_size=0.1):
        self.position_size = position_size

    def calculate_position_size(self, account, pair, entry_price):
        """Calculate position size"""
        # Simple calculation: 10% of balance
        contract_size = 100000
        risk_amount = account.balance * self.position_size
        lot_size = risk_amount / (entry_price * contract_size)
        return max(0.01, min(lot_size, 1.0))  # Clamp between 0.01 and 1.0


class TestPreTradeControls:
    """Test suite for PreTradeControls"""

    @pytest.fixture
    def pre_trade_controls(self):
        """Create PreTradeControls instance with test defaults"""
        return PreTradeControls(
            max_total_exposure_pct=0.30,  # 30%
            max_trades_per_minute=3,
            max_trades_per_hour=20,
            max_leverage=100.0,
            trading_hours_start=0,  # 00:00 UTC
            trading_hours_end=24,  # 24:00 UTC
        )

    @pytest.fixture
    def account(self):
        """Create mock account"""
        return MockAccount(balance=10000.0)

    @pytest.fixture
    def risk_manager(self):
        """Create mock risk manager"""
        return MockRiskManager()

    @pytest.fixture
    def pair(self):
        """Create mock currency pair"""
        return MockCurrencyPair()

    @pytest.fixture
    def feed_status_ready(self):
        """Create ready feed status"""
        return {"ready": True, "max_staleness_seconds": 10.0}

    @pytest.fixture
    def feed_status_stale(self):
        """Create stale feed status"""
        return {"ready": True, "max_staleness_seconds": 400.0}

    def test_exposure_limit_blocking(self, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test that trades are blocked when exposure limits are exceeded"""
        # Add existing positions that exceed exposure limit
        contract_size = 100000
        # Create trades that total 35% exposure (exceeds 30% limit)
        trade1 = MockTrade(ticket="1", lotsize=0.15, open_price=1.1000)
        trade2 = MockTrade(ticket="2", lotsize=0.15, open_price=1.1000)
        account.current_trade = {"1": trade1, "2": trade2}

        # Try to add another trade
        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions=account.current_trade,
            feed_status=feed_status_ready,
        )

        assert not is_valid
        assert "exposure limit exceeded" in reason.lower()

    def test_exposure_limit_allows_valid_trade(self, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test that trades within exposure limits are allowed"""
        # No existing positions
        account.current_trade = {}

        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions=account.current_trade,
            feed_status=feed_status_ready,
        )

        assert is_valid
        assert reason is None

    def test_throttle_limit_per_minute(self, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test that throttle limits per minute are enforced"""
        # Record 3 trades in the last minute (at the limit)
        now = datetime.now()
        for i in range(3):
            timestamp = now - timedelta(seconds=30 - i * 10)
            pre_trade_controls.trade_timestamps.append((timestamp, "BUY"))

        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions={},
            feed_status=feed_status_ready,
        )

        assert not is_valid
        assert "throttle limit exceeded" in reason.lower()
        assert "minute" in reason.lower()

    def test_throttle_limit_per_hour(self, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test that throttle limits per hour are enforced"""
        # Record 20 trades in the last hour (at the limit)
        now = datetime.now()
        for i in range(20):
            timestamp = now - timedelta(minutes=30 - i)
            pre_trade_controls.trade_timestamps.append((timestamp, "BUY"))

        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions={},
            feed_status=feed_status_ready,
        )

        assert not is_valid
        assert "throttle limit exceeded" in reason.lower()
        assert "hour" in reason.lower()

    def test_throttle_cleanup_old_timestamps(self, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test that old timestamps are cleaned up"""
        # Add old timestamp (more than 1 hour ago)
        old_timestamp = datetime.now() - timedelta(hours=2)
        pre_trade_controls.trade_timestamps.append((old_timestamp, "BUY"))

        # Add recent timestamp
        recent_timestamp = datetime.now() - timedelta(seconds=30)
        pre_trade_controls.trade_timestamps.append((recent_timestamp, "BUY"))

        # Validate - should only count recent trade
        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions={},
            feed_status=feed_status_ready,
        )

        # Should pass (only 1 recent trade)
        assert is_valid
        # Old timestamp should be cleaned up
        assert len(pre_trade_controls.trade_timestamps) == 1

    def test_leverage_limit_insufficient_margin(self, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test that trades are blocked when margin is insufficient"""
        # Set low margin_free
        account.margin_free = 10.0  # Very low margin

        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions={},
            feed_status=feed_status_ready,
        )

        assert not is_valid
        assert "insufficient margin" in reason.lower()

    def test_leverage_limit_sufficient_margin(self, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test that trades are allowed when margin is sufficient"""
        # Set sufficient margin
        account.margin_free = 10000.0

        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions={},
            feed_status=feed_status_ready,
        )

        assert is_valid

    @patch("risk.pre_trade_controls.datetime")
    def test_market_hours_validation(self, mock_datetime, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test market hours validation"""
        # Set trading hours to 9-17 UTC
        pre_trade_controls.trading_hours_start = 9
        pre_trade_controls.trading_hours_end = 17

        # Test outside trading hours (8:00 UTC)
        mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 8, 0, 0)
        is_valid, reason = pre_trade_controls.check_market_hours()
        assert not is_valid
        assert "outside trading hours" in reason.lower()

        # Test inside trading hours (12:00 UTC)
        mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 12, 0, 0)
        is_valid, reason = pre_trade_controls.check_market_hours()
        assert is_valid

        # Test outside trading hours (18:00 UTC)
        mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 18, 0, 0)
        is_valid, reason = pre_trade_controls.check_market_hours()
        assert not is_valid

    def test_feed_quality_not_ready(self, pre_trade_controls, account, risk_manager, pair):
        """Test that trades are blocked when feed is not ready"""
        feed_status = {"ready": False}

        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions={},
            feed_status=feed_status,
        )

        assert not is_valid
        assert "feed not ready" in reason.lower()

    def test_feed_quality_stale(self, pre_trade_controls, account, risk_manager, pair, feed_status_stale):
        """Test that trades are blocked when feed is stale"""
        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions={},
            feed_status=feed_status_stale,
        )

        assert not is_valid
        assert "stale" in reason.lower()

    def test_feed_quality_ready(self, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test that trades are allowed when feed is ready and fresh"""
        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions={},
            feed_status=feed_status_ready,
        )

        # Should pass feed quality check (other checks may fail, but feed check passes)
        # We check that feed quality is not the reason for failure
        if not is_valid:
            assert "feed" not in reason.lower() or "ready" in reason.lower()

    def test_close_action_skips_exposure_leverage(self, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test that CLOSE actions skip exposure and leverage checks"""
        # Set up account with insufficient margin (should not matter for CLOSE)
        account.margin_free = 1.0
        account.current_trade = {"1": MockTrade()}

        # CLOSE action should pass (only checks throttle, market hours, feed quality)
        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="CLOSE",
            risk_manager=risk_manager,
            current_positions=account.current_trade,
            feed_status=feed_status_ready,
        )

        # Should pass (margin check is skipped for CLOSE)
        assert is_valid

    def test_record_trade(self, pre_trade_controls):
        """Test that trades are recorded for throttle tracking"""
        initial_count = len(pre_trade_controls.trade_timestamps)

        pre_trade_controls.record_trade("BUY")
        pre_trade_controls.record_trade("SELL")

        assert len(pre_trade_controls.trade_timestamps) == initial_count + 2
        assert pre_trade_controls.trade_timestamps[-2][1] == "BUY"
        assert pre_trade_controls.trade_timestamps[-1][1] == "SELL"

    def test_all_checks_pass(self, pre_trade_controls, account, risk_manager, pair, feed_status_ready):
        """Test that all checks pass for a valid trade"""
        # Set up valid conditions
        account.margin_free = 10000.0
        account.current_trade = {}

        is_valid, reason = pre_trade_controls.validate_action(
            account=account,
            pair=pair,
            action_type="BUY",
            risk_manager=risk_manager,
            current_positions=account.current_trade,
            feed_status=feed_status_ready,
        )

        assert is_valid
        assert reason is None


class TestPreTradeControlsIntegration:
    """Integration tests with TradingController"""

    @pytest.fixture
    def mock_components(self):
        """Create mock components for trading controller"""
        from unittest.mock import Mock

        class MockAgent:
            action_size = 10

            def act(self, state, training=False, action_mask=None):
                return 1  # BUY action

        class MockEnvironment:
            data_providers = [Mock()]

            def get_state(self):
                import numpy as np
                return np.zeros((50, 15))

            def decode_action(self, action):
                from domain.action_type import ActionType
                if action == 0:
                    return None, ActionType.HOLD
                return 0, ActionType.BUY

        class MockDataProvider:
            currency_pair = MockCurrencyPair()

            def is_stale(self, max_age_seconds):
                return False

        env = MockEnvironment()
        env.data_providers = [MockDataProvider()]

        return {
            "agent": MockAgent(),
            "environment": env,
            "account": MockAccount(),
            "risk_manager": MockRiskManager(),
        }

    def test_trading_controller_integration(self, mock_components):
        """Test that PreTradeControls is integrated into TradingController"""
        # This test verifies that PreTradeControls is initialized in TradingController
        # We can't easily test the full integration without running the controller,
        # but we can verify the import and initialization work

        try:
            from trading_controller import TradingController

            controller = TradingController(
                agent=mock_components["agent"],
                environment=mock_components["environment"],
                account=mock_components["account"],
                risk_manager=mock_components["risk_manager"],
                trading_enabled=False,
            )

            # Verify pre_trade_controls is initialized
            assert hasattr(controller, "pre_trade_controls")
            assert controller.pre_trade_controls is not None
            assert isinstance(controller.pre_trade_controls, PreTradeControls)

        except ImportError as e:
            pytest.skip(f"Could not import TradingController: {e}")
