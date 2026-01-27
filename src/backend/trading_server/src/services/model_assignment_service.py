"""
Model Assignment Service

Handles model assignment to accounts and creates TradingController instances
for live trading with trained models.
"""

import os
import threading
import logging
from typing import Optional, Dict, TYPE_CHECKING
from models.account import Account
from trading_controller import TradingController
from infrastructure.factories.agent_factory import AgentFactory
from infrastructure.factories.risk_manager_factory import RiskManagerFactory

if TYPE_CHECKING:
    from environments.live_env import LiveTradingEnv  # noqa: F401
from mlops.model_registry import ModelRegistry
from domain.config.agent_config import AgentConfig
from domain.config.risk_config import RiskConfig
from domain.environment_type import EnvironmentType
from risk.kill_switch import KillSwitch
from risk.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from risk.oms import OrderManagementSystem
from performance.session_manager import SessionManager
from performance.trade_logger import TradeLogger
from performance.equity_tracker import EquityTracker

logger = logging.getLogger(__name__)


class ModelAssignmentService:
    """
    Service for handling model assignments to accounts.

    Creates TradingController instances when models are assigned to live accounts.
    """

    def __init__(self, server_instance):
        """
        Initialize model assignment service

        :param server_instance: Server instance to integrate with
        """
        self.server = server_instance
        self.controllers: Dict[int, TradingController] = (
            {}
        )  # account_login -> controller
        self.controller_threads: Dict[int, threading.Thread] = (
            {}
        )  # account_login -> thread
        self._lock = threading.Lock()

    def handle_model_assignment(
        self, account_id: int, account_login: int, model_id: int, trading_mode: str
    ) -> bool:
        """
        Handle model assignment event - create TradingController for live trading

        :param account_id: Account ID from database
        :param account_login: Account login number
        :param model_id: Model ID to assign
        :param trading_mode: Trading mode ('live' or 'paper')
        :return: True if successful, False otherwise
        """
        try:
            with self._lock:
                # Check if controller already exists for this account
                if account_login in self.controllers:
                    logger.warning(
                        f"TradingController already exists for account {account_login}. "
                        "Stopping existing controller before creating new one."
                    )
                    self.handle_model_unassignment(account_login)

                # Get account from server
                account = self.server.get_account(account_login)
                if not account:
                    logger.error(
                        f"Account {account_login} not found in server. "
                        "Account must be connected before assigning model."
                    )
                    return False

                # Validate account type
                account_type = account.account_type
                if trading_mode == "live" and account_type != "live":
                    logger.error(
                        f"Cannot assign model to account {account_login}: "
                        f"Account must be type 'live' for live trading. "
                        f"Current type: '{account_type}'"
                    )
                    return False

                # Get model from registry
                model_registry = ModelRegistry(self.server._Server__db)
                model = model_registry.get_model(model_id)
                if not model:
                    logger.error(f"Model {model_id} not found in registry")
                    return False

                # Validate model stage
                if trading_mode == "live" and model.stage.value not in (
                    "production",
                    "paper",
                ):
                    logger.error(
                        f"Cannot assign model {model_id} to live account: "
                        f"Model must be in 'production' or 'paper' stage. "
                        f"Current stage: '{model.stage.value}'"
                    )
                    return False

                # Get model path (downloads from MLflow if needed)
                model_path = model_registry.get_model_path(model_id)
                if not model_path:
                    logger.error(
                        f"Could not get model path for model {model_id}. "
                        "Model may not have been saved properly."
                    )
                    return False

                # Get environment for account
                env = self._get_or_create_environment(account, model)
                if not env:
                    logger.error(
                        f"Could not create environment for account {account_login}"
                    )
                    return False

                # Create agent with trained model
                agent_config = AgentConfig.for_live_trading(experience_count=0)
                agent = AgentFactory.create_agent(
                    env=env, config=agent_config, model_path=model_path
                )

                # Set agent to inference mode (no exploration)
                agent.epsilon = 0.0
                agent.epsilon_min = 0.0

                # Create risk manager
                risk_config = (
                    RiskConfig.from_env()
                    if os.getenv("RISK_CONFIG_FROM_ENV")
                    else RiskConfig.default()
                )
                risk_manager = RiskManagerFactory.create_risk_manager(risk_config)

                # Create safety components
                kill_switch = KillSwitch(
                    broker_adapter=account.broker_adapter,
                    database=self.server._Server__db,
                )

                circuit_breaker = CircuitBreaker(
                    config=CircuitBreakerConfig(),
                    database=self.server._Server__db,
                )

                oms = OrderManagementSystem(
                    database=self.server._Server__db,
                )

                # Create performance tracking components
                session_manager = SessionManager(db=self.server._Server__db)
                session_id = session_manager.create_session(
                    model_id=model_id, start_balance=account.balance
                )

                trade_logger = TradeLogger(db=self.server._Server__db)
                equity_tracker = EquityTracker(db=self.server._Server__db)

                # Determine trading enabled based on environment variable
                trading_enabled = (
                    os.getenv("AI_TRADING_ENABLED", "false").lower() == "true"
                )

                # Create TradingController
                controller = TradingController(
                    agent=agent,
                    environment=env,
                    account=account,
                    risk_manager=risk_manager,
                    trading_enabled=trading_enabled,
                    kill_switch=kill_switch,
                    circuit_breaker=circuit_breaker,
                    oms=oms,
                    database=self.server._Server__db,
                    model_id=model_id,
                    session_id=session_id,
                    trade_logger=trade_logger,
                    equity_tracker=equity_tracker,
                )

                # Store controller
                self.controllers[account_login] = controller

                # Start TradingController in background thread
                trading_thread = threading.Thread(target=controller.start, daemon=True)
                trading_thread.start()
                self.controller_threads[account_login] = trading_thread

                logger.info(
                    f"TradingController created and started for account {account_login} "
                    f"with model {model_id} (Trading: {'ENABLED' if trading_enabled else 'DISABLED'})"
                )

                return True

        except Exception as e:
            logger.error(
                f"Error handling model assignment for account {account_login}, model {model_id}: {e}",
                exc_info=True,
            )
            return False

    def handle_model_unassignment(self, account_login: int) -> bool:
        """
        Handle model unassignment - stop TradingController

        :param account_login: Account login number
        :return: True if successful, False otherwise
        """
        try:
            with self._lock:
                if account_login not in self.controllers:
                    logger.warning(
                        f"No TradingController found for account {account_login}"
                    )
                    return False

                controller = self.controllers[account_login]

                # Stop controller
                controller.stop()

                # Wait for thread to finish (with timeout)
                if account_login in self.controller_threads:
                    thread = self.controller_threads[account_login]
                    thread.join(timeout=10.0)
                    if thread.is_alive():
                        logger.warning(
                            f"TradingController thread for account {account_login} "
                            "did not stop within timeout"
                        )

                # Clean up
                del self.controllers[account_login]
                if account_login in self.controller_threads:
                    del self.controller_threads[account_login]

                logger.info(
                    f"TradingController stopped and removed for account {account_login}"
                )

                return True

        except Exception as e:
            logger.error(
                f"Error handling model unassignment for account {account_login}: {e}",
                exc_info=True,
            )
            return False

    def _get_or_create_environment(
        self, account: Account, model
    ) -> Optional["LiveTradingEnv"]:
        """
        Get or create environment for account using model's features

        :param account: Account instance
        :param model: Model instance from registry
        :return: LiveTradingEnv instance or None
        """
        try:
            # Check if environment already exists
            env = self.server._Server__environment_factory.get_environment(
                account.login
            )
            if env:
                return env

            # Get connectors for model's currency pairs (from experiment)
            # For now, we'll need to get currency pairs from the experiment
            # This is a simplified version - in production, you'd get pairs from model metadata
            from experiments.models import ExperimentRepository

            exp_repo = ExperimentRepository(self.server._Server__db)
            if model.experiment_id:
                experiment = exp_repo.get_experiment(model.experiment_id)
                if experiment:
                    currency_pairs = experiment.currency_pairs
                else:
                    logger.warning(
                        f"Experiment {model.experiment_id} not found. "
                        "Using default currency pairs."
                    )
                    currency_pairs = ["EURUSD", "GBPUSD"]  # Default
            else:
                logger.warning(
                    "Model has no experiment_id. Using default currency pairs."
                )
                currency_pairs = ["EURUSD", "GBPUSD"]  # Default

            # Get connectors from server's connector registry
            connectors = []
            all_connectors = (
                self.server._Server__connector_registry.get_all_connectors()
            )

            for symbol in currency_pairs:
                connector = None

                # First try to get by name (symbol might be the name)
                connector = self.server._Server__connector_registry.get_connector(
                    symbol
                )

                # If not found, search all connectors by symbol
                if not connector:
                    for conn_name, conn in all_connectors.items():
                        if (
                            hasattr(conn, "currency_pair")
                            and conn.currency_pair.symbol == symbol
                        ):
                            connector = conn
                            break
                        # Also check config.symbol
                        if hasattr(conn, "config") and hasattr(conn.config, "symbol"):
                            if conn.config.symbol == symbol:
                                connector = conn
                                break

                if connector:
                    connectors.append(connector)
                else:
                    logger.warning(
                        f"Connector not found for {symbol} in registry. "
                        "Creating basic connector."
                    )
                    # Create basic connector if not in registry
                    from connectors.mt5_price_connector import MT5PriceConnector
                    from connectors.base import ConnectorConfig
                    from models.currency_pair import CurrencyPair

                    pair = CurrencyPair(symbol=symbol, digits=5)
                    connector_config = ConnectorConfig(
                        source="mt5", symbol=symbol, extra_config={"digits": 5}
                    )
                    connector = MT5PriceConnector(
                        currency_pair=pair, config=connector_config
                    )
                    connector.connect()
                    connectors.append(connector)

            if not connectors:
                logger.error("No connectors available for environment creation")
                return None

            # Create environment with model's features
            env = self.server._Server__environment_factory.create_environment(
                environment_type=EnvironmentType.LIVE,
                account=account,
                connectors=connectors,
                window_size=50,  # Default, could come from model hyperparameters
                seed=None,  # No seed for live trading
                features=model.features,
            )

            return env

        except Exception as e:
            logger.error(
                f"Error creating environment for account {account.login}: {e}",
                exc_info=True,
            )
            return None

    def get_controller(self, account_login: int) -> Optional[TradingController]:
        """
        Get TradingController for account

        :param account_login: Account login number
        :return: TradingController instance or None
        """
        return self.controllers.get(account_login)
