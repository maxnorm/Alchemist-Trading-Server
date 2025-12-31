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
        
    def start(self):
        """Start the trading controller"""
        if self.is_running:
            print("Controller is already running")
            return
        
        self.is_running = True
        self.risk_manager.initialize(self.account)
        
        print(f"Trading Controller started (Trading: {'ENABLED' if self.trading_enabled else 'DISABLED'})")
        
        try:
            while self.is_running:
                # Get current state
                state = self.env.get_state()
                
                # Get action from agent (no exploration in live trading)
                action = self.agent.act(state, training=False)
                
                # Check risk limits
                can_trade, reason = self.risk_manager.can_trade(self.account)
                
                if not can_trade:
                    print(f"Trading blocked: {reason}")
                    action = 0  # Force hold
                
                # Execute action if trading is enabled
                if self.trading_enabled:
                    self._execute_action(action)
                else:
                    print(f"Action suggested: {action} (Trading disabled - no execution)")
                
                # Wait before next decision
                time.sleep(self.decision_interval)
        
        except KeyboardInterrupt:
            print("Trading controller stopped by user")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the trading controller"""
        self.is_running = False
        print("Trading Controller stopped")
    
    def _execute_action(self, action: int):
        """
        Execute trading action
        :param action: Action to execute (0=Hold, 1=Buy, 2=Sell, 3=Close)
        """
        has_position = len(self.account.current_trade) > 0
        
        # Get currency pair
        pair = None
        if self.env.data_providers:
            pair = self.env.data_providers[0].currency_pair
        
        if pair is None:
            print("No currency pair available")
            return
        
        try:
            if action == 1:  # Buy
                if not has_position:
                    entry_price = pair.ask
                    lot_size = self.risk_manager.calculate_position_size(
                        self.account, pair, entry_price
                    )
                    sl = self.risk_manager.calculate_stop_loss(entry_price, True)
                    tp = self.risk_manager.calculate_take_profit(entry_price, True)
                    
                    trade = self.account.send_order(OrderType.BUY, pair, lot_size, None, sl, tp)
                    if trade:
                        print(f"BUY order executed: {lot_size} lots @ {entry_price}, SL: {sl}, TP: {tp}")
            
            elif action == 2:  # Sell
                if not has_position:
                    entry_price = pair.bid
                    lot_size = self.risk_manager.calculate_position_size(
                        self.account, pair, entry_price
                    )
                    sl = self.risk_manager.calculate_stop_loss(entry_price, False)
                    tp = self.risk_manager.calculate_take_profit(entry_price, False)
                    
                    trade = self.account.send_order(OrderType.SELL, pair, lot_size, None, sl, tp)
                    if trade:
                        print(f"SELL order executed: {lot_size} lots @ {entry_price}, SL: {sl}, TP: {tp}")
            
            elif action == 3:  # Close position
                if has_position:
                    for ticket in list(self.account.current_trade.keys()):
                        self.account.close_order(ticket)
                    print("All positions closed")
        
        except Exception as e:
            print(f"Error executing action {action}: {e}")
