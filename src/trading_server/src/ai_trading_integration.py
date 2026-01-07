"""
AI Trading Integration
Integrates DQN agent with the trading server for live AI-powered trading
"""

import os
import threading
from typing import Optional
from trading_controller import TradingController
from training.live_trainer import LiveTrainer
from models.account import Account
from infrastructure.factories.agent_factory import AgentFactory
from infrastructure.factories.risk_manager_factory import RiskManagerFactory
from domain.config.agent_config import AgentConfig
from domain.config.risk_config import RiskConfig
from domain.config.training_config import TrainingConfig


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
        self.trading_enabled = (
            os.getenv("AI_TRADING_ENABLED", "false").lower() == "true"
        )
        self.live_training_enabled = (
            os.getenv("AI_LIVE_TRAINING_ENABLED", "true").lower() == "true"
        )

    def initialize_agent_for_account(
        self, account: Account, model_path: Optional[str] = None
    ):
        """
        Initialize AI agent for an account
        :param account: Account to initialize agent for
        :param model_path: Optional path to pre-trained model
        """
        if account.login in self.controllers:
            print(f"Agent already initialized for account {account.login}")
            return

        # Get environment for this account
        env = self.server.get_environment(account.login)
        if env is None:
            print(f"No environment found for account {account.login}")
            return

        # Use factories to create components
        risk_config = (
            RiskConfig.from_env()
            if os.getenv("RISK_CONFIG_FROM_ENV")
            else RiskConfig.default()
        )
        risk_manager = RiskManagerFactory.create_risk_manager(risk_config)

        # Create agent using factory (start with 0 experiences, will adapt as it learns)
        agent_config = AgentConfig.for_live_trading(experience_count=0)
        agent = AgentFactory.create_agent(env, agent_config, model_path)

        # If loading existing model, update epsilon based on current experience count
        if model_path and os.path.exists(model_path):
            try:
                # Try to get experience count from loaded agent
                experience_count = len(agent.memory)
                if experience_count > 0:
                    agent.update_epsilon_adaptive(experience_count)
            except Exception:
                # If memory not accessible, use default
                pass

        # Create trading controller
        controller = TradingController(
            agent=agent,
            environment=env,
            account=account,
            risk_manager=risk_manager,
            trading_enabled=self.trading_enabled,
        )

        self.controllers[account.login] = controller

        # Create live trainer if enabled
        if self.live_training_enabled:
            # Use configuration from environment or defaults
            training_config = TrainingConfig.from_env()
            training_config.trading_enabled = self.trading_enabled

            trainer = LiveTrainer(
                agent=agent,
                environment=env,
                account=account,
                risk_manager=risk_manager,
                save_dir=os.path.join("models", f"account_{account.login}"),
                config=training_config,
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
            print(
                f"AI trading integrated with live trainer for account {account_login}"
            )

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
