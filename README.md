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
│  React Dashboard│ (Port 3000, runs locally)
└────────┬────────┘
         │ HTTP/WebSocket
┌────────▼────────┐
│    Gateway     │ (Port 80, routes to backend)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────────┐
│  API  │ │  Server   │
│ :8000 │ │  :8080    │
└───────┘ └────┬──────┘
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
- **Node.js 20.19+ or 22.12+** (for dashboard development)
- MetaTrader 5 platform with a valid paper or live account

## Quick Start

1. **Create a `.env` file** in the project root with the following variables:
   ```env
   SERVER_IP=0.0.0.0
   SERVER_PORT=8080
   DB_HOST=postgres
   DB_PORT=5432
   DB_NAME=db_forex
   DB_USER=forex_user
   DB_PASSWORD=forex_password
   MYFXBOOK_EMAIL=your_email@example.com
   MYFXBOOK_PASSWORD=your_password
   URL_MYFXBOOK=https://www.myfxbook.com/
   CLERK_SECRET_KEY=your_clerk_secret_key
   CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key
   ```

2. **Seed Clerk user account for local development** (optional):
   ```bash
   # Creates a default dev account (dev@localhost / dev123)
   python scripts/seed_clerk_user.py
   
   # Or with custom credentials
   CLERK_SEED_EMAIL=admin@localhost CLERK_SEED_PASSWORD=admin123 python scripts/seed_clerk_user.py
   ```
   See [Developer Guide](docs/DEVELOPER_GUIDE.md#seeding-clerk-user-account) for more details.

3. **Run database migrations** (if not already done):
   ```bash
   # Option 1: Use migration runner (recommended)
   python scripts/run-migrations.py
   
   # Option 2: Run scripts manually
   # Run migrations using the migration script
   python scripts/run-migrations.py
   ```

4. **Start the Docker environment** (backend services only):
   ```bash
   docker compose up -d --build gateway api server postgres redis mlflow
   ```
   
   **Note:** Dashboard is no longer included in Docker Compose. Run it locally via `npm run dev` (see step 3 above).

5. **Verify the server is running**:
   ```bash
   docker logs server
   ```
   You should see: `Server socket bind to 0.0.0.0:8080`

## MT5 Platform Configuration

1. **Install MetaTrader 5** from the [official website](https://www.metatrader5.com/en/download)

2. **Find your Docker host IP address**:
   - On Windows/Mac: Use `localhost` or `127.0.0.1` if running Docker Desktop
   - On Linux: Use your machine's IP address or `localhost`
   - If using Docker on a remote server, use that server's IP address

3. **Configure Expert Advisors**:
   - Navigate to: Tools -> Options -> Expert Advisors
   - Enable "Allow WebRequest for listed URL"
   - Add your endpoint: `http://<your-ip>:8080` (if needed for web requests)

4. **Load the Expert Advisors**:
   - Copy the EAs from `src/utils/MT5-EA/EAs/` to your MT5 `Experts` folder
   
   **For Tick Streamer (mt5_tick_streamer.mq5):**
   - Set connection details (see options below)
   - Set `streamer_token`: Token from `STREAMER_AUTH_TOKEN` in your `.env` file
   - Generate token: `openssl rand -hex 32` or `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - No account registration needed
   
   **For Trading Operations (mt5_trading_operation.mq5):**
   - Set connection details (see options below)
   - Register account via API to get `auth_token`
   - Set `auth_token`: Account auth token from API
   
   **Connection Options:**
   
   **Option 1 (Direct IP - Simplest, No DNS Required):**
   - `ip`: Your server's IP address (e.g., `192.168.1.100` or your public IP)
   - `port`: `8080`
   - Works immediately, no configuration needed
   
   **Option 2 (With DNS - Production):**
   - `ip`: `mt5.yourdomain.com` (requires DNS A record setup)
   - `port`: `8080`
   - Requires DNS A record: `mt5.yourdomain.com` → Your server's public IP
   
   **Option 3 (Local Testing with /etc/hosts):**
   - Add entry to hosts file: `127.0.0.1 mt5.yourdomain.com`
   - Then use: `ip`: `mt5.yourdomain.com` and `port`: `8080`

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
pytest tests/ --cov=src/trading_server/src --cov-report=html
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

3. **Start Dashboard (Local Development)**
   - Navigate to dashboard directory: `cd src/dashboard`
   - Install dependencies: `npm install`
   - Create `.env.local` file:
     ```env
     VITE_API_URL=http://localhost/api
     VITE_WS_URL=ws://localhost/ws
     VITE_CLERK_PUBLISHABLE_KEY=your_clerk_key
     ```
   - Start development server: `npm run dev`
   - Open http://localhost:3000
   
   **Note:** Dashboard now runs locally via `npm run dev` and connects to backend services via the gateway. The gateway serves only backend services (API + Server).
   - Create your first experiment!

See [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) for detailed setup instructions.

## License

This project is licensed under the **MIT License**.

See the [LICENSE](LICENSE) file for the full license text.

© 2026, Alchemist Capital

### Disclaimer

**USE AT YOUR OWN RISK** - This software is provided "as is" without warranty. Trading Forex, crypto, and any other financial instruments carries high risk and may result in loss of capital. This platform is for educational and research purposes only and does not constitute financial advice. You are solely responsible for all trading decisions and must ensure compliance with applicable laws in your jurisdiction. See the [LICENSE](LICENSE) file for the complete disclaimer.
