---
name: "Week 8: DRL Robustness - Adaptive Learning Rates & Reward Normalization"
overview: Implement adaptive learning rate scheduling and reward normalization to improve DRL agent robustness in non-stationary market conditions, addressing reward hacking and learning rate stability issues.
todos:
  - id: week8_learning_rate_scheduler
    content: Create learning rate scheduler module with ReduceLROnPlateau and CosineAnnealing schedulers
    status: completed
  - id: week8_integrate_scheduler
    content: Integrate learning rate scheduler with DQN agent, modify optimizer to use scheduler
    status: completed
    dependencies:
      - week8_learning_rate_scheduler
  - id: week8_reward_normalizer
    content: Create reward normalizer module with running statistics and adaptive normalization
    status: completed
  - id: week8_integrate_normalizer
    content: Integrate reward normalizer with LiveTradingEnv.calculate_reward() method
    status: completed
    dependencies:
      - week8_reward_normalizer
  - id: week8_reward_monitor
    content: Create reward monitor module to track reward components and detect anomalies
    status: completed
  - id: week8_integrate_monitor
    content: Integrate reward monitor with environment and add logging/alerting
    status: completed
    dependencies:
      - week8_reward_monitor
  - id: week8_tests
    content: Create unit tests for adaptive learning, reward normalization, and integration tests
    status: completed
    dependencies:
      - week8_integrate_scheduler
      - week8_integrate_normalizer
      - week8_integrate_monitor
---

# Week 8: DRL Robustness - Adaptive Learning Rates & Reward Normalization

## Overview

Week 8 focuses on improving the robustness of the Deep Reinforcement Learning (DRL) agent by implementing adaptive learning rate scheduling and reward normalization. These improvements address the non-stationary nature of financial markets and prevent reward hacking, where agents exploit reward function flaws instead of maximizing actual profit.

## Context

**Current State:**

- DQN agent uses fixed learning rate (0.001 default) in [`src/mt5-python_server/src/agents/dqn_agent.py`](src/mt5-python_server/src/agents/dqn_agent.py)
- Reward function in [`src/mt5-python_server/src/environments/live_env.py`](src/mt5-python_server/src/environments/live_env.py) combines multiple components but lacks normalization
- No mechanism to adapt learning rates based on training progress or market conditions
- Reward magnitudes can vary significantly, leading to unstable learning

**Target State:**

- Adaptive learning rate scheduler that adjusts based on training metrics (reduce on plateau, cosine annealing)
- Normalized reward function to prevent reward hacking
- Reward stability monitoring to detect anomalies
- Improved agent performance across different market regimes

## Implementation Tasks

### Task 8.1: Adaptive Learning Rate Scheduler (Days 23-25)

**Files to Modify:**

- [`src/mt5-python_server/src/agents/dqn_agent.py`](src/mt5-python_server/src/agents/dqn_agent.py) - Add learning rate scheduler integration

**Files to Create:**

- `src/mt5-python_server/src/agents/learning_rate_scheduler.py` - Learning rate scheduler implementations

**Implementation Details:**

1. **Create Learning Rate Scheduler Module**

   - Implement `ReduceLROnPlateauScheduler` that reduces learning rate when training loss plateaus
   - Implement `CosineAnnealingScheduler` for cyclical learning rate schedules
   - Implement `AdaptiveScheduler` that combines multiple strategies
   - Support for monitoring metrics: loss, reward, Sharpe ratio, drawdown

2. **Integrate with DQN Agent**

   - Add `learning_rate_scheduler` parameter to `DQNAgent.__init__()`
   - Modify `_build_model()` to use scheduler-aware optimizer
   - Add `update_learning_rate()` method that calls scheduler after each training step
   - Store learning rate history for monitoring

3. **Scheduler Configuration**

   - Reduce on plateau: monitor training loss, reduce by factor (0.5) after N steps without improvement (patience=10)
   - Cosine annealing: cycle length based on training episodes
   - Minimum learning rate threshold to prevent too-small rates

**Success Criteria:**

- Learning rate adapts based on training progress
- Scheduler can be configured via agent config
- Learning rate history logged for monitoring
- Tests verify scheduler reduces learning rate appropriately

### Task 8.2: Reward Normalization (Days 23-25)

**Files to Modify:**

- [`src/mt5-python_server/src/environments/live_env.py`](src/mt5-python_server/src/environments/live_env.py) - Add reward normalization

**Files to Create:**

- `src/mt5-python_server/src/environments/reward_normalizer.py` - Reward normalization utilities

**Implementation Details:**

1. **Create Reward Normalizer**

   - Implement `RewardNormalizer` class with:
     - Running statistics (mean, std) for reward normalization
     - Exponential moving average for adaptive normalization
     - Clip extreme rewards to prevent outliers
     - Window-based normalization for recent rewards

2. **Integrate with Environment**

   - Add `reward_normalizer` to `LiveTradingEnv.__init__()`
   - Modify `calculate_reward()` to normalize rewards before returning
   - Normalize rewards using running statistics (z-score normalization)
   - Clip normalized rewards to reasonable range (e.g., [-3, 3] standard deviations)

3. **Reward Stability Monitoring**

   - Track reward statistics (mean, std, min, max) over time
   - Detect reward distribution shifts (indicates reward hacking or market regime change)
   - Log reward statistics periodically

**Success Criteria:**

- Rewards are normalized to stable distribution
- Reward statistics tracked and logged
- No reward hacking detected (stable reward distribution)
- Tests verify normalization works correctly

