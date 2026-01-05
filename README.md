![The Alchemist](assets/gh-social-card.png)

# AI Forex Experimentation & Trading Platform

The Alchemist is an **AI Forex Experimentation & Trading Platform** that enables iterative development of profitable DRL (Deep Reinforcement Learning) trading models. The platform provides a complete workflow from:

```
data collection → feature engineering → model training → backtesting → paper trading → live deployment
```

## Platform Overview

The Alchemist provides:

- **Extensible Data Sources**: Auto-discovery system for data providers with feature catalog
- **Experiment Builder**: Create and configure experiments through the dashboard UI
- **Dual Training Modes**: Live training (real-time data) or historical backtesting
- **Hyperparameter Tuning**: Manual configuration or automated Optuna search
- **Model Lifecycle**: Clear progression from Training → Paper Trading → Live Trading
- **Safety First**: Kill switch, circuit breakers, and order management built-in
- **Performance Tracking**: Real-time metrics, equity curves, and trade history
- **React Dashboard**: Complete experimentation UI for managing experiments

## Architecture

```
┌─────────────────┐
│  React Dashboard│ (Port 3000)
└────────┬────────┘
         │
┌────────▼────────┐
│  FastAPI Service│ (Port 8000)
└────────┬────────┘
         │
┌────────▼────────┐
│ Trading Server  │ (Port 1234)
└────────┬────────┘
         │
    ┌────┴────┐
    │   MT5   │
    └─────────┘
```

## Core Components

1. **Data Collection & Features**
   - Real-time tick data from MT5
   - Technical indicators (RSI, MACD, Bollinger Bands, etc.)
   - Auto-discovery of features from registered providers
   - Feature catalog with metadata

2. **Experiment Management**
   - Create experiments with feature selection
   - Configure hyperparameters manually or via Optuna
   - Track experiments with MLflow integration
   - Model registry with promotion workflow

3. **Trading Operations**
   - Direct connection to MT5 Expert Advisors
   - Order management with idempotency
   - Position reconciliation
   - Real-time trade execution

4. **Safety Infrastructure** ✅
   - Kill Switch: Multiple trigger mechanisms (file, env, network, signal, API)
   - Circuit Breaker: Automatic halt on excessive losses
   - Order Management System: Complete order lifecycle tracking

5. **Performance Tracking** ✅
   - Trade logging and P&L calculation
   - Equity curve tracking
   - Performance metrics (Sharpe ratio, win rate, drawdown, etc.)
   - Portfolio-level aggregation

6. **MLOps** ✅
   - MLflow experiment tracking
   - Model versioning and promotion
   - Paper trading validation
   - Model lifecycle management

## Requirements
- Docker and Docker Compose
- Python 3.11
- MetaTrader 5 platform with a valid paper or live account

## Quick Start

1. **Create a `.env` file** in the project root with the following variables:
   ```env
   SERVER_IP=0.0.0.0
   SERVER_PORT=1234
   DB_HOST=mariadb
   DB_PORT=3306
   DB_NAME=db_forex
   DB_USER=forex_user
   DB_PASSWORD=forex_password
   MYFXBOOK_EMAIL=your_email@example.com
   MYFXBOOK_PASSWORD=your_password
   URL_MYFXBOOK=https://www.myfxbook.com/
   ```

2. **Run database migrations** (if not already done):
   ```bash
   # Option 1: Use migration runner (recommended)
   python scripts/run-migrations.py
   
   # Option 2: Run scripts manually
   mysql -u root -p db_forex < src/database/scripts/01_create.sql
   mysql -u root -p db_forex < src/database/scripts/02_procedures.sql
   mysql -u root -p db_forex < src/database/scripts/06_safety_infrastructure.sql
   ```

3. **Start the Docker environment**:
   ```bash
   docker compose up -d --build
   ```

4. **Verify the server is running**:
   ```bash
   docker logs server
   ```
   You should see: `Server socket bind to 0.0.0.0:1234`

## MT5 Platform Configuration

1. **Install MetaTrader 5** from the [official website](https://www.metatrader5.com/en/download)

2. **Find your Docker host IP address**:
   - On Windows/Mac: Use `localhost` or `127.0.0.1` if running Docker Desktop
   - On Linux: Use your machine's IP address or `localhost`
   - If using Docker on a remote server, use that server's IP address

3. **Configure Expert Advisors**:
   - Navigate to: Tools -> Options -> Expert Advisors
   - Enable "Allow WebRequest for listed URL"
   - Add your endpoint: `http://<your-ip>:1234` (if needed for web requests)

4. **Load the Expert Advisors**:
   - Copy the EAs from `src/mql5_code/EAs/` to your MT5 `Experts` folder
   - In the EA inputs, set:
     - `ip`: Your Docker host IP (e.g., `localhost` or your machine's IP)
     - `port`: `1234` (must match SERVER_PORT in .env)

5. **Attach EAs to charts**:
   - `mt5_tick_streamer.mq5`: Attach to any chart for the symbol you want to stream
   - `mt5_trading_operation.mq5`: Attach to enable trading operations


## Documentation

- **[API Reference](docs/API_REFERENCE.md)** - Complete API documentation with examples
- **[User Guide](docs/USER_GUIDE.md)** - Getting started and using the platform
- **[Developer Guide](docs/DEVELOPER_GUIDE.md)** - Adding data sources and extending features
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Setup, configuration, and troubleshooting

## Testing

### Running Tests

```bash
# All tests
pytest tests/

# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# API tests
pytest tests/api/

# With coverage
pytest tests/ --cov=src/mt5-python_server/src --cov-report=html
```

### Test Coverage

- Unit tests: Core components and utilities
- Integration tests: Component interactions and workflows
- API tests: All REST endpoints and WebSocket channels
- E2E tests: Complete user workflows
- Performance tests: Benchmarks and optimization validation

## Quick Start

1. **Clone and Configure**
   ```bash
   git clone <repository-url>
   cd alchemist-platform
   cp .env.example .env
   # Edit .env with your settings
   ```

2. **Start Services**
   ```bash
   docker compose up -d
   ```

3. **Access Dashboard**
   - Open http://localhost:3000
   - Create your first experiment!

See [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) for detailed setup instructions.

## License

This project is licensed under the **MIT License**.

See the [LICENSE](LICENSE) file for the full license text.

© 2026, Alchemist Capital

### Disclaimer

**USE AT YOUR OWN RISK** - This software is provided "as is" without warranty. Trading Forex, crypto, and any other financial instruments carries high risk and may result in loss of capital. This platform is for educational and research purposes only and does not constitute financial advice. You are solely responsible for all trading decisions and must ensure compliance with applicable laws in your jurisdiction. See the [LICENSE](LICENSE) file for the complete disclaimer.
