"""
Trading system constants
Centralizes all magic numbers and default values
"""


class TradingConstants:
    """Trading system constants"""
    
    # State configuration
    DEFAULT_WINDOW_SIZE = 50
    DEFAULT_FEATURES_PER_PAIR = 15
    
    # Timing
    DEFAULT_DECISION_INTERVAL_SECONDS = 60
    DEFAULT_EPISODE_DURATION_HOURS = 24
    
    # Training
    DEFAULT_MIN_EXPERIENCES_BEFORE_TRAINING = 100
    DEFAULT_SAVE_FREQUENCY_STEPS = 1000
    DEFAULT_MAX_TRAINING_STEPS = 1000  # For episode training
    
    # Risk management defaults
    DEFAULT_MAX_POSITION_SIZE = 0.1  # 10% of account per trade
    DEFAULT_MAX_DAILY_LOSS = 0.05   # 5% max daily loss
    DEFAULT_MAX_DRAWDOWN = 0.20     # 20% max drawdown
    DEFAULT_STOP_LOSS_PCT = 0.02   # 2% stop loss
    DEFAULT_TAKE_PROFIT_PCT = 0.04  # 4% take profit (2:1 ratio)
    DEFAULT_MAX_OPEN_POSITIONS = 3
    
    # Agent configuration defaults
    DEFAULT_LEARNING_RATE = 0.001
    DEFAULT_DISCOUNT_FACTOR = 0.95
    DEFAULT_EPSILON = 1.0
    DEFAULT_EPSILON_MIN = 0.01
    DEFAULT_EPSILON_DECAY = 0.995
    DEFAULT_MEMORY_SIZE = 10000
    DEFAULT_BATCH_SIZE = 32
    DEFAULT_TARGET_UPDATE_FREQ = 100
    
    # Live trading agent defaults
    DEFAULT_LIVE_EPSILON = 0.01  # Low epsilon for live trading (minimal exploration)
    DEFAULT_LIVE_EPSILON_DECAY = 1.0  # No decay in live trading
    
    # Contract sizes
    STANDARD_LOT_SIZE = 100000  # Standard lot = 100,000 units
    MIN_LOT_SIZE = 0.01
    
    # Transaction costs
    DEFAULT_TRANSACTION_COST = 0.001  # Default 0.1%
    
    # Technical indicators
    DEFAULT_RSI_PERIOD = 14
    DEFAULT_SMA_PERIOD_20 = 20
    DEFAULT_SMA_PERIOD_50 = 50
    DEFAULT_EMA_PERIOD_12 = 12
    DEFAULT_EMA_PERIOD_26 = 26
    DEFAULT_MACD_FAST = 12
    DEFAULT_MACD_SLOW = 26
    DEFAULT_MACD_SIGNAL = 9
    DEFAULT_BOLLINGER_PERIOD = 20
    DEFAULT_BOLLINGER_STD = 2.0
    
    # Performance metrics
    DEFAULT_METRICS_WINDOW_SIZE = 252  # 1 year of trading days
    
    # Reward calculation
    DEFAULT_ACTION_PENALTY = -0.01  # Penalty for holding without position
    DEFAULT_PROFIT_BONUS = 0.1  # Bonus for closing profitable position
    DEFAULT_SHARPE_SCALE = 10  # Scale factor for Sharpe ratio reward
    
    # Pip values
    DEFAULT_PIP_VALUE = 0.0001  # For most pairs
    JPY_PIP_VALUE = 0.01  # For JPY pairs
    
    # RSI thresholds
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    RSI_NEUTRAL = 50
