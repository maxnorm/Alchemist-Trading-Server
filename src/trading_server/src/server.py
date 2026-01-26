"""
Class Server for connection to MetaTrader5
"""

import os
import datetime
import threading
import time
from typing import Dict

from database import Database
from web_scraper.web_scraper_myfxbook import WebScraperMyfxbook
from utils.time_utils import print_with_datetime
from models.currency_pair import CurrencyPair
from models.account import Account
from infrastructure.zeromq.zeromq_connection_manager import ZeroMQConnectionManager
from infrastructure.zeromq.zeromq_broker import ZeroMQBroker
from infrastructure.connections.streamer_discovery_service import StreamerDiscoveryService

from features.catalog import FeatureCatalog
from environments.live_env import LiveTradingEnv
from http_controller import HTTPController


class Server:
    """
    Class for the server

    The server and data are base in the GMT+3 timezone
    """

    def __init__(self, verbose=False, database=None, scraper=None):
        self.__verbose = verbose
        self.__accounts = []
        self.__all_currency_pairs = {}
        self._connectors = (
            []
        )  # Unified connector pattern (replaces legacy __price_data_providers and __indicator_providers)
        self.__environments = {}

        self.__stop_char = "\n"

        self.__console_lock = threading.Lock()

        # Initialize HTTP controller for handling HTTP requests (Prometheus metrics, etc.)
        self.__http_controller = HTTPController(console_lock=self.__console_lock)

        # Use provided database or create new one
        self.__db = database if database is not None else Database()

        # Initialize connector registry and feature catalog
        from connectors.registry import ConnectorRegistry

        self._connector_registry = ConnectorRegistry()
        self.__feature_catalog = FeatureCatalog(self.__db)

        # Initialize experiment components (Phase 3)
        try:
            from experiments import (
                ExperimentBuilder,
                ExperimentRunner,
                OptunaHyperparameterTuner,
            )
            from infrastructure.factories.agent_factory import AgentFactory
            from infrastructure.factories.environment_factory import EnvironmentFactory
            from mlops.experiment_tracker import get_experiment_tracker

            # Initialize factories
            self.__agent_factory = AgentFactory()
            self.__environment_factory = EnvironmentFactory()

            # Initialize experiment tracker (MLflow) - non-blocking
            # MLflow initialization happens asynchronously to avoid blocking server startup
            try:
                self.__experiment_tracker = get_experiment_tracker(allow_dummy=True)
            except Exception as e:
                # If MLflow initialization fails, use dummy tracker and continue
                with self.__console_lock:
                    print_with_datetime(
                        f"Warning: MLflow tracker initialization failed, using dummy tracker: {e}"
                    )
                from mlops.experiment_tracker import DummyExperimentTracker

                self.__experiment_tracker = DummyExperimentTracker()

            # Initialize experiment components
            self.__experiment_builder = ExperimentBuilder(
                database=self.__db, feature_catalog=self.__feature_catalog
            )

            # Helper functions for experiment runner
            def get_account():
                # Return first account or create a default one
                if self.__accounts:
                    return self.__accounts[0]
                return None

            def get_risk_manager():
                from infrastructure.factories.risk_manager_factory import (
                    RiskManagerFactory,
                )
                from domain.config.risk_config import RiskConfig

                risk_config = RiskConfig.default()
                return RiskManagerFactory.create_risk_manager(risk_config)

            self.__experiment_runner = ExperimentRunner(
                database=self.__db,
                experiment_tracker=self.__experiment_tracker,
                agent_factory=self.__agent_factory,
                environment_factory=self.__environment_factory,
                get_account_func=get_account,
                get_risk_manager_func=get_risk_manager,
                feature_catalog=self.__feature_catalog,
            )

            self.__optuna_tuner = OptunaHyperparameterTuner(
                database=self.__db, experiment_runner=self.__experiment_runner
            )

            # Initialize experiment event consumer (Redis pub/sub)
            try:
                from infrastructure.messaging.experiment_consumer import ExperimentConsumer

                self.__experiment_consumer = ExperimentConsumer(
                    experiment_runner=self.__experiment_runner
                )
                self.__experiment_consumer.start()
                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime("Started Experiment Event Consumer")
            except Exception as e:
                # Experiment consumer is optional - log warning but don't fail
                with self.__console_lock:
                    print_with_datetime(
                        f"Warning: Failed to start experiment consumer: {e}"
                    )
                self.__experiment_consumer = None

            if self.__verbose:
                with self.__console_lock:
                    print_with_datetime("Initialized Experiment Management")
        except Exception as e:
            # Experiment components are optional - log warning but don't fail
            with self.__console_lock:
                print_with_datetime(
                    f"Warning: Failed to initialize experiment components: {e}"
                )
            self.__experiment_builder = None
            self.__experiment_runner = None
            self.__optuna_tuner = None
            self.__experiment_consumer = None

        # Initialize feature discovery (will be populated as providers register)
        if self.__verbose:
            with self.__console_lock:
                print_with_datetime(
                    "Initialized Data Provider Registry and Feature Catalog"
                )

        # Use provided scraper or create new one
        if scraper is not None:
            self.__myfxbook = scraper
        else:
            self.__myfxbook = WebScraperMyfxbook(
                email=os.getenv("MYFXBOOK_EMAIL"),
                password=os.getenv("MYFXBOOK_PASSWORD"),
                url=os.getenv("URL_MYFXBOOK"),
            )
        # Initialize ZeroMQ broker (routes EA PUSH -> PUB for subscribers)
        broker_host = os.getenv("ZMQ_HOST", "127.0.0.1")
        broker_port = int(os.getenv("ZMQ_BROKER_PORT", 5557))
        tick_port = int(os.getenv("ZMQ_TICK_PORT", 5555))
        
        self.__zmq_broker = ZeroMQBroker(
            host=broker_host,
            broker_port=broker_port,
            tick_port=tick_port,
            verbose=self.__verbose,
        )
        self.__zmq_broker.start()
        
        # Initialize ZeroMQ connection manager (EA binds, Python connects)
        self.__zmq_manager = ZeroMQConnectionManager(
            host=broker_host,
            order_port=int(os.getenv("ZMQ_ORDER_PORT", 5556)),
            tick_port=tick_port,
        )
        
        self.__streamer_discovery = StreamerDiscoveryService(
            zmq_manager=self.__zmq_manager,
            database=self.__db,
            host=broker_host,
            tick_port=tick_port,
            verbose=self.__verbose,
            server=self,  # Pass server reference for connector registration
        )
        
        # Start discovery service
        self.__streamer_discovery.start()

        # Track account IDs for connection lifecycle management
        self.__account_ids: Dict[int, int] = {}  # login -> account_id mapping

        if self.__verbose:
            print_with_datetime("ZeroMQ broker started")
            print_with_datetime("ZeroMQ connection manager initialized")
            print_with_datetime("Streamer discovery service started")

    def start(self):
        """
        Start the server
        """
        raise RuntimeError(
            "TCP listener removed. Use connect_account() with ZeroMQ EAs."
        )

    def __collect_economic_calendar(self, hour, minute):
        """
        Collect economic data from the economic calendar of yesterday at a specific time
        and store them in database
        """
        while True:
            now = datetime.datetime.now()
            if now.hour == hour and now.minute == minute and now.weekday() < 5:
                try:
                    data = self.__myfxbook.download_economic_calendar()
                    self.__db.insert_economic_calendar_data(data)

                    if self.__verbose:
                        with self.__console_lock:
                            print_with_datetime("Economic Calendar was download")
                except Exception as e:
                    with self.__console_lock:
                        print_with_datetime(
                            f"Error while downloading economic calendar: {e}"
                        )

            time.sleep(60)

    def connect_account(
        self, account_login: int, auth_token: str
    ) -> Account:
        """
        Connect to MT5 EA terminal for account via ZeroMQ (REQ/REP).
        
        Note: Streamers are auto-discovered and registered by StreamerDiscoveryService.
        This method only connects the trading terminal (for order execution).
        
        :param account_login: MT5 account login number
        :param auth_token: Authentication token for the account
        :return: Account instance
        """
        terminal = self.__zmq_manager.connect_terminal(
            account_login=account_login,
            auth_token=auth_token,
            port_offset=(account_login % 100),
        )

        # Streamer connection is handled by StreamerDiscoveryService
        # which auto-discovers streamers when they start publishing

        account = Account(account_login, terminal=terminal)
        self.__accounts.append(account)
        return account

    def _setup_terminal_disconnect_tracking(self, terminal, login):
        """Set up tracking for terminal disconnection"""
        try:
            # Store reference to account_id in terminal for cleanup
            account_id = self.__account_ids.get(login)
            if account_id:
                # Store account_id as attribute for cleanup
                terminal._account_id = account_id
                terminal._account_login = login
        except Exception as e:
            if self.__verbose:
                with self.__console_lock:
                    print_with_datetime(f"Error setting up disconnect tracking: {e}")

    def _handle_terminal_disconnect(self, terminal_id, login):
        """Handle terminal disconnection"""
        try:
            from infrastructure.db_integration import update_connection_status

            account_id = self.__account_ids.get(login)
            if account_id:
                update_connection_status(
                    account_id=account_id,
                    terminal_id=terminal_id,
                    is_connected=False,
                    disconnect_reason="Terminal disconnected",
                )

                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime(
                            f"Terminal {terminal_id} disconnected for account {login}"
                        )
        except Exception as e:
            with self.__console_lock:
                print_with_datetime(f"Error handling terminal disconnect: {e}")

    def _persist_account_to_db(self, account, terminal, client, infos):
        """
        Update account information in database (account must be pre-registered).
        """
        try:
            from infrastructure.db_integration import (
                update_account_in_db,
                log_connection,
            )

            # Extract account info
            account_info = account.info

            # Determine account type from EA message or account info
            account_type = infos.get("account_type", "live")
            if isinstance(account_type, int):
                # Convert MT5 account type code: 0=Demo, 2=Real
                account_type = "demo" if account_type == 0 else "live"

            # Get connection IP
            connection_ip = None
            try:
                connection_ip = client.getpeername()[0]
            except Exception:
                pass

            # Update account in database (only updates, never creates)
            account_id = update_account_in_db(
                login=account.login,
                account_type=account_type,
                broker_name=(
                    infos.get("broker_name") or account_info.broker_name
                    if hasattr(account_info, "broker_name")
                    else None
                ),
                broker_server=(
                    infos.get("broker_server") or account_info.broker_server
                    if hasattr(account_info, "broker_server")
                    else None
                ),
                currency=account_info.currency,
                leverage=account_info.leverage,
                account_name=infos.get("account_name"),
            )

            if account_id:
                # Store account_id mapping for connection tracking
                self.__account_ids[account.login] = account_id

                # Log connection
                log_connection(
                    account_id=account_id,
                    terminal_id=terminal.id,
                    ea_version=infos.get("ea_version"),
                    connection_ip=connection_ip,
                )

                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime(
                            f"Updated account {account.login} in database (ID: {account_id})"
                        )

                # Set up disconnect tracking on terminal
                self._setup_terminal_disconnect_tracking(terminal, account.login)
            else:
                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime(
                            f"Warning: Failed to update account {account.login} in database (account may not exist)"
                        )

        except ImportError:
            # Database integration not available - skip persistence
            if self.__verbose:
                with self.__console_lock:
                    print_with_datetime(
                        "Database integration not available - skipping account persistence"
                    )
        except Exception as e:
            # Log error but don't fail authentication
            with self.__console_lock:
                print_with_datetime(f"Error persisting account to database: {e}")

    @property
    def provider_registry(self):
        """
        Get the connector registry (for API access)
        Backward compatibility: returns connector registry instead of provider registry
        """
        return self._connector_registry

    @property
    def feature_catalog(self):
        """Get the feature catalog (for API access)"""
        return self.__feature_catalog

    @property
    def experiment_builder(self):
        """Get the experiment builder (for API access)"""
        return self.__experiment_builder

    @property
    def experiment_runner(self):
        """Get the experiment runner (for API access)"""
        return self.__experiment_runner

    @property
    def optuna_tuner(self):
        """Get the Optuna tuner (for API access)"""
        return self.__optuna_tuner

    def __del__(self):
        """Cleanup on server destruction"""
        try:
            if hasattr(self, '_Server__streamer_discovery'):
                self.__streamer_discovery.stop()
        except Exception:
            pass
        try:
            if hasattr(self, '_Server__zmq_broker'):
                self.__zmq_broker.stop()
        except Exception:
            pass
        return
