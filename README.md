# The Alchemist

A comprehensive AI-powered trading system that integrates with MetaTrader 5 (MT5). The Alchemist collects real-time market data, trains a Deep Reinforcement Learning agent on live ticks, and (optionally) executes trades autonomously.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Running the System](#running-the-system)
7. [MT5 Setup](#mt5-setup)
8. [AI Training & Trading](#ai-training--trading)
9. [Monitoring & Logs](#monitoring--logs)
10. [Backup & Recovery](#backup--recovery)
11. [Project Structure](#project-structure)
12. [Troubleshooting](#troubleshooting)
13. [License](#license)

---

## Overview

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Tick Streaming** | Real-time bid/ask collection from MT5 via socket |
| **Database Storage** | Tick history and economic data |
| **AI Agent** | DQN with LSTM for sequential decision making |
| **Live Training** | Train on real-time data without historical backfill |
| **Risk Management** | Position sizing, stop-loss, take-profit, drawdown limits |
| **Trading Execution** | Send/close orders through MT5 terminal connection |

### Data Flow

```
MT5 Expert Advisors
        │
        ▼
┌───────────────────┐
│  Python Server    │
│  ┌─────────────┐  │
│  │ Tick        │  │◄─── mt5_tick_streamer.mq5
│  │ Streamer    │  │
│  └──────┬──────┘  │
│         ▼         │
│  ┌─────────────┐  │
│  │ Price       │  │
│  │ Provider    │  │
│  └──────┬──────┘  │
│         ▼         │
│  ┌─────────────┐  │
│  │ Live        │  │
│  │ Environment │  │
│  └──────┬──────┘  │
│         ▼         │
│  ┌─────────────┐  │
│  │ DQN Agent   │  │
│  │ (Training)  │  │
│  └──────┬──────┘  │
│         ▼         │
│  ┌─────────────┐  │
│  │ Trading     │  │───► mt5_trading_operation.mq5
│  │ Controller  │  │
│  └─────────────┘  │
└───────────────────┘
        │
        ▼
   MariaDB (ticks, calendar)
```

---

## Architecture

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `server.py` | `src/mt5-python_server/src/` | Main server; handles socket connections |
| `ai_trading_integration.py` | `src/mt5-python_server/src/` | Wires AI agent to server lifecycle |
| `dqn_agent.py` | `src/mt5-python_server/src/agents/` | Double DQN with LSTM |
| `live_env.py` | `src/mt5-python_server/src/environments/` | Gym-style environment for live data |
| `live_trainer.py` | `src/mt5-python_server/src/training/` | Continuous online training loop |
| `trading_controller.py` | `src/mt5-python_server/src/` | Executes trades via MT5 terminal |
| `mt5_tick_streamer.mq5` | `src/mql5_code/EAs/` | EA that streams ticks to server |
| `mt5_trading_operation.mq5` | `src/mql5_code/EAs/` | EA that receives order commands |

---

## Requirements

- **Python 3.11+**
- **Docker & Docker Compose** (for MariaDB)
- **MetaTrader 5** with demo or live account
- **Windows** (MT5 only runs on Windows; server can run in WSL/Docker)


## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/maxnorm/Alchemist-Trading-Server.git
```

### 2. Create Environment File

Create `.env` in the project root:

```env
# Server
SERVER_IP=0.0.0.0
SERVER_PORT=8080

# Database
DB_HOST=mariadb
DB_PORT=3306
DB_NAME=db_forex
DB_USER=forex_user
DB_PASSWORD=forex_password

# MyFxBook (optional, for economic calendar)
MYFXBOOK_EMAIL=your_email@example.com
MYFXBOOK_PASSWORD=your_password
URL_MYFXBOOK=https://www.myfxbook.com/

# AI Configuration
AI_LIVE_TRAINING_ENABLED=true
AI_AUTO_START=true
AI_TRADING_ENABLED=false
AI_DECISION_INTERVAL=60
AI_EPISODE_DURATION_HOURS=24
```

### 3. Start Database

```bash
docker compose up -d mariadb
```

Wait for healthy status:

```bash
docker compose ps
# mariadb should show "healthy"
```

### 4. Start Server

**Option A: Docker (recommended for production)**

```bash
docker compose up -d --build server
docker logs -f server
```

**Option B: Local Python (for development)**

```bash
cd src/mt5-python_server
pip install -r requirements.txt
python src/app.py -v
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_IP` | `0.0.0.0` | IP to bind server socket |
| `SERVER_PORT` | `1234` | Port for MT5 EA connections |
| `DB_HOST` | `mariadb` | Database hostname |
| `DB_PORT` | `3306` | Database port |
| `DB_NAME` | `db_forex` | Database name |
| `DB_USER` | `forex_user` | Database username |
| `DB_PASSWORD` | `forex_password` | Database password |
| `AI_LIVE_TRAINING_ENABLED` | `true` | Enable live training |
| `AI_AUTO_START` | `true` | Auto-start training on account connect |
| `AI_TRADING_ENABLED` | `false` | Enable real trade execution |
| `AI_DECISION_INTERVAL` | `60` | Seconds between agent decisions |
| `AI_EPISODE_DURATION_HOURS` | `24` | Hours per training episode |
| `AI_MODEL_PATH` | *(empty)* | Path to pre-trained model (optional) |

### Safety Defaults

The system starts in **safe mode**:

- `AI_TRADING_ENABLED=false` - No real trades executed
- Agent trains on simulated mark-to-market PnL
- Risk manager enforces position limits even when enabled

---

## Running the System

### Quick Start (3 Steps)

1. **Start infrastructure**:
   ```bash
   docker compose up -d
   ```

2. **Verify server is running**:
   ```bash
   docker logs server
   # Look for: "Server socket bind to 0.0.0.0:8080"
   ```

3. **Connect MT5** (see next section)

---

## MT5 Setup

### 1. Install Expert Advisors

Copy EAs to your MT5 installation:

```
src/mql5_code/EAs/mt5_tick_streamer.mq5    → <MT5>/MQL5/Experts/
src/mql5_code/EAs/mt5_trading_operation.mq5 → <MT5>/MQL5/Experts/
src/mql5_code/Include/JAson.mqh            → <MT5>/MQL5/Include/
src/mql5_code/Include/socket_utils.mqh     → <MT5>/MQL5/Include/
```

### 2. Compile EAs

In MT5 MetaEditor:

1. Open each `.mq5` file
2. Press F7 to compile
3. Verify no errors

### 3. Configure MT5

1. Go to **Tools → Options → Expert Advisors**
2. Check "Allow algorithmic trading"
3. Check "Allow DLL imports" (if needed)

### 4. Attach EAs to Chart

1. Open a chart (e.g., EURUSD M1)
2. Drag `mt5_tick_streamer` onto the chart
   - Set `ip` = `127.0.0.1` (or Docker host IP)
   - Set `port` = `1234`
3. Drag `mt5_trading_operation` onto the **same chart**
   - Same IP/port settings
4. Enable **Algo Trading** in MT5 toolbar (green button)

### 5. Verify Connection

Server logs should show:

```
<datetime> | Connected to ('127.0.0.1', xxxxx)
<datetime> | Received authentification infos: {'auth_code': 1, 'symbol': 'EURUSD', 'digits': 5}
<datetime> | Connected to ('127.0.0.1', yyyyy)
<datetime> | Received authentification infos: {'auth_code': 2, 'login': 12345678}
<datetime> | Created trading environment for account 12345678
<datetime> | AI live training started for account 12345678
```

---

## AI Training & Trading

### Training Phases

| Phase | Steps | What Happens |
|-------|-------|--------------|
| **Data Collection** | 0-100 | Agent observes, no training yet |
| **Active Learning** | 100+ | Agent trains on experiences, epsilon decays |
| **Continuous** | Ongoing | Checkpoints saved every 1000 steps |

### Console Output

```
=== Starting Live Training ===
Training: ENABLED
Trading: DISABLED
Decision Interval: 60s
Episode Duration: 24 hours
Account: 12345678
========================================

[Step 100] Action: 1, Reward: 0.0500, Balance: 10000.00, 
          Profit: 23.45 (0.23%), Experiences: 100, Loss: 0.0123,
          Epsilon: 0.9500, Mode: SIM
```

### Enabling Live Trading

**Only after sufficient training (1000+ steps) on a paper account:**

1. Edit `.env`:
   ```env
   AI_TRADING_ENABLED=true
   ```

2. Restart server:
   ```bash
   docker compose restart server
   ```

Or dynamically (without restart):

```python
# Access via Python console
server._Server__ai_integration.enable_trading()
```

**Warning banner will appear:**

```
⚠️  LIVE TRADING ENABLED - Real money at risk!
```

### Model Checkpoints

Saved to: `models/account_<login>/`

```
models/account_12345678/
├── scalers/
│   └── feature_engineer.pkl
├── live_checkpoint_step1000/
│   ├── q_network.h5
│   ├── target_network.h5
│   ├── agent_params.json
│   └── metrics.json
└── live_final_step5000/
    └── ...
```

### Loading a Pre-trained Model

Set in `.env`:

```env
AI_MODEL_PATH=models/account_12345678/live_checkpoint_step5000
```

---

## Monitoring & Logs

### Server Logs

```bash
# Docker
docker logs -f server

# Local
# Logs print to console with timestamps
```

### Key Metrics to Watch

| Metric | Meaning | Target |
|--------|---------|--------|
| `Reward` | Per-step risk-adjusted reward | Positive trend |
| `Loss` | DQN training loss | Decreasing |
| `Epsilon` | Exploration rate | Decaying to 0.01 |
| `Experiences` | Replay buffer size | Growing to 10000 |
| `Balance` | Account balance (real or simulated) | Stable/growing |
| `Mode` | SIM or TRADING | SIM until ready |

### Episode Metrics

At episode end (default: 24 hours):

```
=== Episode 1 Complete ===
Duration: 24:00:00
Total Reward: 12.34
Profit: 234.56 (2.35%)
Average Loss: 0.0089
Total Steps: 1440
========================================
```

---

## Backup & Recovery

### Database Backup

```bash
# Manual backup
docker compose run --rm backup

# Backups stored in Docker volume: backup_data
```

### Model Backup

```bash
# Copy models directory
cp -r models/ backups/models_$(date +%Y%m%d)/
```

### Restore

```bash
# Restore models
cp -r backups/models_20250101/ models/

# Restore database
docker exec -i mariadb mysql -u root -proot db_forex < backup.sql
```

---

## Project Structure

```
1.1/
├── .env                          # Environment configuration
├── docker-compose.yml            # Docker services
├── Dockerfile                    # Server container
├── README.md                     # This file
│
├── database/
│   ├── scripts/                  # SQL init scripts
│   ├── backup.py                 # Backup utility
│   └── mariadb.cnf               # Database config
│
├── models/                       # Trained models (gitignored)
│   └── account_<login>/
│       ├── scalers/
│       └── live_checkpoint_stepN/
│
├── src/
│   ├── mql5_code/
│   │   ├── EAs/
│   │   │   ├── mt5_tick_streamer.mq5
│   │   │   └── mt5_trading_operation.mq5
│   │   └── Include/
│   │       ├── JAson.mqh
│   │       └── socket_utils.mqh
│   │
│   └── mt5-python_server/
│       ├── requirements.txt
│       └── src/
│           ├── app.py                    # Entry point
│           ├── server.py                 # Main server
│           ├── database.py               # DB operations
│           ├── ai_trading_integration.py # AI wiring
│           ├── trading_controller.py     # Order execution
│           │
│           ├── agents/
│           │   ├── dqn_agent.py          # Double DQN
│           │   └── rl_trading_agent.py   # Simple Q-learning
│           │
│           ├── environments/
│           │   ├── base_trading_env.py
│           │   └── live_env.py           # Live Gym env
│           │
│           ├── training/
│           │   ├── live_trainer.py       # Online training
│           │   └── train_agent.py        # Offline training
│           │
│           ├── data_providers/
│           │   ├── base_provider.py
│           │   └── price_provider.py
│           │
│           ├── mt5_connection/
│           │   ├── conn.py
│           │   ├── terminal.py
│           │   └── tick_streamer.py
│           │
│           ├── models/
│           │   ├── account.py
│           │   ├── currency_pair.py
│           │   └── trade.py
│           │
│           ├── utils/
│           │   ├── feature_engineering.py
│           │   ├── performance_metrics.py
│           │   ├── risk_management.py
│           │   ├── technical_indicators.py
│           │   ├── transaction_costs.py
│           │   └── time_utils.py
│           │
│           └── web_scraper/
│               ├── web_scraper_myfxbook.py
│               └── web_scraper_forexlive.py
```

---

## Troubleshooting

### Server won't start

```
Error connecting to MariaDB Platform
```

**Solution**: Wait for database to be healthy:

```bash
docker compose ps  # Check mariadb status
docker compose logs mariadb  # Check for errors
```

### MT5 EA won't connect

```
Socket connection failed
```

**Solutions**:

1. Check firewall allows port 8080
2. Verify server is running on correct IP/port
3. Check EA input settings match `.env`

### "Waiting for data..." forever

**Cause**: Not enough ticks received yet.

**Solutions**:

1. Ensure MT5 market is open
2. Verify tick streamer EA is attached and running
3. Check server logs for tick reception

### Agent not training

```
Experiences: 50, Loss: 0.0000
```

**Cause**: Need 100+ experiences before training starts.

**Solution**: Wait for more ticks (at 60s interval = ~2 hours for 100 steps).

### Model load error

```
Error loading model: ...
```

**Solutions**:

1. Check `AI_MODEL_PATH` is correct
2. Verify model files exist and aren't corrupted
3. Clear path to train fresh

### High memory usage

**Cause**: Replay buffer grows to 10000 experiences.

**Solution**: Reduce `memory_size` in agent config or increase system RAM.

---

## Recommended Timeline

| Week | Goal | Settings |
|------|------|----------|
| 1 | Training only, monitor | `AI_TRADING_ENABLED=false` |
| 2 | Enable on paper account | `AI_TRADING_ENABLED=true` (demo) |
| 3 | Evaluate metrics | Check Sharpe, drawdown |
| 4+ | Gradual live (if profitable) | Small position sizes |

---

## License

**Proprietary software of Alchemist Capital**

Unauthorized use or distribution is prohibited.

© 2025, Alchemist Capital - All rights reserved
