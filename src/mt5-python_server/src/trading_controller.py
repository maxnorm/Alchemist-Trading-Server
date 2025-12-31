"""
Trading Controller
Main controller that integrates agent with environment for live trading
"""
import os
import time
from typing import Optional
from agents.dqn_agent import DQNAgent
from environments.live_env import LiveTradingEnv
from utils.risk_management import RiskManager
from models.account import Account
from models.currency_pair import CurrencyPair
from codes.order_type import OrderType
from application.services.action_executor import ActionExecutor
from utils.market_utils import check_if_market_open
from utils.logging_config import get_logger
import logging


class TradingController:
    """Controller for live AI trading"""
    
    def __init__(
        self,
        agent: DQNAgent,
        environment: LiveTradingEnv,
        account: Account,
        risk_manager: RiskManager,
        trading_enabled: bool = False
    ):
        """
        Initialize trading controller
        :param agent: Trained DQN agent
        :param environment: Live trading environment
        :param account: Trading account
        :param risk_manager: Risk manager
        :param trading_enabled: Whether to enable live trading (default False for safety)
        """
        self.agent = agent
        self.env = environment
        self.account = account
        self.risk_manager = risk_manager
        self.trading_enabled = trading_enabled
        
        self.is_running = False
        self.decision_interval = 60  # Make decision every 60 seconds
        
        # Initialize structured logger
        try:
            self.logger = get_logger('trading_controller', 'trading_controller.log')
        except Exception:
            self.logger = logging.getLogger(__name__)
        self.action_executor = ActionExecutor(self.logger)
        
    def start(self):
        """Start the trading controller"""
        if self.is_running:
            print("Controller is already running")
            return
        
        self.is_running = True
        self.risk_manager.initialize(self.account)
        
        if hasattr(self.logger, 'log_event'):
            self.logger.log_event(
                event_type='trading_controller_started',
                message=f"Trading Controller started (Trading: {'ENABLED' if self.trading_enabled else 'DISABLED'})",
                metrics={
                    'trading_enabled': self.trading_enabled,
                    'account_login': self.account.login if self.account else None
                }
            )
        print(f"Trading Controller started (Trading: {'ENABLED' if self.trading_enabled else 'DISABLED'})")
        
        try:
            while self.is_running:
                # Check if market is open before proceeding
                if not check_if_market_open():
                    if hasattr(self.logger, 'log_event'):
                        self.logger.log_event(
                            event_type='market_closed',
                            message="Market is closed - skipping action execution"
                        )
                    else:
                        self.logger.info("Market is closed - skipping action execution")
                    # Wait before checking again
                    time.sleep(self.decision_interval)
                    continue
                
                # Get current state
                state = self.env.get_state()
                
                # Get action from agent (no exploration in live trading)
                action = self.agent.act(state, training=False)
                
                # Check risk limits
                can_trade, reason = self.risk_manager.can_trade(self.account)
                
                if not can_trade:
                    if hasattr(self.logger, 'log_event'):
                        self.logger.log_event(
                            event_type='trading_blocked',
                            message=f"Trading blocked: {reason}",
                            metrics={'reason': reason},
                            level='WARNING'
                        )
                    print(f"Trading blocked: {reason}")
                    action = 0  # Force hold
                
                # Execute action if trading is enabled
                if self.trading_enabled:
                    self._execute_action(action)
                else:
                    if hasattr(self.logger, 'log_event'):
                        self.logger.log_event(
                            event_type='action_suggested',
                            message=f"Action suggested: {action} (Trading disabled - no execution)",
                            metrics={'action': action}
                        )
                    print(f"Action suggested: {action} (Trading disabled - no execution)")
                
                # Wait before next decision
                time.sleep(self.decision_interval)
        
        except KeyboardInterrupt:
            if hasattr(self.logger, 'log_event'):
                self.logger.log_event(
                    event_type='trading_controller_stopped',
                    message="Trading controller stopped by user",
                    level='WARNING'
                )
            print("Trading controller stopped by user")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the trading controller"""
        self.is_running = False
        if hasattr(self.logger, 'log_event'):
            self.logger.log_event(
                event_type='trading_controller_stopped',
                message="Trading Controller stopped"
            )
        print("Trading Controller stopped")
    
    def _execute_action(self, action: int):
        """
        Execute trading action using ActionExecutor
        :param action: Encoded action (pair_index * 4 + action_type)
                       Decoded: (pair_index, action_type) where action_type: 0=Hold, 1=Buy, 2=Sell, 3=Close
        """
        try:
            # Use ActionExecutor to execute the action
            previous_balance = self.account.balance
            self.action_executor.execute(
                action=action,
                environment=self.env,
                account=self.account,
                risk_manager=self.risk_manager,
                previous_balance=previous_balance,
                trading_enabled=self.trading_enabled
            )
        except Exception as e:
            # Decode action for error message
            try:
                pair_index, action_type = self.env.decode_action(action)
                pair = self.env.data_providers[pair_index].currency_pair if self.env.data_providers else None
                symbol = pair.symbol if pair else "UNKNOWN"
            except:
                symbol = "UNKNOWN"
                action_type = "UNKNOWN"
            
            error_msg = f"Error executing action {action} (action_type={action_type}) on {symbol}: {e}"
            print(error_msg)
            if hasattr(self.logger, 'log_error'):
                self.logger.log_error(
                    event_type='action_execution_error',
                    error=error_msg,
                    symbol=symbol,
                    account_login=self.account.login if self.account else None,
                    metrics={
                        'action': action,
                        'action_type': str(action_type)
                    },
                    exc_info=True
                )
            else:
                self.logger.error(error_msg, exc_info=True)
