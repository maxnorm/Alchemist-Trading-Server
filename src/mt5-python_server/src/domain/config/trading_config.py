"""
Trading system configuration
Centralizes configuration values and supports environment variables
"""
import os


class TradingConfig:
    """Trading system configuration"""
    
    # Window size and feature configuration
    WINDOW_SIZE = int(os.getenv('WINDOW_SIZE', '50'))
    DECISION_INTERVAL = int(os.getenv('DECISION_INTERVAL', '60'))  # seconds
    FEATURES_PER_PAIR = int(os.getenv('FEATURES_PER_PAIR', '20'))
    
    # Position and risk management
    MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '0.1'))  # 10% of account
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '0.05'))  # 5% daily loss
    MAX_DRAWDOWN = float(os.getenv('MAX_DRAWDOWN', '0.20'))  # 20% drawdown
    STOP_LOSS_PCT = float(os.getenv('STOP_LOSS_PCT', '0.02'))  # 2% stop loss
    TAKE_PROFIT_PCT = float(os.getenv('TAKE_PROFIT_PCT', '0.04'))  # 4% take profit
    MAX_OPEN_POSITIONS = int(os.getenv('MAX_OPEN_POSITIONS', '3'))
    MAX_CORRELATED_POSITIONS = int(os.getenv('MAX_CORRELATED_POSITIONS', '2'))
    
    # Data staleness
    MAX_DATA_STALENESS = int(os.getenv('MAX_DATA_STALENESS', '60'))  # seconds
    MAX_DATA_STALENESS_WARNING = int(os.getenv('MAX_DATA_STALENESS_WARNING', '300'))  # seconds
    
    # Tick streaming
    TICK_BATCH_SIZE = int(os.getenv('TICK_BATCH_SIZE', '50'))
    TICK_BATCH_INTERVAL = float(os.getenv('TICK_BATCH_INTERVAL', '2.0'))  # seconds
    TICK_BUFFER_MAX_SIZE = int(os.getenv('TICK_BUFFER_MAX_SIZE', '200'))
    DB_WRITE_QUEUE_SIZE = int(os.getenv('DB_WRITE_QUEUE_SIZE', '1000'))
    
    # DQN Agent configuration
    LEARNING_RATE = float(os.getenv('LEARNING_RATE', '0.001'))
    DISCOUNT_FACTOR = float(os.getenv('DISCOUNT_FACTOR', '0.95'))
    EPSILON = float(os.getenv('EPSILON', '1.0'))
    EPSILON_MIN = float(os.getenv('EPSILON_MIN', '0.01'))
    EPSILON_DECAY = float(os.getenv('EPSILON_DECAY', '0.995'))
    MEMORY_SIZE = int(os.getenv('MEMORY_SIZE', '10000'))
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '32'))
    TARGET_UPDATE_FREQ = int(os.getenv('TARGET_UPDATE_FREQ', '100'))
    USE_DOUBLE_DQN = os.getenv('USE_DOUBLE_DQN', 'true').lower() == 'true'
    USE_PER = os.getenv('USE_PER', 'true').lower() == 'true'
    PER_ALPHA = float(os.getenv('PER_ALPHA', '0.6'))
    PER_BETA = float(os.getenv('PER_BETA', '0.4'))
    PER_BETA_INCREMENT = float(os.getenv('PER_BETA_INCREMENT', '0.001'))
    
    # Feature drift detection
    DRIFT_THRESHOLD = float(os.getenv('DRIFT_THRESHOLD', '0.25'))
    DRIFT_N_BINS = int(os.getenv('DRIFT_N_BINS', '10'))
    
    # Economic calendar
    ECONOMIC_CALENDAR_HOURS_AHEAD = int(os.getenv('ECONOMIC_CALENDAR_HOURS_AHEAD', '24'))
    
    # Technical indicators
    SMA_PERIOD_20 = int(os.getenv('SMA_PERIOD_20', '20'))
    SMA_PERIOD_50 = int(os.getenv('SMA_PERIOD_50', '50'))
    EMA_PERIOD_12 = int(os.getenv('EMA_PERIOD_12', '12'))
    EMA_PERIOD_26 = int(os.getenv('EMA_PERIOD_26', '26'))
    RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
    MACD_FAST = int(os.getenv('MACD_FAST', '12'))
    MACD_SLOW = int(os.getenv('MACD_SLOW', '26'))
    MACD_SIGNAL = int(os.getenv('MACD_SIGNAL', '9'))
    BOLLINGER_PERIOD = int(os.getenv('BOLLINGER_PERIOD', '20'))
    BOLLINGER_STD = float(os.getenv('BOLLINGER_STD', '2.0'))
    
    @classmethod
    def get_all_config(cls) -> dict:
        """
        Get all configuration values as dictionary
        
        :return: Dictionary of all config values
        """
        return {
            'WINDOW_SIZE': cls.WINDOW_SIZE,
            'DECISION_INTERVAL': cls.DECISION_INTERVAL,
            'FEATURES_PER_PAIR': cls.FEATURES_PER_PAIR,
            'MAX_POSITION_SIZE': cls.MAX_POSITION_SIZE,
            'MAX_DAILY_LOSS': cls.MAX_DAILY_LOSS,
            'MAX_DRAWDOWN': cls.MAX_DRAWDOWN,
            'STOP_LOSS_PCT': cls.STOP_LOSS_PCT,
            'TAKE_PROFIT_PCT': cls.TAKE_PROFIT_PCT,
            'MAX_OPEN_POSITIONS': cls.MAX_OPEN_POSITIONS,
            'MAX_CORRELATED_POSITIONS': cls.MAX_CORRELATED_POSITIONS,
            'MAX_DATA_STALENESS': cls.MAX_DATA_STALENESS,
            'MAX_DATA_STALENESS_WARNING': cls.MAX_DATA_STALENESS_WARNING,
            'TICK_BATCH_SIZE': cls.TICK_BATCH_SIZE,
            'TICK_BATCH_INTERVAL': cls.TICK_BATCH_INTERVAL,
            'TICK_BUFFER_MAX_SIZE': cls.TICK_BUFFER_MAX_SIZE,
            'DB_WRITE_QUEUE_SIZE': cls.DB_WRITE_QUEUE_SIZE,
            'LEARNING_RATE': cls.LEARNING_RATE,
            'DISCOUNT_FACTOR': cls.DISCOUNT_FACTOR,
            'EPSILON': cls.EPSILON,
            'EPSILON_MIN': cls.EPSILON_MIN,
            'EPSILON_DECAY': cls.EPSILON_DECAY,
            'MEMORY_SIZE': cls.MEMORY_SIZE,
            'BATCH_SIZE': cls.BATCH_SIZE,
            'TARGET_UPDATE_FREQ': cls.TARGET_UPDATE_FREQ,
            'USE_DOUBLE_DQN': cls.USE_DOUBLE_DQN,
            'USE_PER': cls.USE_PER,
            'PER_ALPHA': cls.PER_ALPHA,
            'PER_BETA': cls.PER_BETA,
            'PER_BETA_INCREMENT': cls.PER_BETA_INCREMENT,
            'DRIFT_THRESHOLD': cls.DRIFT_THRESHOLD,
            'DRIFT_N_BINS': cls.DRIFT_N_BINS,
            'ECONOMIC_CALENDAR_HOURS_AHEAD': cls.ECONOMIC_CALENDAR_HOURS_AHEAD
        }
