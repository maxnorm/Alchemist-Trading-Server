"""
AI Trading Integration
Integrates DQN agent with the trading server for live AI-powered trading
"""
import os
import threading
from typing import Optional
from agents.dqn_agent import DQNAgent
from environments.live_env import LiveTradingEnv
from utils.risk_management import RiskManager
from trading_controller import TradingController
from training.live_trainer import LiveTrainer
from models.account import Account


class AITradingIntegration:
    """Integration layer for AI trading with the server"""
    
    def __init__(self, server_instance):
        """
        Initialize AI trading integration
        :param server_instance: Server instance to integrate with
        """
        self.server = server_instance
        self.controllers = {}  # One controller per account
        self.trainers = {}  # Live trainers per account
        self.trading_enabled = os.getenv('AI_TRADING_ENABLED', 'false').lower() == 'true'
        self.live_training_enabled = os.getenv('AI_LIVE_TRAINING_ENABLED', 'true').lower() == 'true'
        
    def initialize_agent_for_account(self, account: Account, model_path: Optional[str] = None):
        """
        Initialize AI agent for an account
        :param account: Account to initialize agent for
        :param model_path: Optional path to pre-trained model
        """
        if account.login in self.controllers:
            print(f"Agent already initialized for account {account.login}")
            return
        
        # Get environment for this account
        if account.login not in self.server._Server__environments:
            print(f"No environment found for account {account.login}")
            return
        
        env = self.server._Server__environments[account.login]
        
        # Initialize risk manager
        risk_manager = RiskManager(
            max_position_size=0.1,  # 10% max per trade
            max_daily_loss=0.05,     # 5% max daily loss
            max_drawdown=0.20,       # 20% max drawdown
            stop_loss_pct=0.02,      # 2% stop loss
            take_profit_pct=0.04     # 4% take profit
        )
        
        # Initialize DQN agent
        state_shape = env.observation_space.shape  # (window_size, n_features)
        action_size = env.action_space.n
        
        agent = DQNAgent(
            state_shape=state_shape,
            action_size=action_size,
            learning_rate=0.001,
            discount_factor=0.95,
            epsilon=0.01,  # Low epsilon for live trading (minimal exploration)
            epsilon_min=0.01,
            epsilon_decay=1.0,  # No decay in live trading
            memory_size=10000,
            batch_size=32
        )
        
        # Load pre-trained model if provided
        if model_path and os.path.exists(model_path):
            try:
                agent.load(model_path)
                print(f"Loaded pre-trained model from {model_path}")
            except Exception as e:
                print(f"Error loading model: {e}. Using untrained agent.")
        
        # Create trading controller
        controller = TradingController(
            agent=agent,
            environment=env,
            account=account,
            risk_manager=risk_manager,
            trading_enabled=self.trading_enabled
        )
        
        self.controllers[account.login] = controller
        
        # Create live trainer if enabled
        if self.live_training_enabled:
            decision_interval = int(os.getenv('AI_DECISION_INTERVAL', '60'))
            episode_duration = int(os.getenv('AI_EPISODE_DURATION_HOURS', '24'))
            
            trainer = LiveTrainer(
                agent=agent,
                environment=env,
                account=account,
                risk_manager=risk_manager,
                save_dir=os.path.join("models", f"account_{account.login}"),
                decision_interval=decision_interval,
                training_enabled=True,
                trading_enabled=self.trading_enabled,  # Use same setting as controller
                episode_duration_hours=episode_duration,
                min_experiences_before_training=100,
                save_freq_steps=1000
            )
            
            self.trainers[account.login] = trainer
            print(f"Live trainer initialized for account {account.login}")
        
        print(f"AI agent initialized for account {account.login}")
    
    def start_trading_for_account(self, account_login: str):
        """
        Start AI trading for an account
        :param account_login: Account login to start trading
        """
        if account_login not in self.controllers:
            print(f"No agent initialized for account {account_login}")
            return
        
        # Start live training if enabled
        if self.live_training_enabled and account_login in self.trainers:
            trainer = self.trainers[account_login]
            trainer.start()
            print(f"Live training started for account {account_login}")
        
        # Start trading controller
        controller = self.controllers[account_login]
        
        # Start controller in separate thread (only if not using live trainer)
        if not self.live_training_enabled:
            trading_thread = threading.Thread(target=controller.start, daemon=True)
            trading_thread.start()
            print(f"AI trading started for account {account_login}")
        else:
            print(f"AI trading integrated with live trainer for account {account_login}")
    
    def stop_trading_for_account(self, account_login: str):
        """
        Stop AI trading for an account
        :param account_login: Account login to stop trading
        """
        # Stop live trainer if running
        if account_login in self.trainers:
            trainer = self.trainers[account_login]
            trainer.stop()
            print(f"Live training stopped for account {account_login}")
        
        # Stop trading controller
        if account_login in self.controllers:
            controller = self.controllers[account_login]
            controller.stop()
            print(f"AI trading stopped for account {account_login}")
    
    def enable_trading(self):
        """Enable live trading (safety feature)"""
        self.trading_enabled = True
        for controller in self.controllers.values():
            controller.trading_enabled = True
        for trainer in self.trainers.values():
            trainer.enable_trading()
        print("⚠️  Live trading ENABLED - Real money at risk!")
    
    def disable_trading(self):
        """Disable live trading"""
        self.trading_enabled = False
        for controller in self.controllers.values():
            controller.trading_enabled = False
        for trainer in self.trainers.values():
            trainer.disable_trading()
        print("Live trading DISABLED")
