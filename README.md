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

### Service Stack

| Service | Type | Port | Purpose |
|---------|------|------|---------|
| **Gateway** | nginx | 80, 443, 5557, 5556 | Reverse proxy, routing |
| **API** | FastAPI | 8000 | REST API + WebSocket |
| **Trading Server** | Python | 8080 | Trading operations, broker connection |
| **PostgreSQL** | TimescaleDB | 5432 | Time-series database |
| **Redis** | Redis 7 | 6379 | Message broker, caching |
| **MLflow** | MLflow | 5000 | Experiment tracking |
| **Airflow** | Airflow 2.8 | 8081 | Data pipeline orchestration |
| **Prometheus** | Prometheus | 9090 | Metrics collection |
| **Grafana** | Grafana | 3000 | Monitoring dashboards |

## Core Components

### 1. Data Collection & Features

- **Real-time Data**: MT5 tick streaming via ZeroMQ
- **Historical Data**: Dukascopy backfill support
- **Alternative Data Sources**:
  - **FRED**: US economic indicators
  - **ECB**: European Central Bank data
  - **World Bank**: Global economic indicators
  - **NewsAPI**: News articles and sentiment
  - **RSS Feeds**: Real-time news feeds
  - **Web Scraping**: ForexLive, Myfxbook calendar
- **Technical Indicators**: RSI, MACD, Bollinger Bands, ATR, EMA, etc.
- **Feature Catalog**: Auto-discovery of features from registered providers
- **Feature Engineering**: Window-based normalization and aggregation

### 2. Experiment Management

- **Experiment Builder**: Create experiments with feature selection via dashboard
- **Hyperparameter Configuration**: Manual tuning or automated Optuna search
- **Training Modes**: Live training (real-time) or historical backtesting
- **MLflow Integration**: Experiment tracking, model versioning, and registry
- **Model Lifecycle**: Training → Paper Trading → Live Trading promotion workflow

### 3. Trading Operations

- **MT5 Integration**: Direct connection via Expert Advisors (EAs)
- **Order Management**: Idempotent order submission with state tracking
- **Position Reconciliation**: Periodic sync with MT5 positions
- **Real-time Execution**: Low-latency trade execution via ZeroMQ
- **Multi-Account Support**: Manage multiple MT5 accounts (Coming Soon)

### 4. Safety Infrastructure

- **Kill Switch**: Multiple trigger mechanisms (file, environment, network, signal, API)
- **Circuit Breaker**: Automatic halt on excessive losses, drawdown, or volatility spikes
- **Order Management System**: Complete order lifecycle tracking with idempotency
- **Pre-trade Controls**: Risk checks before order execution

### 5. Performance Tracking

- **Trade Logging**: Complete trade history with P&L calculation
- **Equity Curves**: Real-time portfolio equity tracking
- **Performance Metrics**: Sharpe ratio, win rate, drawdown, max drawdown, etc.
- **Portfolio Aggregation**: Multi-model and multi-account performance views
- **Real-time Monitoring**: WebSocket updates for live metrics

### 6. MLOps

- **MLflow Tracking**: Experiment tracking with metrics, parameters, and artifacts
- **Model Registry**: Version control and model promotion workflow
- **Paper Trading Validation**: Required validation phase before live deployment
- **Data Versioning**: DVC integration for dataset versioning

## Requirements

- **Docker** and **Docker Compose**
- **Python 3.11+**
- **Node.js 20.19+ or 22.12+** (for dashboard development)
- **MetaTrader 5** platform with a valid paper or live account


## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/maxnorm/Alchemist-AI 
cd Alchemist-AI

npm install
```

### 2. Configuration

Create a `.env` file in the project root. Minimum required variables:

```bash
cp .env.example .env
```

See `.env.example` for all available configuration options.

### 3. Initialize Environment

```bash
# Create required directories with proper permissions
./scripts/init-docker-directories.sh
```

### 4. Start Backend Services

```bash
# Start all services
npm run services:up

# Or start specific services
npm run services:up -- gateway api server postgres redis mlflow
```

### 5. Start Dashboard (Local Development)

```bash
# Install Dependencies
npm run dashboard:install

# Run Vite in dev
npm run dashboard:dev
```

The dashboard will be available at `http://localhost:3000`.

### 6. Verify Services

```bash
# Check server status
docker logs server
# Should see: "Server socket bind to 0.0.0.0:8080"

# Check API health
curl http://localhost/api/health

# Check gateway
curl http://localhost/gateway/health
```

## MT5 Platform Configuration

### 1. Install MetaTrader 5

