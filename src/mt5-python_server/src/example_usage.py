"""
Example Usage of AI Trading System
Demonstrates how to train and use the AI trading agent
"""
import os
from agents.dqn_agent import DQNAgent
from environments.live_env import LiveTradingEnv
from utils.risk_management import RiskManager
from utils.feature_engineering import FeatureEngineer
from training.train_agent import AgentTrainer
from trading_controller import TradingController


def example_train_agent():
    """Example: Train the agent"""
    print("=== Training DQN Agent ===")
    
    # This is a simplified example - in practice, you'd load real account/data
    # For now, this shows the structure
    
    # 1. Initialize components
    state_shape = (50, 15)  # (window_size, n_features)
    action_size = 3  # Hold, Buy, Sell
    
    agent = DQNAgent(
        state_shape=state_shape,
        action_size=action_size,
        learning_rate=0.001,
        discount_factor=0.95
    )
    
    # 2. Create environment (would use real account/data in practice)
    # env = LiveTradingEnv(account, data_providers, window_size=50)
    
    # 3. Initialize risk manager
    risk_manager = RiskManager(
        max_position_size=0.1,
        max_daily_loss=0.05,
        stop_loss_pct=0.02,
        take_profit_pct=0.04
    )
    
    # 4. Train agent
    # trainer = AgentTrainer(agent, env, account, risk_manager)
    # trainer.train(num_episodes=100, save_freq=10)
    
    print("Training example structure created")
    print("In production, connect to real account and data providers")


def example_use_trained_agent():
    """Example: Use trained agent for live trading"""
    print("=== Using Trained Agent ===")
    
    # 1. Load trained agent
    model_path = "models/checkpoint_ep100"
    
    state_shape = (50, 15)
    action_size = 3
    
    agent = DQNAgent(state_shape=state_shape, action_size=action_size)
    
    if os.path.exists(model_path):
        agent.load(model_path)
        print(f"Loaded model from {model_path}")
    else:
        print(f"Model not found at {model_path}. Using untrained agent.")
    
    # 2. Initialize environment with real account/data
    # env = LiveTradingEnv(account, data_providers)
    
    # 3. Initialize risk manager
    risk_manager = RiskManager()
    
    # 4. Create trading controller
    # controller = TradingController(
    #     agent=agent,
    #     environment=env,
    #     account=account,
    #     risk_manager=risk_manager,
    #     trading_enabled=False  # Set to True to enable live trading
    # )
    
    # 5. Start trading
    # controller.start()
    
    print("Live trading example structure created")
    print("Set trading_enabled=True to enable live trading (use with caution!)")


if __name__ == "__main__":
    print("AI Trading System - Example Usage")
    print("\n1. Training Example:")
    example_train_agent()
    print("\n2. Live Trading Example:")
    example_use_trained_agent()
    print("\nNote: These are structural examples. Connect to real MT5 accounts for actual use.")
