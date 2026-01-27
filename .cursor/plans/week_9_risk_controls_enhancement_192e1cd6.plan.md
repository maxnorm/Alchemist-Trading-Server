---
name: Week 9 Risk Controls Enhancement
overview: Implement pre-trade exposure limits with throttle controls to enhance production risk management and prevent excessive exposure.
todos:
  - id: week9_pre_trade_module
    content: Create PreTradeControls class in src/mt5-python_server/src/risk/pre_trade_controls.py with exposure limits, throttle controls, leverage validation, market hours, and feed quality checks
    status: completed
  - id: week9_pre_trade_integration
    content: Integrate PreTradeControls into TradingController._execute_action() method to validate orders before execution
    status: completed
    dependencies:
      - week9_pre_trade_module
  - id: week9_pre_trade_config
    content: Add pre-trade control parameters to RiskConfig dataclass with from_env() support
    status: completed
    dependencies:
      - week9_pre_trade_module
  - id: week9_pre_trade_tests
    content: Create comprehensive integration tests in tests/integration/test_pre_trade_controls.py covering all validation scenarios
    status: completed
    dependencies:
      - week9_pre_trade_integration
---

# Week 9: Risk Controls Enhancement

## Overview

Week 9 focuses on implementing comprehensive pre-trade risk controls to prevent excessive exposure and ensure safe trading operations.

**Pre-Trade Exposure Limits**: Add comprehensive pre-trade risk checks and throttle controls to prevent excessive exposure, validate leverage limits, enforce market hours, and ensure feed quality before trade execution.

---

## Pre-Trade Exposure Limits (Days 25-27)

### Current State Analysis

**Existing Risk Controls:**

- `RiskManager.can_trade()` checks: balance, drawdown, daily loss, max open positions
- `RiskManager.check_correlation_risk()` checks for correlated positions
- Basic risk checks in `trading_controller.py` line 291

**Missing Components:**

- Pre-trade exposure limit checks (total exposure across all positions)
- Throttle controls (max trades per minute/hour)
- Leverage limit validation
- Market hours validation
- Feed quality checks before trade execution

### Implementation Plan

#### Step 1: Create Pre-Trade Controls Module

**File to create:** `src/mt5-python_server/src/risk/pre_trade_controls.py`

**Implementation:**

```python
class PreTradeControls:
    """Comprehensive pre-trade validation before order execution"""
    
    def __init__(
        self,
        max_total_exposure_pct: float = 0.30,  # Max 30% total exposure
        max_trades_per_minute: int = 3,
        max_trades_per_hour: int = 20,
        max_leverage: float = 100.0,
        trading_hours_start: int = 0,  # 00:00 UTC
        trading_hours_end: int = 24,    # 24:00 UTC
    ):
        self.max_total_exposure_pct = max_total_exposure_pct
        self.max_trades_per_minute = max_trades_per_minute
        self.max_trades_per_hour = max_trades_per_hour
        self.max_leverage = max_leverage
        self.trading_hours_start = trading_hours_start
        self.trading_hours_end = trading_hours_end
        
        # Trade throttle tracking
        self.trade_timestamps = []  # List of (timestamp, action_type)
    
    def validate_order(
        self, 
        account: Account, 
        order: Order,
        current_positions: Dict[str, Position],
        feed_status: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Comprehensive pre-trade validation"""
        checks = [
            self.check_exposure_limits(account, order, current_positions),
            self.check_throttle_limits(),
            self.check_leverage_limits(account, order),
            self.check_market_hours(),
            self.check_feed_quality(feed_status),
        ]
        
        for passed, reason in checks:
            if not passed:
                return False, reason
        
        return True, None
    
    def check_exposure_limits(
        self, 
        account: Account, 
        order: Order,
        current_positions: Dict[str, Position]
    ) -> Tuple[bool, Optional[str]]:
        """Check total exposure across all positions"""
        # Calculate current exposure
        current_exposure = sum(
            pos.volume * pos.entry_price 
            for pos in current_positions.values()
        )
        
        # Calculate new exposure if order executes
        new_exposure = current_exposure + (order.volume * order.price)
        
        # Check against account balance
        max_exposure = account.balance * self.max_total_exposure_pct
        
        if new_exposure > max_exposure:
            return False, (
                f"Total exposure limit exceeded: "
                f"{new_exposure/account.balance:.1%} > {self.max_total_exposure_pct:.1%}"
            )
        
        return True, None
    
    def check_throttle_limits(self) -> Tuple[bool, Optional[str]]:
        """Check trade frequency limits"""
        now = datetime.now()
        
        # Clean old timestamps (older than 1 hour)
        self.trade_timestamps = [
            ts for ts in self.trade_timestamps
            if (now - ts).total_seconds() < 3600
        ]
        
        # Check per-minute limit
        recent_minute = [
            ts for ts in self.trade_timestamps
            if (now - ts).total_seconds() < 60
        ]
        if len(recent_minute) >= self.max_trades_per_minute:
            return False, (
                f"Trade throttle limit exceeded: "
                f"{len(recent_minute)} trades in last minute > {self.max_trades_per_minute}"
            )
        
        # Check per-hour limit
        if len(self.trade_timestamps) >= self.max_trades_per_hour:
            return False, (
                f"Trade throttle limit exceeded: "
                f"{len(self.trade_timestamps)} trades in last hour > {self.max_trades_per_hour}"
            )
        
        return True, None
    
    def record_trade(self, action_type: str):
        """Record trade execution for throttle tracking"""
        self.trade_timestamps.append((datetime.now(), action_type))
    
    def check_leverage_limits(
        self, 
        account: Account, 
        order: Order
    ) -> Tuple[bool, Optional[str]]:
        """Check leverage limits"""
        # Calculate required margin
        contract_size = 100000
        required_margin = (order.volume * order.price * contract_size) / self.max_leverage
        
        # Check available margin
        margin_free = getattr(account, "margin_free", account.balance)
        
        if required_margin > margin_free:
            return False, (
                f"Insufficient margin: required={required_margin:.2f}, "
                f"available={margin_free:.2f}"
            )
        
        return True, None
    
    def check_market_hours(self) -> Tuple[bool, Optional[str]]:
        """Check if trading is allowed during current market hours"""
        now = datetime.utcnow()
        current_hour = now.hour
        
        if not (self.trading_hours_start <= current_hour < self.trading_hours_end):
            return False, (
                f"Outside trading hours: {current_hour}:00 UTC "
                f"(allowed: {self.trading_hours_start}:00-{self.trading_hours_end}:00)"
            )
        
        return True, None
    
    def check_feed_quality(
        self, 
        feed_status: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Check market feed quality before trading"""
        if not feed_status.get("ready", False):
            return False, "Market feed not ready"
        
        # Check for stale data
        max_staleness = feed_status.get("max_staleness_seconds", float("inf"))
        if max_staleness > 300:  # 5 minutes
            return False, f"Market feed stale: {max_staleness:.0f} seconds"
        
        return True, None
```