Download from the [official website](https://www.metatrader5.com/en/download).

### 2. Find Your Server IP

- **Windows/Mac (Docker Desktop)**: Use `localhost` or `127.0.0.1`
- **Linux**: Use your machine's IP address or `localhost`
- **Remote Server**: Use the server's public IP address

### 3. Configure Expert Advisors

1. Navigate to: **Tools → Options → Expert Advisors**
2. Enable **"Allow algorithmic trading"**
3. Enable **"Allow WebRequest for listed URL"** (if needed)

### 4. Load Expert Advisors

Copy the EAs from `src/utils/MT5-EA/EAs/` to your MT5 `Experts` folder.

#### Tick Streamer (`mt5_zeromq_streamer.mq5`)

- **Purpose**: Streams real-time tick data to the platform via ZeroMQ
- **Configuration**:
  - `broker_host`: Your gateway IP (see connection options below)
  - `broker_port`: `5557`
  - `token`: Token from `STREAMER_AUTH_TOKEN` in `.env`
  - Generate token: `openssl rand -hex 32` or `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- **No account registration needed**

#### Trading Operations (`mt5_zeromq_trading.mq5`)

- **Purpose**: Enables trading operations (order execution) via ZeroMQ
- **Configuration**:
  - `order_port`: `5556` (EA binds to this port, server connects to it)
  - `auth_token`: Account auth token from API (register account via API first)

#### Connection Options

**Option 1: Direct IP (Simplest)**
- For tick streamer: `broker_host`: Your server's IP address (e.g., `192.168.1.100` or public IP), `broker_port`: `5557`
- For trading EA: `order_port`: `5556` (EA binds locally, server connects via gateway)
- Works immediately, no DNS required

**Option 2: DNS (Production)**
- For tick streamer: `broker_host`: `mt5.yourdomain.com` (requires DNS A record), `broker_port`: `5557`
- For trading EA: `order_port`: `5556`
- Requires DNS A record: `mt5.yourdomain.com` → Your server's public IP

**Option 3: Local Testing**
- Add to `/etc/hosts`: `127.0.0.1 mt5.yourdomain.com`
- For tick streamer: `broker_host`: `mt5.yourdomain.com`, `broker_port`: `5557`
- For trading EA: `order_port`: `5556`

### 5. Attach EAs to Charts

- **`mt5_zeromq_streamer.mq5`**: Attach to any chart for the symbol you want to stream
- **`mt5_zeromq_trading.mq5`**: Attach to enable trading operations

**Note**: The platform also supports legacy socket-based EAs (`mt5_tick_streamer.mq5` and `mt5_trading_operation.mq5`) which use port 8080, but the ZeroMQ-based EAs (version 2.00) are recommended for better performance and reliability.

## Documentation

| Document | Description |
|----------|-------------|
| **[API Reference](docs/API_REFERENCE.md)** | Complete API documentation with examples |
| **[User Guide](docs/USER_GUIDE.md)** | Getting started and using the platform |
| **[Developer Guide](docs/DEVELOPER_GUIDE.md)** | Adding data sources and extending features |
| **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** | Setup, configuration, and troubleshooting |
| **[Architecture Docs](docs/architecture/index.md)** | System architecture and design decisions |
| **[Data Source Guide](docs/data-source-guide/ADDING_DATA_SOURCES.md)** | Adding new data source connectors |

## Testing

### Running Tests

```bash
# All tests
pytest tests/

# By category
pytest tests/unit/          # Unit tests
pytest tests/integration/   # Integration tests
pytest tests/api/           # API tests

# With coverage
pytest tests/ --cov=src/trading_server/src --cov-report=html
```

## Development

### Project Structure

```
qpl/
├── src/
│   ├── api/              # FastAPI REST + WebSocket service
│   ├── dashboard/        # React dashboard (runs locally)
│   ├── trading_server/   # Core trading server
│   ├── database/         # Database migrations and scripts
│   ├── gateway/          # nginx configuration
│   └── monitoring/       # Prometheus & Grafana configs
├── scripts/              # Utility scripts
├── tests/                # Test suite
├── docs/                 # Documentation
└── docker-compose.yml    # Service orchestration
```

## License

This project is licensed under the **MIT License**.

See the [LICENSE](LICENSE) file for the full license text.

© 2026, Alchemist Capital

### ⚠️ Disclaimer

**USE AT YOUR OWN RISK** - This software is provided "as is" without warranty. Trading Forex, crypto, and any other financial instruments carries high risk and may result in loss of capital. This platform is for educational and research purposes only and does not constitute financial advice. You are solely responsible for all trading decisions and must ensure compliance with applicable laws in your jurisdiction. See the [LICENSE](LICENSE) file for the complete disclaimer.