### Task 8.3: Reward Function Stability Monitoring (Days 24-25)

**Files to Modify:**

- [`src/mt5-python_server/src/environments/live_env.py`](src/mt5-python_server/src/environments/live_env.py) - Add monitoring

**Files to Create:**

- `src/mt5-python_server/src/environments/reward_monitor.py` - Reward monitoring utilities

**Implementation Details:**

1. **Create Reward Monitor**

   - Track reward components separately (Sharpe, drawdown, volatility, transaction costs)
   - Detect sudden changes in reward distribution
   - Monitor for reward hacking patterns (e.g., agent exploits specific reward component)
   - Alert when reward statistics deviate significantly

2. **Integration**

   - Add `RewardMonitor` to environment
   - Log reward statistics to MLflow or structured logs
   - Create alerts for reward anomalies

**Success Criteria:**

- Reward components monitored separately
- Anomalies detected and logged
- Monitoring integrated with observability stack

### Task 8.4: Testing & Validation (Days 25)

**Files to Create:**

- `tests/unit/test_adaptive_learning.py` - Tests for adaptive learning rates
- `tests/unit/test_reward_normalization.py` - Tests for reward normalization
- `tests/integration/test_drl_robustness.py` - Integration tests

**Test Coverage:**

- Learning rate scheduler reduces rate on plateau
- Cosine annealing cycles correctly
- Reward normalization produces stable distribution
- Reward monitor detects anomalies
- Agent training stability improved with adaptive rates

## Technical Design

### Learning Rate Scheduler Architecture

```python
class ReduceLROnPlateauScheduler:
    """Reduces learning rate when metric plateaus"""
    def __init__(self, factor=0.5, patience=10, min_lr=1e-6, monitor='loss'):
        self.factor = factor
        self.patience = patience
        self.min_lr = min_lr
        self.monitor = monitor
        self.best_metric = None
        self.wait_count = 0
    
    def step(self, metric_value, optimizer):
        """Update learning rate based on metric"""
        if self.best_metric is None or metric_value < self.best_metric:
            self.best_metric = metric_value
            self.wait_count = 0
        else:
            self.wait_count += 1
            if self.wait_count >= self.patience:
                new_lr = max(optimizer.learning_rate * self.factor, self.min_lr)
                optimizer.learning_rate.assign(new_lr)
                self.wait_count = 0
```

### Reward Normalization Architecture

```python
class RewardNormalizer:
    """Normalizes rewards using running statistics"""
    def __init__(self, alpha=0.99, clip_range=(-3, 3)):
        self.alpha = alpha  # EMA factor
        self.clip_range = clip_range
        self.reward_mean = 0.0
        self.reward_std = 1.0
        self.count = 0
    
    def normalize(self, reward):
        """Normalize reward using running statistics"""
        # Update statistics
        self.count += 1
        self.reward_mean = self.alpha * self.reward_mean + (1 - self.alpha) * reward
        # ... update std similarly
        
        # Normalize
        normalized = (reward - self.reward_mean) / (self.reward_std + 1e-8)
        return np.clip(normalized, self.clip_range[0], self.clip_range[1])
```

## Dependencies

**Prerequisites:**

- Week 7: Feature versioning (completed)
- Week 4: Observability baseline (for monitoring integration)

**Dependencies:**

- TensorFlow/Keras for optimizer learning rate updates
- NumPy for reward statistics
- MLflow for logging (if available)

## Success Metrics

1. **Learning Rate Adaptation:**

   - Learning rate reduces when loss plateaus
   - Learning rate adapts to market conditions
   - Training stability improved (lower variance in loss)

2. **Reward Normalization:**

   - Reward distribution stable (coefficient of variation < 0.5)
   - No reward hacking detected
   - Agent performance consistent across market regimes

3. **Monitoring:**

   - Reward statistics logged
   - Anomalies detected and alerted
   - Learning rate history tracked

## Risk Mitigation

1. **Learning Rate Too Low:**

   - Set minimum learning rate threshold
   - Monitor training loss to detect stagnation
   - Allow manual override if needed

2. **Reward Normalization Issues:**

   - Use conservative normalization (don't over-normalize)
   - Monitor reward statistics to detect issues
   - Fallback to unnormalized rewards if needed

3. **Performance Regression:**

   - A/B test adaptive vs fixed learning rates
   - Monitor agent performance metrics
   - Rollback capability if performance degrades

## Deliverables

1. ✅ Learning rate scheduler module
2. ✅ Reward normalizer module
3. ✅ Reward monitor module
4. ✅ Integration with DQN agent
5. ✅ Integration with trading environment
6. ✅ Unit tests for all components
7. ✅ Integration tests
8. ✅ Documentation updates

## Phase 2 Gates

Week 8 completion gates:

- ✅ Adaptive learning rate scheduler implemented and tested
- ✅ Reward normalization implemented and tested
- ✅ Reward monitoring operational
- ✅ Agent training stability improved
- ✅ All tests passing

## References

- **FinRL Paper (2021)**: "FinRL: A Deep Reinforcement Learning Library for Automated Trading in Quantitative Finance" - Recommends adaptive learning rates and reward normalization for DRL trading systems
- **Research on Non-Stationarity**: Markets are non-stationary; fixed learning rates may fail in changing market conditions
- **Reward Hacking Prevention**: Normalization prevents agents from exploiting reward function flaws