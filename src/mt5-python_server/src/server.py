"""
Class Server for connection to MetaTrader5
"""
import os
import threading
from typing import Optional, List

from database import Database
from web_scraper.web_scraper_myfxbook import WebScraperMyfxbook
from utils.time_utils import print_with_datetime
from codes.socket_code import Socket
from models.account import Account
from data_providers.price_provider import PriceDataProvider
from environments.live_env import LiveTradingEnv
from ai_trading_integration import AITradingIntegration
from infrastructure.socket.socket_server import SocketServer
from infrastructure.auth.authentication_handler import AuthenticationHandler
from infrastructure.connections.streamer_manager import StreamerManager
from infrastructure.connections.terminal_manager import TerminalManager
from infrastructure.collectors.economic_calendar_collector import EconomicCalendarCollector
from infrastructure.factories.environment_factory import EnvironmentFactory
from utils.logging_config import get_logger
from utils.structured_logging import CorrelationContext

class Server:
    """
    Class for the server

    The server and data are base in the GMT+3 timezone
    """


    def __init__(self, verbose=False, database=None, scraper=None):
        """
        Initialize server
        :param verbose: Enable verbose logging
        :param database: Optional database instance (creates new if not provided)
        :param scraper: Optional web scraper instance (creates new if not provided)
        """
        self.__verbose = verbose
        self.__stop_char = '\n'
        self.__console_lock = threading.Lock()
        
        # Initialize structured logger
        try:
            self.__logger = get_logger('server', 'server.log')
        except Exception:
            self.__logger = None
        
        # Initialize dependencies
        self.__db = database or Database()
        self.__myfxbook = scraper or WebScraperMyfxbook(
            email=os.getenv('MYFXBOOK_EMAIL'),
            password=os.getenv('MYFXBOOK_PASSWORD'),
            url=os.getenv('URL_MYFXBOOK')
        )
        
        # Initialize infrastructure components
        server_ip = os.getenv('SERVER_IP')
        server_port = int(os.getenv('SERVER_PORT'))
        
        self.socket_server = SocketServer(server_ip, server_port, verbose)
        self.auth_handler = AuthenticationHandler(self.__stop_char, verbose, self.__console_lock)
        self.streamer_manager = StreamerManager(
            self.__db, self.__stop_char, verbose, self.__console_lock
        )
        self.terminal_manager = TerminalManager()
        self.calendar_collector = EconomicCalendarCollector(
            self.__db, self.__myfxbook, verbose, self.__console_lock
        )
        self.env_factory = EnvironmentFactory()
        
        # Set up authentication handlers
        self.auth_handler.set_streamer_handler(self._handle_streamer_auth)
        self.auth_handler.set_terminal_handler(self._handle_terminal_auth)
        
        # Initialize AI integration
        self.__ai_integration = AITradingIntegration(self)
        self.__auto_start_ai = os.getenv('AI_AUTO_START', 'true').lower() == 'true'
        
        # Bind and start
        self.socket_server.bind()
        self.start()

    def start(self):
        """
        Start the server
        """
        self.socket_server.listen()

        if self.__verbose:
            with self.__console_lock:
                print_with_datetime("Server now listening for MT5 EA")

        # Economic calendar collector - DISABLED
        # TODO: Re-enable when new scraping methods are implemented
        # self.calendar_collector.start_scheduled_collection(17, 10)

        # Main server loop
        while True:
            result = self.socket_server.accept()
            if result is None:
                continue
            
            client_conn, client_address = result

            with self.__console_lock:
                print_with_datetime(f'Connected to {client_address}')

            # Generate correlation ID for this connection
            correlation_id = CorrelationContext.generate_correlation_id() if CorrelationContext else None
            
            if self.__logger and hasattr(self.__logger, 'log_event'):
                self.__logger.log_event(
                    event_type='client_connected',
                    message=f'Connected to {client_address}',
                    metrics={'client_address': str(client_address)},
                    correlation_id=correlation_id
                )

            # Handle authentication in separate thread with correlation ID
            threading.Thread(
                target=self._handle_connection,
                args=(client_conn, correlation_id),
                daemon=True
            ).start()
    
    def _handle_connection(self, client, correlation_id=None):
        """Handle new connection"""
        # Set correlation ID for this thread
        if correlation_id and CorrelationContext:
            CorrelationContext.set_correlation_id(correlation_id)
        
        try:
            self.auth_handler.authenticate(client)
        except Exception as e:
            if self.__logger and hasattr(self.__logger, 'log_error'):
                self.__logger.log_error(
                    event_type='connection_error',
                    error=f"Error handling connection: {e}",
                    correlation_id=correlation_id,
                    exc_info=True
                )
            if self.__verbose:
                with self.__console_lock:
                    print_with_datetime(f"Error handling connection: {e}")

    def _handle_streamer_auth(self, client, infos):
        """Handle streamer authentication"""
        success = self.streamer_manager.authenticate_streamer(client, infos)
        if not success:
            self._reject_auth(client, 'Invalid message format.')
    
    def _handle_terminal_auth(self, client, infos):
        """Handle terminal authentication"""
        correlation_id = CorrelationContext.get_correlation_id() if CorrelationContext else None
        
        account = self.terminal_manager.authenticate_terminal(
            client, infos
        )
        
        if account:
            if self.__logger and hasattr(self.__logger, 'log_event'):
                self.__logger.log_event(
                    event_type='terminal_authenticated',
                    message=f"Terminal authenticated for account {account.login}",
                    metrics={'account_login': account.login},
                    correlation_id=correlation_id
                )
            
            # Create environment if it doesn't exist
            if not self.env_factory.has_environment(account.login):
                self._create_environment_for_account(account)
            
            # Initialize AI agent and (optionally) start training/trading
            try:
                self.__ai_integration.initialize_agent_for_account(account)
                if self.__auto_start_ai:
                    self.__ai_integration.start_trading_for_account(account.login)
                    if self.__logger and hasattr(self.__logger, 'log_event'):
                        self.__logger.log_event(
                            event_type='ai_training_started',
                            message=f"AI live training started for account {account.login}",
                            metrics={'account_login': account.login},
                            correlation_id=correlation_id
                        )
                    if self.__verbose:
                        with self.__console_lock:
                            print_with_datetime(f"AI live training started for account {account.login}")
                else:
                    if self.__logger and hasattr(self.__logger, 'log_event'):
                        self.__logger.log_event(
                            event_type='ai_initialized',
                            message=f"AI initialized for account {account.login} (auto-start disabled)",
                            metrics={'account_login': account.login},
                            correlation_id=correlation_id
                        )
                    if self.__verbose:
                        with self.__console_lock:
                            print_with_datetime(f"AI initialized for account {account.login} (auto-start disabled)")
            except Exception as e:
                if self.__logger and hasattr(self.__logger, 'log_error'):
                    self.__logger.log_error(
                        event_type='ai_initialization_error',
                        error=f"Error initializing AI for account {account.login}: {e}",
                        account_login=account.login,
                        correlation_id=correlation_id,
                        exc_info=True
                    )
                with self.__console_lock:
                    print_with_datetime(f"Error initializing AI for account {account.login}: {e}")
        else:
            self._reject_auth(client, 'Invalid message format. Missing account login')
    
    def _create_environment_for_account(self, account: Account) -> LiveTradingEnv:
        """
        Create environment for account
        :param account: Account instance
        :return: Created environment
        """
        data_providers = self.streamer_manager.get_price_data_providers()
        env = self.env_factory.create_environment(
            account=account,
            data_providers=data_providers,
            window_size=50
        )
        
        correlation_id = CorrelationContext.get_correlation_id() if CorrelationContext else None
        if self.__logger and hasattr(self.__logger, 'log_event'):
            self.__logger.log_event(
                event_type='environment_created',
                message=f"Created trading environment for account {account.login}",
                metrics={'account_login': account.login},
                correlation_id=correlation_id
            )
        
        if self.__verbose:
            with self.__console_lock:
                print_with_datetime(f"Created trading environment for account {account.login}")
        
        return env
    
    def _reject_auth(self, client, msg):
        """
        Reject authentication
        :param client: Client socket
        :param msg: Error message
        """
        import json
        from codes.socket_code import Socket
        
        data = {
            'auth_status': Socket.FAILED_AUTH.value,
            'message': msg
        }
        try:
            client.send(bytes(json.dumps(data) + '\n', 'utf-8'))
        except Exception:
            pass
        
        with self.__console_lock:
            try:
                print_with_datetime(f'Error from {client.getpeername()}: {msg}. Closing connection.')
            except Exception:
                print_with_datetime(f'Error: {msg}. Closing connection.')
        try:
            client.close()
        except Exception:
            pass
    
    # Public methods for accessing server state
    def get_environment(self, account_login: int) -> Optional[LiveTradingEnv]:
        """
        Get environment for an account
        :param account_login: Account login identifier
        :return: LiveTradingEnv instance or None if not found
        """
        return self.env_factory.get_environment(account_login)
    
    def get_data_providers(self) -> List[PriceDataProvider]:
        """
        Get all price data providers
        :return: List of price data providers
        """
        return self.streamer_manager.get_price_data_providers()
    
    def get_account(self, account_login: int) -> Optional[Account]:
        """
        Get account by login
        :param account_login: Account login
        :return: Account instance or None if not found
        """
        return self.terminal_manager.get_account(account_login)
    
    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, 'socket_server') and self.socket_server:
            self.socket_server.close()
