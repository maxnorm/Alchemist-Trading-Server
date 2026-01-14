"""
Class Server for connection to MetaTrader5
"""

import os
import datetime
import json
import socket
import threading
import time
from typing import Dict

from database import Database
from web_scraper.web_scraper_myfxbook import WebScraperMyfxbook
from utils.time_utils import print_with_datetime
from codes.socket_code import Socket
from mt5_connection.tick_streamer import MT5TickStreamer
from mt5_connection.terminal import MT5Terminal
from models.currency_pair import CurrencyPair
from models.account import Account

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
        self.__socket = None

        self.__streamers = []
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
            )

            self.__optuna_tuner = OptunaHyperparameterTuner(
                database=self.__db, experiment_runner=self.__experiment_runner
            )

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
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        server_ip = os.getenv("SERVER_IP")
        server_port = int(os.getenv("SERVER_PORT"))
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.bind((server_ip, server_port))

        # Track account IDs for connection lifecycle management
        self.__account_ids: Dict[int, int] = {}  # login -> account_id mapping

        if self.__verbose:
            print_with_datetime(f"Server socket bind to {server_ip}:{server_port}")

        self.start()

    def start(self):
        """
        Start the server
        """
        self.__socket.listen(5)

        if self.__verbose:
            with self.__console_lock:
                print_with_datetime("Server now listening for incoming connections")

        threading.Thread(target=self.__collect_economic_calendar, args=(17, 10)).start()

        while True:
            client_conn, client_address = self.__socket.accept()

            with self.__console_lock:
                print_with_datetime(f"Connected to {client_address}")

            self.__auth_socket(client_conn)

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

    def __auth_socket(self, client):
        """
        Receive auth code from the newly connected socket
        and create a new instance of TickStreamer or MT5Terminal
        """
        # Set socket timeout to prevent indefinite blocking (15 seconds for auth)
        # MT5 EA might need time to send authentication after connecting
        try:
            client.settimeout(15.0)
        except Exception:
            pass  # Socket might already be configured

        cum_data = ""
        max_attempts = 100  # Prevent infinite loop
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            try:
                # Peek at first byte to detect SSL handshake without consuming it
                peek_data = client.recv(1, socket.MSG_PEEK)
                if not peek_data:
                    if attempt <= 3:
                        import time

                        wait_time = 0.2 * attempt
                        time.sleep(wait_time)
                        continue
                    else:
                        self.__invalid_auth(
                            client,
                            f"Empty authentication message received after "
                            f"{attempt} attempts. Is the MT5 EA configured correctly?",
                        )
                        return

                # Check if this is an SSL handshake (first byte is 0x16)
                is_ssl = len(peek_data) > 0 and peek_data[0] == 0x16

                # If SSL detected, let HTTP controller handle it (it will wrap the socket)
                if is_ssl:
                    if self.__http_controller.handle_request(client, peek_data):
                        return
                    # If controller couldn't handle it (SSL not configured), reject
                    self.__invalid_auth(
                        client, "HTTPS connection detected but SSL is not configured"
                    )
                    return

                # Receive data normally (not SSL)
                data_bytes = client.recv(1024)
            except socket.timeout:
                self.__invalid_auth(
                    client,
                    "Authentication timeout: client did not send data within "
                    "15 seconds. Check if MT5 EA is running and configured correctly.",
                )
                return
            except Exception as e:
                self.__invalid_auth(client, f"Socket error during authentication: {e}")
                return

            # Handle empty data (client disconnected or sent nothing)
            if not data_bytes:
                if attempt <= 3:
                    # First few attempts with empty data - might be a timing issue, wait a bit
                    # MT5 EA might need time to send authentication after connecting
                    import time

                    wait_time = 0.2 * attempt  # Progressive wait: 0.2s, 0.4s, 0.6s
                    time.sleep(wait_time)
                    continue
                else:
                    # After 3 attempts with empty data, give up
                    self.__invalid_auth(
                        client,
                        f"Empty authentication message received after "
                        f"{attempt} attempts. Is the MT5 EA configured correctly?",
                    )
                    return

            # Detect HTTP requests (Prometheus metrics scraping, health checks, etc.)
            # Use HTTP controller to handle HTTP requests (pass raw bytes for detection)
            if self.__http_controller.handle_request(client, data_bytes):
                # Request was handled as HTTP, return early
                return

            # Decode bytes to string for MT5 authentication
            try:
                data = data_bytes.decode("utf-8")
            except UnicodeDecodeError:
                # If we can't decode, it's probably not valid MT5 data
                self.__invalid_auth(
                    client, "Invalid data encoding received. Expected UTF-8 text."
                )
                return

            cum_data += data

            if self.__stop_char in cum_data:
                # Extract the message up to the stop character
                infos_str = cum_data[: cum_data.index(self.__stop_char)].strip()

                # Check if we have actual content to parse
                if not infos_str:
                    self.__invalid_auth(
                        client, "Empty JSON message received (only whitespace)"
                    )
                    return

                try:
                    infos = json.loads(infos_str)
                except json.JSONDecodeError as e:
                    self.__invalid_auth(
                        client,
                        f"Invalid JSON in authentication message: {e}. Received: {repr(infos_str[:100])}",
                    )
                    return

                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime(f"Received authentification infos: {infos}")

                auth_code = infos["auth_code"]

                if auth_code == Socket.STREAMER.value:
                    try:
                        self.__auth_streamer(client, infos)
                    except Exception:
                        raise
                elif auth_code == Socket.TERMINAL.value:
                    self.__auth_terminal(client, infos)
                else:
                    self.__invalid_auth(
                        client, f"Invalid authentification code [{auth_code}]"
                    )
                break

        # If we exit the loop without breaking, we've exceeded max attempts
        if attempt >= max_attempts:
            self.__invalid_auth(
                client,
                f"Authentication failed: exceeded maximum attempts ({max_attempts}) without receiving valid message",
            )

    def __auth_streamer(self, client, infos):
        """
        Authenticate tick streamer using environment variable token

        Expected message format:
            {
                "auth_code": 1,
                "symbol": Currency pair symbol,
                "digits": Number of digits,
                "streamer_token": Streamer authentication token
            }

        Successful authentication response:
            {
                "auth_status": 0
            }
        """
        # Get token from environment
        expected_token = os.getenv("STREAMER_AUTH_TOKEN")
        if not expected_token:
            self.__invalid_auth(client, "Streamer authentication not configured")
            return

        # Validate required fields
        required_fields = {"symbol", "digits", "streamer_token"}
        if not required_fields.issubset(infos.keys()):
            self.__invalid_auth(
                client,
                "Invalid message format. Expected symbol, digits, and streamer_token",
            )
            return

        # Validate token
        provided_token = infos.get("streamer_token")
        if provided_token != expected_token:
            self.__invalid_auth(client, "Authentication failed")
            return

        # Authentication successful - proceed with streamer setup
        if len(infos) >= 3:
            data = {"auth_status": Socket.SUCCESSFUL_AUTH.value}
            try:
                client.send(bytes(json.dumps(data) + "\n", "utf-8"))
            except Exception:
                raise

            pair = CurrencyPair(infos["symbol"], infos["digits"])
            self.__all_currency_pairs[infos["symbol"]] = pair

            # Create MT5PriceConnector instead of PriceDataProvider
            from connectors.mt5_price_connector import MT5PriceConnector
            from connectors.base import ConnectorConfig
            from connectors.registry import ConnectorRegistry

            connector_config = ConnectorConfig(
                source="mt5",
                symbol=infos["symbol"],
                extra_config={"digits": infos["digits"]},
            )
            price_connector = MT5PriceConnector(
                currency_pair=pair,
                config=connector_config,
            )

            # Connect the connector
            price_connector.connect()

            # Store connector in unified connector list
            if not hasattr(self, "_connectors"):
                self._connectors = []
            self._connectors.append(price_connector)

            # Register connector with registry (replacing provider_registry)
            if not hasattr(self, "_connector_registry"):
                self._connector_registry = ConnectorRegistry()
            connector_name = f"price_{infos['symbol']}"
            self._connector_registry.register_connector(connector_name, price_connector)

            # Sync catalog with newly registered connectors
            try:
                self.__feature_catalog.sync_with_connector_registry(
                    self._connector_registry
                )
                if self.__verbose:
                    with self.__console_lock:
                        feature_count = len(
                            self._connector_registry.discover_features()
                        )
                        print_with_datetime(
                            f"Registered connector for {infos['symbol']}. "
                            f"Total features discovered: {feature_count}"
                        )
            except Exception as e:
                with self.__console_lock:
                    print_with_datetime(f"Warning: Failed to sync feature catalog: {e}")

            streamer = MT5TickStreamer(
                client,
                pair,
                self.__stop_char,
                self.__verbose,
                self.__console_lock,
                self.__db,
            )

            threading.Thread(target=streamer.receive_tick).start()
            self.__streamers.append(streamer)
        else:
            self.__invalid_auth(client, "Invalid message format.")

    def __auth_terminal(self, client, infos):
        """
        Manage the authentification of a mt5 trading terminal
        Create a new MT5Terminal and attach it to an Account.

        Expected message format:
            {
                "auth_code": 2,
                "login": Account login,
                "auth_token": Account auth token
            }

        Successfull authentification response:
            {
                "auth_status": 0,
                "terminal_id": Current terminal id
            }
        """
        from infrastructure.db_integration import (
            get_account_auth_token,
            get_account_from_db,
        )

        if (
            len(infos) >= 2
        ):  # Allow for additional fields (account_type, broker_name, etc.)
            login = infos.get("login")
            provided_token = infos.get("auth_token")

            # Validate login and token before creating terminal
            if login is None:
                self.__invalid_auth(
                    client, "Invalid message format. Missing account login"
                )
                return

            # First check if account exists in database (must be pre-registered)
            account_data = get_account_from_db(login)
            if not account_data:
                self.__invalid_auth(
                    client,
                    "Account not registered. Please register account via API first.",
                )
                return

            # Then validate token
            expected_token = get_account_auth_token(login)
            if (
                not expected_token
                or not provided_token
                or expected_token != provided_token
            ):
                self.__invalid_auth(client, "Authentication failed")
                return

            terminal = MT5Terminal(client)

            data = {
                "auth_status": Socket.SUCCESSFUL_AUTH.value,
                "terminal_id": terminal.id,
            }

            client.send(bytes(json.dumps(data) + "\n", "utf-8"))

            # Create broker adapter from terminal
            from trading.brokers.mt5_adapter import MT5BrokerAdapter

            broker_adapter = MT5BrokerAdapter.from_terminal(terminal)

            # Check if account already exists
            account_exists = False
            for account in self.__accounts:
                if account.login == infos["login"]:
                    account.set_broker_adapter(broker_adapter)
                    account_exists = True
                    # Update account in database
                    self._persist_account_to_db(account, terminal, client, infos)
                    break

            if not account_exists:
                account = Account(infos["login"], broker_adapter=broker_adapter)
                self.__accounts.append(account)
                # Persist account to database
                self._persist_account_to_db(account, terminal, client, infos)

            if infos["login"] not in self.__environments:

                # Create environment with all registered connectors
                env = LiveTradingEnv(
                    account=account, connectors=self._connectors, window_size=50
                )
                self.__environments[infos["login"]] = env

                if self.__verbose:
                    with self.__console_lock:
                        print_with_datetime(
                            f"Created trading environment for account {infos['login']}"
                        )

        else:
            self.__invalid_auth(client, "Invalid message format. Missing account login")

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

    def __invalid_auth(self, client, msg):
        """
        When the socket failed the authentification

        Failed authentification response:
            {
                "auth_status": -1
                "message": Error message provided
            }
        """
        data = {"auth_status": Socket.FAILED_AUTH.value, "message": msg}
        client.send(bytes(json.dumps(data) + "\n", "utf-8"))

        with self.__console_lock:
            print_with_datetime(
                f"Error from {client.getpeername()}: {msg} ." f"Closing connection."
            )
        client.close()

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
        if hasattr(self, "_Server__socket") and self.__socket:
            self.__socket.close()
