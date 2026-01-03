# User Guide

## Getting Started

### First Experiment Creation

1. **Access the Dashboard**
   - Open `http://localhost:3000` in your browser
   - You should see the Experiment Builder page

2. **Select Features**
   - Browse available features in the Feature Catalog
   - Select features you want to use for training
   - Common features:
     - Price features: `price_bid`, `price_ask`, `price_mid`
     - Technical indicators: `rsi_14`, `macd_signal`, `bollinger_upper`

3. **Configure Experiment**
   - Enter experiment name and description
   - Select currency pairs (e.g., EURUSD, GBPUSD)
   - Choose training mode: Live or Historical

4. **Set Hyperparameters**
   - Manual: Enter hyperparameters directly
   - Optuna: Let the system find optimal values automatically

5. **Start Training**
   - Click "Start Experiment"
   - Monitor progress in the Training Monitor page

## Feature Selection Guide

### Price Features
- **price_bid**: Current bid price
- **price_ask**: Current ask price
- **price_mid**: Mid price (bid + ask) / 2
- **spread**: Ask - Bid

### Technical Indicators
- **RSI (Relative Strength Index)**: Momentum indicator (0-100)
- **MACD**: Trend-following momentum indicator
- **Bollinger Bands**: Volatility indicator
- **ATR (Average True Range)**: Volatility measure
- **EMA (Exponential Moving Average)**: Trend indicator

### Selecting Features
- Start with 3-5 features for initial experiments
- Add more features gradually to see impact
- Use feature importance from Optuna to guide selection

## Hyperparameter Tuning

### Manual Configuration

Common hyperparameters:
- **learning_rate**: 0.0001 to 0.01 (typically 0.001)
- **gamma**: 0.9 to 0.99 (discount factor)
- **batch_size**: 32, 64, or 128
- **hidden_layers**: List of layer sizes, e.g., [128, 64]

### Optuna Automated Search

1. **Create Base Experiment**
   - Set up experiment with desired features
   - Use default hyperparameters as starting point

2. **Start Optuna Search**
   - Go to Hyperparameter Search page
   - Select metric to optimize (Sharpe ratio, win rate, etc.)
   - Set number of trials (50-100 recommended)
   - Click "Start Search"

3. **Monitor Progress**
   - Watch trial progress in real-time
   - View parameter importance charts
   - See best parameters as they're found

4. **Apply Best Parameters**
   - Once search completes, review best parameters
   - Click "Apply to Experiment" to update hyperparameters
   - Start training with optimized parameters

## Model Promotion Workflow

### Training → Paper Trading → Live Trading

1. **Training Phase**
   - Model trains on live or historical data
   - Monitor training metrics (loss, reward)
   - Wait for training to complete

2. **Paper Trading Validation**
   - After training, promote to paper trading
   - Model trades on demo account
   - Must meet validation criteria:
     - Minimum 100 trades
     - Win rate > 50%
     - Positive Sharpe ratio
     - Max drawdown < 15%

3. **Live Trading**
   - Once paper trading validates, promote to live
   - Model trades on real account
   - Monitor performance closely
   - Use kill switch if needed

## Performance Monitoring

### Portfolio Performance Page
- View aggregate metrics across all models
- See equity curve chart
- Compare performance across time periods

### Model Performance Page
- Individual model metrics
- Trade history table
- Win/loss distribution
- Drawdown visualization

### Key Metrics
- **Win Rate**: Percentage of profitable trades
- **Sharpe Ratio**: Risk-adjusted return (target: > 1.5)
- **Max Drawdown**: Largest peak-to-trough decline
- **Profit Factor**: Gross profit / Gross loss

## Troubleshooting

### Experiment Won't Start
- Check that all selected features are available
- Verify currency pairs are valid
- Ensure hyperparameters are complete

### Training Stuck
- Check Training Monitor for error messages
- Verify MT5 connection is active
- Check kill switch status

### Poor Performance
- Try different feature combinations
- Adjust hyperparameters
- Use Optuna to find better parameters
- Check for overfitting (high training performance, low validation)

### Kill Switch Activated
- Check audit log for trigger reason
- Review circuit breaker status
- Reset kill switch only after addressing issue
- Verify account balance and positions

## Best Practices

1. **Start Small**: Begin with simple experiments (few features, one currency pair)
2. **Validate First**: Always use paper trading before live
3. **Monitor Closely**: Watch performance metrics regularly
4. **Use Optuna**: Let automated search find optimal parameters
5. **Document Experiments**: Use descriptive names and notes
6. **Set Limits**: Use circuit breakers and kill switch appropriately