#### Step 2: Integrate Pre-Trade Controls into Trading Controller

**File to modify:** `src/mt5-python_server/src/trading_controller.py`

**Changes:**

1. Import `PreTradeControls` at top
2. Initialize `PreTradeControls` in `__init__` method
3. Add pre-trade validation before action execution in `_execute_action` method
4. Record trades for throttle tracking

**Key integration points:**

- Line 290-302: Add pre-trade validation before `can_trade` check
- Line 475-495: Add pre-trade validation in `_execute_action` before order submission
- Line 308: Record trade execution for throttle tracking

#### Step 3: Add Configuration

**File to modify:** `src/mt5-python_server/src/domain/config/risk_config.py`

**Changes:**

- Add pre-trade control parameters to `RiskConfig` dataclass
- Add `from_env()` support for pre-trade configuration

### Testing

**File to create:** `tests/integration/test_pre_trade_controls.py`

**Test cases:**

1. Test exposure limit blocking when total exposure exceeds limit
2. Test throttle limits (per-minute and per-hour)
3. Test leverage limit validation
4. Test market hours validation
5. Test feed quality checks
6. Test integration with `TradingController`

### Success Criteria

- ✅ Trades blocked when exposure limits exceeded
- ✅ Throttle controls prevent excessive trade frequency
- ✅ All pre-trade checks integrated into trading loop
- ✅ Tests pass with 100% coverage of pre-trade controls
- ✅ Logging captures all blocked trades with reasons

---

## Dependencies

- ✅ Week 8 completed (DRL robustness)
- ✅ Existing `RiskManager` class
- ✅ Existing `TradingController` class

---

## Implementation Order

1. **Day 25-26**: Implement pre-trade controls module and integrate into trading controller
2. **Day 26-27**: Test pre-trade controls and fix any issues
3. **Day 27-28**: Additional testing, documentation, and refinement

---

## Files Summary

### Files to Create

- `src/mt5-python_server/src/risk/pre_trade_controls.py`
- `tests/integration/test_pre_trade_controls.py`

### Files to Modify

- `src/mt5-python_server/src/trading_controller.py`
- `src/mt5-python_server/src/domain/config/risk_config.py`

---

## Risk Mitigation

1. **Pre-Trade Controls**: Start with conservative limits, monitor and adjust based on trading patterns
2. **Testing**: Comprehensive integration tests before production deployment
3. **Gradual Rollout**: Test pre-trade controls in paper trading before enabling in live trading

---

## Success Metrics

- **Pre-Trade Controls**: 
  - 100% of trades validated before execution
  - Zero trades executed when limits exceeded
  - Throttle limits enforced correctly
  - All validation checks logged with reasons for blocked trades