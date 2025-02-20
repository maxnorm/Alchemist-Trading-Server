import numpy as np
from models.trade import Trade
from models.account import Account
from codes.order_type import OrderType

class RLTradingAgent:
    def __init__(self, account: Account, learning_rate=0.001, discount_factor=0.95, epsilon=1.0):
        self.account = account
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.995
        
        # State space: [current_price, SMA_20, SMA_50, RSI, position_active]
        self.state_size = 5
        
        # Action space: 0=Do nothing, 1=Buy, 2=Sell, 3=Close position
        self.action_size = 4
        
        # Q-table for storing state-action values
        self.q_table = {}
        
    def get_state(self, pair):
        """Convert current market data into a state representation"""
        current_price = pair.mid_price
        position_active = len(self.account.current_trade) > 0
        
        # TODO: Calculate technical indicators
        sma_20 = current_price  # Placeholder
        sma_50 = current_price  # Placeholder
        rsi = 50  # Placeholder
        
        state = (current_price, sma_20, sma_50, rsi, position_active)
        return state
        
    def discretize_state(self, state):
        """Convert continuous state values into discrete buckets"""
        price, sma_20, sma_50, rsi, pos = state
        
        # Discretize price and indicators into buckets
        price_bucket = int(price * 100) # Example discretization
        sma20_bucket = int(sma_20 * 100)
        sma50_bucket = int(sma_50 * 100)
        rsi_bucket = int(rsi / 10)
        
        return (price_bucket, sma20_bucket, sma50_bucket, rsi_bucket, pos)
        
    def choose_action(self, state):
        """Choose action using epsilon-greedy policy"""
        if np.random.rand() <= self.epsilon:
            return np.random.randint(self.action_size)
            
        state = self.discretize_state(state)
        if state not in self.q_table:
            self.q_table[state] = np.zeros(self.action_size)
            
        return np.argmax(self.q_table[state])
        
    def learn(self, state, action, reward, next_state):
        """Update Q-values using Q-learning algorithm"""
        state = self.discretize_state(state)
        next_state = self.discretize_state(next_state)
        
        if state not in self.q_table:
            self.q_table[state] = np.zeros(self.action_size)
        if next_state not in self.q_table:
            self.q_table[next_state] = np.zeros(self.action_size)
            
        # Q-learning update
        current_q = self.q_table[state][action]
        next_max_q = np.max(self.q_table[next_state])
        new_q = current_q + self.learning_rate * (reward + self.discount_factor * next_max_q - current_q)
        self.q_table[state][action] = new_q
        
        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
            
    def execute_action(self, action, pair):
        """Execute the chosen action in the market"""
        if action == 0:  # Do nothing
            return 0
            
        elif action == 1:  # Buy
            if len(self.account.current_trade) == 0:
                trade = self.account.send_order(
                    OrderType.BUY,
                    pair,
                    0.01  # Minimum lot size
                )
                return 0  # Initial reward
                
        elif action == 2:  # Sell
            if len(self.account.current_trade) == 0:
                trade = self.account.send_order(
                    OrderType.SELL,
                    pair,
                    0.01  # Minimum lot size
                )
                return 0  # Initial reward
                
        elif action == 3:  # Close position
            if len(self.account.current_trade) > 0:
                for ticket in self.account.current_trade:
                    self.account.close_order(ticket)
                return self.account.profit  # Use actual profit as reward
                
        return 0 