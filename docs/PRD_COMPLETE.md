# Product Requirements Document (PRD)
# The Alchemist - AI Forex Experimentation & Trading Platform

**Version:** 5.0  
**Date:** January 2, 2025  
**Author:** Development Team  
**Status:** Active  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Vision & Goals](#2-vision--goals)
3. [Platform Concept](#3-platform-concept)
4. [Current State Analysis](#4-current-state-analysis)
5. [Target Architecture](#5-target-architecture)
6. [Feature Requirements](#6-feature-requirements)
7. [Data Source Plugin System](#7-data-source-plugin-system)
8. [Feature Catalog](#8-feature-catalog)
9. [Experiment Builder](#9-experiment-builder)
10. [Hyperparameter Configuration](#10-hyperparameter-configuration)
11. [Training Pipeline](#11-training-pipeline)
12. [Model Lifecycle](#12-model-lifecycle)
13. [Live Performance Tracking](#13-live-performance-tracking)
14. [MT5 Account Management](#14-mt5-account-management)
15. [Dashboard Specifications](#15-dashboard-specifications)
16. [API Specification](#16-api-specification)
17. [Database Schema](#17-database-schema)
18. [Security Requirements](#18-security-requirements)
19. [Technical Specifications](#19-technical-specifications)
20. [Development Phases](#20-development-phases)
21. [Testing Strategy](#21-testing-strategy)
22. [Risk Assessment](#22-risk-assessment)
23. [Success Metrics](#23-success-metrics)
24. [Deployment Strategy](#24-deployment-strategy)
25. [Future Roadmap](#25-future-roadmap)
26. [Appendix](#26-appendix)

---

## 1. Executive Summary

### 1.1 Project Overview

The Alchemist is an **AI Forex Experimentation Platform** that enables iterative development of profitable DRL (Deep Reinforcement Learning) trading models. The platform provides a complete workflow from **data collection → feature engineering → model training → backtesting → paper trading → live deployment**.

The dashboard serves as the **control center** for creating, training, and deploying trading agents - not just monitoring live trading.

### 1.2 Core Value Proposition

| Capability | Description |
|------------|-------------|
| **Extensible Data Sources** | Developers add new data providers in code; dashboard auto-discovers available features |
| **Experiment Builder** | Users select features and configure models through the dashboard UI |
| **Dual Training Modes** | Live training (real-time data) or historical backtesting (when data available) |
| **Hyperparameter Tuning** | Manual configuration or automated Optuna search |
| **Model Lifecycle** | Clear progression: Train → Paper Trade → Live Trading |
| **Safety First** | Kill switch, circuit breakers, and order management built-in |

### 1.3 Key Deliverables

| Track | Deliverables | Priority |
|-------|--------------|----------|
| **Data Layer** | Data source plugin system, feature catalog, auto-discovery | P0 |
| **Experiment Builder** | Feature selection UI, model configuration, training controls | P0 |
| **Hyperparameters** | Manual tuning + Optuna integration | P0 |
| **Training Pipeline** | Live training, historical backtest, MLflow tracking | P0 |
| **Safety & Risk** | Kill switch, circuit breakers, order management system | P0 |
| **Model Registry** | Version control, staging, promotion workflow | P0 |
| **Dashboard** | React SPA for experimentation and monitoring | P0 |
| **API Layer** | FastAPI REST + WebSocket service | P0 |

### 1.4 Technology Stack

| Layer | Technology | Justification |
|-------|------------|---------------|
| **Core Server** | Python 3.11+ | Existing codebase, ML ecosystem |
| **AI/ML** | PyTorch, Attention-DQN | Deep RL with market state encoding |
| **Hyperparameter Search** | Optuna | Efficient automated tuning with pruning |
| **Database** | MariaDB/TimescaleDB | Time-series optimized storage |
| **Experiment Tracking** | MLflow | Industry standard for ML experiments |
| **Data Versioning** | DVC | Dataset versioning and reproducibility |
| **API** | FastAPI | Async, WebSocket support, auto-docs |
| **Real-time** | WebSocket | Low-latency streaming |
| **Frontend** | Vite + React + TypeScript | Fast SPA, modern tooling |
| **UI Components** | shadcn/ui + Tailwind CSS | Beautiful, accessible components |
| **Charts** | Lightweight Charts (TradingView) | Industry-standard trading charts |
| **State** | Zustand + TanStack Query | Simple, performant state management |

---

## 2. Vision & Goals

### 2.1 Vision Statement

Build an **AI Forex Experimentation Platform** that enables:
- **Rapid iteration** on trading strategies through the dashboard
- **Extensible data sources** that developers can add via code
- **Automated model discovery** through hyperparameter search
- **Safe progression** from training to live trading with validation gates

### 2.2 Primary Goals

| ID | Goal | Success Criteria |
|----|------|------------------|
| G1 | **Experimentation Velocity** | Create and train new experiment in < 5 minutes via dashboard |
| G2 | **Data Extensibility** | Add new data source in < 4 hours (developer task) |
| G3 | **Feature Discovery** | All registered features auto-appear in dashboard |
| G4 | **Optimal Models** | Find best hyperparameters via Optuna search |
| G5 | **Trading Safety** | Zero uncontrolled losses; all operations auditable |
| G6 | **Model Validation** | Paper trading required before live deployment |

### 2.3 Secondary Goals

| ID | Goal | Success Criteria |
|----|------|------------------|
| G7 | ML Reproducibility | Any experiment can be reproduced from logged artifacts |
| G8 | Real-time Monitoring | View all metrics with < 1s latency |
| G9 | Multi-pair Support | Train on single or multiple currency pairs |
| G10 | Performance Analytics | Track win rate, Sharpe ratio, drawdown |

### 2.4 Scope

**In Scope (v3.2):**
- Forex trading via MT5 only
- Single and multi-pair experiments
- Manual and Optuna hyperparameter tuning
- Live training (primary) and historical backtest (when data available)
- React dashboard for experimentation & live performance tracking
- Local desktop deployment
- Multiple MT5 accounts (can run multiple MT5 terminals locally, each with different accounts)

**Out of Scope (v3.2):**
- Cryptocurrency markets (future version)
- Mobile native apps
- User authentication for dashboard/API (no login required for local deployment)
- Enterprise account management features
- Enterprise monitoring (Prometheus/Grafana)
- Multi-environment deployment (dev/staging/prod)
- Third-party integrations (Telegram, Discord)

---

## 3. Platform Concept

### 3.1 User Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     THE ALCHEMIST EXPERIMENTATION WORKFLOW                   │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ 1. SELECT   │───▶│ 2. CONFIGURE│───▶│ 3. TRAIN    │───▶│ 4. VALIDATE │  │
│  │    FEATURES │    │    MODEL    │    │             │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│        │                  │                  │                  │           │
│        ▼                  ▼                  ▼                  ▼           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ Dashboard   │    │ Manual or   │    │ Live or     │    │ Paper       │  │
│  │ shows all   │    │ Optuna      │    │ Historical  │    │ Trading     │  │
│  │ available   │    │ tuning      │    │ backtest    │    │ validation  │  │
│  │ features    │    │             │    │             │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                   │          │
│                                                                   ▼          │
│                                                            ┌─────────────┐  │
│                                                            │ 5. DEPLOY   │  │
│                                                            │    TO LIVE  │  │
│                                                            │    TRADING  │  │
│                                                            └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Platform Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCE LAYER (Code Level)                     │
│                    Developers add new data sources here                      │
│                                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │ MT5 Ticks   │ │ Economic    │ │ Sentiment   │ │  News/RSS   │  ...more   │
│  │ Provider    │ │ Calendar    │ │ Provider    │ │  Provider   │            │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘            │
│         │               │               │               │                    │
│         └───────────────┴───────────────┴───────────────┘                    │
│                                   │                                          │
│                                   ▼                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    DATA SOURCE REGISTRY (Auto-Discovery)               │  │
│  │        Scans registered providers, extracts feature metadata           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FEATURE CATALOG (Database)                         │
│                   Stores metadata for all available features                 │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ Feature Name      │ Source        │ Type    │ Description               ││
│  ├───────────────────┼───────────────┼─────────┼───────────────────────────││
│  │ price_mid         │ MT5           │ float   │ Mid price                 ││
│  │ rsi_14            │ Indicators    │ float   │ RSI with period 14        ││
│  │ macd_signal       │ Indicators    │ float   │ MACD signal line          ││
│  │ bollinger_upper   │ Indicators    │ float   │ Bollinger upper band      ││
│  │ event_impact      │ EconCalendar  │ int     │ Upcoming event impact     ││
│  │ sentiment_score   │ Sentiment     │ float   │ Market sentiment          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DASHBOARD (Experimentation UI)                        │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        EXPERIMENT BUILDER                              │  │
│  │                                                                        │  │
│  │  ┌─ FEATURE SELECTION ─────────────────────────────────────────────┐  │  │
│  │  │  ☑ price_mid        ☑ rsi_14         ☑ macd_signal             │  │  │
│  │  │  ☑ bollinger_upper  ☐ event_impact   ☐ sentiment_score         │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  ┌─ CURRENCY PAIRS ────────────────────────────────────────────────┐  │  │
│  │  │  ☑ EURUSD           ☑ GBPUSD         ☐ USDJPY                  │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  ┌─ HYPERPARAMETERS ───────────────────────────────────────────────┐  │  │
│  │  │  Mode: ○ Manual  ● Optuna Search                                │  │  │
│  │  │  Learning Rate: [0.00001] to [0.01]                             │  │  │
│  │  │  Trials: [50]   Optimize for: [Sharpe Ratio]                    │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  [Start Training]  [Start Optuna Search]                              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Key Concepts

| Concept | Description |
|---------|-------------|
| **Data Provider** | Code module that collects data (ticks, indicators, sentiment, etc.) |
| **Feature** | Individual data point extracted from a provider (e.g., `rsi_14`, `price_mid`) |
| **Feature Catalog** | Database of all available features with metadata |
| **Experiment** | Configuration of features + model + hyperparameters + training run |
| **Hyperparameter Search** | Optuna-based automatic optimization of model settings |
| **Model Registry** | Versioned storage of trained models with lifecycle stages |

---

## 4. Current State Analysis

### 4.1 What Exists

| Component | Status | Location |
|-----------|--------|----------|
| Socket server for MT5 | ✅ Complete | `src/mt5-python_server/src/server.py` |
| Tick streaming | ✅ Complete | `src/mt5-python_server/src/mt5_connection/tick_streamer.py` |
| DQN Agent (Attention) | ✅ Complete | `src/mt5-python_server/src/agents/attention_dqn_agent.py` |
| Feature engineering | ✅ Complete | `src/mt5-python_server/src/utils/feature_engineering.py` |
| Technical indicators | ✅ Complete | `src/mt5-python_server/src/utils/technical_indicators.py` |
| Live training loop | ✅ Complete | `src/mt5-python_server/src/training/live_trainer.py` |
| Base data provider | ✅ Complete | `src/mt5-python_server/src/data_providers/base_provider.py` |
| Price data provider | ✅ Complete | `src/mt5-python_server/src/data_providers/price_provider.py` |
| Database integration | ✅ Complete | `src/mt5-python_server/src/database.py` |
| Trading controller | 🔄 Started | `src/mt5-python_server/src/trading_controller.py` |
| Risk module | 🔄 Started | `src/mt5-python_server/src/risk/` |

### 4.2 What's Missing

| Component | Priority | Notes |
|-----------|----------|-------|
| Data source registry | P0 | Auto-discovery of providers |
| Feature catalog | P0 | Database + API for features |
| Experiment builder UI | P0 | Dashboard feature selection |
| Optuna integration | P0 | Hyperparameter search |
| Kill switch | P0 | Multiple trigger mechanisms |
| Circuit breakers | P0 | Auto-halt on loss/volatility |
| Order management | P0 | Idempotency, reconciliation |
| MLflow integration | P0 | Experiment tracking |
| Paper trading env | P0 | Real-time validation |
| FastAPI service | P0 | REST + WebSocket API |
| React dashboard | P0 | Experimentation UI |

### 4.3 Historical Data Strategy

**Current situation:** No historical data for backtesting.

**Strategy:**
1. **Phase 1 (Now):** Focus on live training - models learn from real-time tick data as it arrives
2. **Phase 2 (3-6 months):** Collected data enables backtesting validation
3. **Phase 3 (6+ months):** Full historical backtest capability with 6+ months of data

| Timeframe | Training Mode | Backtest Capability |
|-----------|---------------|---------------------|
| Day 1-90 | Live only | None (collecting data) |
| Day 90-180 | Live + limited backtest | 1-3 months data |
| Day 180+ | Live + full backtest | 6+ months data |

---

## 5. Target Architecture

### 5.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ MT5 Terminal│  │WebSocket    │  │MariaDB      │  │ DVC Storage         │ │
│  │ (Ticks)     │  │ (Events)    │  │ (Time-series│  │ (Data Versions)     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼────────────────┼────────────────────┼────────────┘
          │                │                │                    │
          ▼                ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCE LAYER                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     Data Provider Registry                             │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────┐   │  │
│  │  │   Price    │  │ Technical  │  │  Economic  │  │   Sentiment    │   │  │
│  │  │  Provider  │  │ Indicators │  │  Calendar  │  │   Provider     │   │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│                                      ▼                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        Feature Catalog                                 │  │
│  │            (Auto-discovered features stored in database)               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CORE SERVICES                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Experiment & Training Engine                        │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────┐   │  │
│  │  │ Experiment │  │   Optuna   │  │  Training  │  │    Live        │   │  │
│  │  │  Builder   │  │  Tuner     │  │   Loop     │  │   Trainer      │   │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         Risk Engine                                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────┐   │  │
│  │  │ Kill Switch│  │  Circuit   │  │    OMS     │  │  Position      │   │  │
│  │  │            │  │  Breaker   │  │            │  │  Manager       │   │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         MLOps Layer                                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────┐   │  │
│  │  │  MLflow    │  │   Model    │  │   Data     │  │  Experiment    │   │  │
│  │  │  Server    │  │  Registry  │  │ Versioner  │  │   Tracker      │   │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         FastAPI Server                                 │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────┐   │  │
│  │  │   REST     │  │ WebSocket  │  │   Auth     │  │   Metrics      │   │  │
│  │  │ Endpoints  │  │  Manager   │  │ Middleware │  │   Exporter     │   │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                 React Dashboard (Experimentation UI)                   │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────────┐   │  │
│  │  │ Experiment │  │  Training  │  │   Model    │  │    Live        │   │  │
│  │  │  Builder   │  │  Monitor   │  │  Registry  │  │   Trading      │   │  │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Target Directory Structure

```
1.1/
├── README.md
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── dvc.yaml
├── .dvc/
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── training.yml
│       └── deploy.yml
│
├── src/
│   ├── api/                              # FastAPI Service
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── dependencies.py
│   │       ├── routers/
│   │       │   ├── auth.py
│   │       │   ├── trading.py
│   │       │   ├── experiments.py        # Experiment management
│   │       │   ├── features.py           # Feature catalog
│   │       │   ├── hyperparameters.py    # Optuna endpoints
│   │       │   └── models.py
│   │       ├── schemas/
│   │       ├── services/
│   │       └── websocket/
│   │
│   ├── dashboard/                        # React SPA
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.js
│   │   └── src/
│   │       ├── App.tsx
│   │       ├── main.tsx
│   │       ├── components/
│   │       ├── pages/
│   │       │   ├── Dashboard.tsx
│   │       │   ├── ExperimentBuilder.tsx  # Feature selection + config
│   │       │   ├── TrainingMonitor.tsx    # Training progress
│   │       │   ├── HyperparameterSearch.tsx # Optuna UI
│   │       │   ├── ModelRegistry.tsx
│   │       │   ├── LiveTrading.tsx
│   │       │   └── Settings.tsx
│   │       ├── hooks/
│   │       ├── services/
│   │       ├── stores/
│   │       └── types/
│   │
│   └── mt5-python_server/
│   └── src/
│       ├── server.py
│       ├── trading_controller.py
│       ├── agents/
│       ├── application/
│       ├── domain/
│       ├── environments/
│       ├── infrastructure/
│       │
│       ├── data_providers/           # Data source plugins
│       │   ├── base_provider.py
│       │   ├── price_provider.py
│       │   ├── indicator_provider.py  # NEW
│       │   ├── sentiment_provider.py  # NEW (example)
│       │   ├── news_provider.py       # NEW (example)
│       │   └── registry.py            # NEW: Auto-discovery
│       │
│       ├── features/                  # NEW: Feature catalog
│       │   ├── __init__.py
│       │   ├── catalog.py             # Feature registry
│       │   ├── extractor.py           # Feature extraction
│       │   └── definitions.py         # Feature metadata
│       │
│       ├── experiments/               # NEW: Experiment management
│       │   ├── __init__.py
│       │   ├── builder.py             # Experiment configuration
│       │   ├── runner.py              # Training execution
│       │   └── hyperparameter_tuner.py # Optuna integration
│       │
│       ├── mlops/
│       │   ├── experiment_tracker.py
│       │   ├── model_promoter.py
│       │   └── data_versioner.py
│       │
│       ├── risk/
│       │   ├── kill_switch.py
│       │   ├── circuit_breaker.py
│       │   └── oms.py
│       │
│       └── utils/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── splits/
│
├── docs/
│   ├── getting-started/
│   ├── architecture/
│   ├── api-reference/
│   ├── data-source-guide/            # How to add data sources
│   ├── training-guide/
│   └── operations/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── stress/
│   └── e2e/
│
└── scripts/
    ├── setup-dev.ps1
    ├── export-data.py
    └── train-model.py
```

---

## 6. Feature Requirements

### 6.1 Safety & Risk Management (P0)

#### FR-1: Kill Switch

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | Support file-based trigger | P0 |
| FR-1.2 | Support network trigger (UDP) | P0 |
| FR-1.3 | Support API trigger | P0 |
| FR-1.4 | Support dashboard button trigger | P0 |
| FR-1.5 | Close all open positions immediately on trigger | P0 |
| FR-1.6 | Cancel all pending orders on trigger | P0 |
| FR-1.7 | Log incident with timestamp and source | P0 |
| FR-1.8 | Require manual reset after trigger | P0 |

#### FR-2: Circuit Breakers

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.1 | Halt trading when daily loss exceeds threshold | P0 |
| FR-2.2 | Halt trading when consecutive losses exceed count | P0 |
| FR-2.3 | Halt trading when drawdown exceeds threshold | P0 |
| FR-2.4 | Halt trading when volatility spikes above threshold | P0 |
| FR-2.5 | Configurable cooldown period before auto-resume | P1 |
| FR-2.6 | Log all circuit breaker activations | P0 |

#### FR-3: Order Management System (OMS)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | Assign unique order ID to every order | P0 |
| FR-3.2 | Idempotent order submission (prevent duplicates) | P0 |
| FR-3.3 | Order state machine (pending → submitted → filled/rejected) | P0 |
| FR-3.4 | Position reconciliation with MT5 every N seconds | P0 |
| FR-3.5 | Alert on position mismatch | P0 |

---

## 7. Data Source Plugin System

### 7.1 Overview

The platform allows developers to add new data sources through code. Each data provider:
1. Implements the `IDataProvider` interface
2. Registers itself with the `DataProviderRegistry`
3. Declares the features it provides
4. Features automatically appear in the dashboard for selection

### 7.2 Data Provider Interface

#### FR-4: Data Provider Protocol

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | All providers implement `IDataProvider` protocol | P0 |
| FR-4.2 | Providers must implement `get_current_data()` method | P0 |
| FR-4.3 | Providers must implement `subscribe(callback)` method | P0 |
| FR-4.4 | Providers must implement `get_features()` method | P0 |
| FR-4.5 | Providers must declare feature metadata (name, type, description) | P0 |
| FR-4.6 | Providers can implement optional `collect_historical()` method | P1 |

### 7.3 Provider Registration

#### FR-5: Data Provider Registry

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | Auto-discover registered providers on startup | P0 |
| FR-5.2 | Extract feature metadata from each provider | P0 |
| FR-5.3 | Store feature catalog in database | P0 |
| FR-5.4 | Provide health check for each provider | P0 |
| FR-5.5 | Support provider enable/disable without restart | P1 |

### 7.4 Data Provider Code Pattern

```python
# Example: How developers add a new data source
# File: src/mt5-python_server/src/data_providers/sentiment_provider.py

from data_providers.base_provider import DataProvider, Feature

class SentimentProvider(DataProvider):
    """Provider for market sentiment data"""
    
    # Declare features this provider offers
    FEATURES = [
        Feature(
            name="sentiment_bullish_pct",
            data_type=float,
            description="Percentage of bullish sentiment",
            source="sentiment"
        ),
        Feature(
            name="sentiment_bearish_pct",
            data_type=float,
            description="Percentage of bearish sentiment",
            source="sentiment"
        ),
        Feature(
            name="retail_long_pct",
            data_type=float,
            description="Retail traders long percentage",
            source="sentiment"
        ),
    ]
    
    def get_features(self) -> list[Feature]:
        return self.FEATURES
    
    def get_current_data(self) -> dict:
        # Fetch real-time sentiment data
        return {
            "sentiment_bullish_pct": 0.65,
            "sentiment_bearish_pct": 0.35,
            "retail_long_pct": 0.42,
        }
    
    def subscribe(self, callback):
        # Subscribe to sentiment updates
        self.subscribers.append(callback)
    
    def collect_historical(self, start, end) -> pd.DataFrame:
        # Optional: Collect historical data for backtesting
        pass
```

---

## 8. Feature Catalog

### 8.1 Overview

The Feature Catalog is a central database of all available features, auto-populated from registered data providers.

### 8.2 Feature Catalog Requirements

#### FR-6: Feature Catalog

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-6.1 | Store feature metadata (name, type, source, description) | P0 |
| FR-6.2 | Auto-populate from registered providers on startup | P0 |
| FR-6.3 | Provide API endpoint to list all features | P0 |
| FR-6.4 | Support filtering by source, type, or search | P0 |
| FR-6.5 | Track feature availability status (online/offline) | P0 |
| FR-6.6 | Store feature statistics (min, max, mean) when available | P1 |

### 8.3 Feature Categories

| Category | Examples | Source |
|----------|----------|--------|
| **Price** | `price_bid`, `price_ask`, `price_mid` | MT5 Provider |
| **Technical** | `rsi_14`, `macd_signal`, `bollinger_upper`, `atr_14` | Indicator Provider |
| **Economic** | `event_impact`, `event_countdown`, `high_impact_count` | Economic Calendar |
| **Sentiment** | `bullish_pct`, `retail_long_pct` | Sentiment Provider |
| **News** | `news_sentiment`, `news_volume_24h` | News Provider |

---

## 9. Experiment Builder

### 9.1 Overview

The Experiment Builder is the dashboard interface for creating and configuring new experiments.

### 9.2 Experiment Builder Requirements

#### FR-7: Experiment Configuration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-7.1 | Display all available features from catalog | P0 |
| FR-7.2 | Allow multi-select of features for training | P0 |
| FR-7.3 | Filter features by source/category | P0 |
| FR-7.4 | Select currency pairs for training | P0 |
| FR-7.5 | Support single-pair and multi-pair experiments | P0 |
| FR-7.6 | Select training mode (live or historical) | P0 |
| FR-7.7 | Configure hyperparameters (manual or Optuna) | P0 |
| FR-7.8 | Name and describe experiment | P0 |
| FR-7.9 | Save experiment configuration | P0 |
| FR-7.10 | Clone existing experiment | P1 |

### 9.3 Experiment Builder UI Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CREATE NEW EXPERIMENT                               │
│                                                                              │
│  Experiment Name: [EURUSD_DQN_RSI_MACD_v1                    ]              │
│  Description:     [Testing RSI and MACD features on EURUSD  ]              │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════════│
│                                                                              │
│  ┌─ FEATURE SELECTION ─────────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  Filter: [Search features...        ]  Source: [All Sources ▼]         ││
│  │                                                                          ││
│  │  ┌─ Price ──────────────────────────┐  ┌─ Technical ─────────────────┐  ││
│  │  │ ☑ price_mid         (MT5)        │  │ ☑ rsi_14        (Indicators) │  ││
│  │  │ ☐ price_bid         (MT5)        │  │ ☑ macd_signal   (Indicators) │  ││
│  │  │ ☐ price_ask         (MT5)        │  │ ☑ macd_hist     (Indicators) │  ││
│  │  │ ☐ spread            (MT5)        │  │ ☐ bollinger_up  (Indicators) │  ││
│  │  └──────────────────────────────────┘  │ ☐ bollinger_low (Indicators) │  ││
│  │                                        │ ☐ atr_14        (Indicators) │  ││
│  │  ┌─ Economic ───────────────────────┐  │ ☐ ema_20        (Indicators) │  ││
│  │  │ ☐ event_impact    (Calendar)     │  └─────────────────────────────┘  ││
│  │  │ ☐ hours_to_event  (Calendar)     │                                   ││
│  │  └──────────────────────────────────┘                                   ││
│  │                                                                          ││
│  │  Selected: 4 features                                                    ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ CURRENCY PAIRS ────────────────────────────────────────────────────────┐│
│  │  ☑ EURUSD    ☐ GBPUSD    ☐ USDJPY    ☐ AUDUSD    ☐ USDCAD             ││
│  │                                                                          ││
│  │  Training Mode: ○ Single pair (each pair separately)                    ││
│  │                 ● Multi-pair (agent sees all pairs)                     ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ TRAINING MODE ─────────────────────────────────────────────────────────┐│
│  │  ● Live Training (learn from real-time data)                            ││
│  │  ○ Historical Backtest (replay stored data) [No data available yet]     ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  [Continue to Hyperparameters →]                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Hyperparameter Configuration

### 10.1 Overview

The platform supports two modes for hyperparameter configuration:
1. **Manual Mode**: User sets exact values for each hyperparameter
2. **Optuna Mode**: Automated search for optimal hyperparameters

### 10.2 Hyperparameter Requirements

#### FR-8: Manual Hyperparameter Configuration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-8.1 | Set learning rate | P0 |
| FR-8.2 | Set gamma (discount factor) | P0 |
| FR-8.3 | Set batch size | P0 |
| FR-8.4 | Set hidden layer configuration | P0 |
| FR-8.5 | Set window size (lookback period) | P0 |
| FR-8.6 | Set replay buffer size | P0 |
| FR-8.7 | Set epsilon decay schedule | P0 |
| FR-8.8 | Set target network update frequency | P0 |
| FR-8.9 | Save hyperparameter preset for reuse | P1 |

#### FR-9: Optuna Hyperparameter Search

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-9.1 | Define search ranges for each hyperparameter | P0 |
| FR-9.2 | Set number of trials | P0 |
| FR-9.3 | Select optimization metric (Sharpe, win rate, P&L) | P0 |
| FR-9.4 | Enable/disable pruning (stop bad trials early) | P0 |
| FR-9.5 | Set parallel trial count (if GPU available) | P1 |
| FR-9.6 | View real-time search progress | P0 |
| FR-9.7 | View parameter importance analysis | P0 |
| FR-9.8 | Export best hyperparameters | P0 |
| FR-9.9 | Apply best hyperparameters to new experiment | P0 |

### 10.3 Hyperparameters Supported

| Parameter | Type | Manual Default | Optuna Range |
|-----------|------|----------------|--------------|
| `learning_rate` | float | 0.0001 | [0.00001, 0.01] log scale |
| `gamma` | float | 0.99 | [0.9, 0.999] |
| `batch_size` | int | 64 | [32, 64, 128, 256] |
| `hidden_layers` | list | [256, 128] | [[64,64], [128,64], [256,128], [512,256]] |
| `window_size` | int | 50 | [20, 50, 100] |
| `replay_buffer_size` | int | 100000 | [10000, 100000, 500000] |
| `epsilon_start` | float | 1.0 | Fixed |
| `epsilon_end` | float | 0.01 | [0.01, 0.1] |
| `epsilon_decay` | int | 10000 | [5000, 10000, 50000] |
| `target_update_freq` | int | 1000 | [100, 1000, 5000] |

### 10.4 Hyperparameter UI Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       HYPERPARAMETER CONFIGURATION                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  MODE:   ● Manual (set exact values)                                    ││
│  │          ○ Optuna Search (find optimal values automatically)            ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════════│
│                                                                              │
│  ┌─ MANUAL CONFIGURATION ──────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  Learning Rate:     [0.0001      ]     Gamma:           [0.99      ]    ││
│  │  Batch Size:        [64    ▼]          Window Size:     [50        ]    ││
│  │  Hidden Layers:     [256, 128    ]     Replay Buffer:   [100000    ]    ││
│  │                                                                          ││
│  │  ─── Epsilon (Exploration) ───────────────────────────────────────────  ││
│  │  Start:  [1.0  ]   End:  [0.01 ]   Decay Steps: [10000    ]             ││
│  │                                                                          ││
│  │  Target Update Frequency: [1000      ] steps                             ││
│  │                                                                          ││
│  │  [Load Preset ▼]  [Save as Preset]                                       ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════════│
│                                                                              │
│  ┌─ OPTUNA SEARCH CONFIGURATION ───────────────────────────────────────────┐│
│  │                                                                          ││
│  │  Learning Rate:     [0.00001  ] to [0.01     ]   ☑ Log scale            ││
│  │  Gamma:             [0.9      ] to [0.999    ]                          ││
│  │  Batch Size:        ☑ 32  ☑ 64  ☑ 128  ☐ 256                           ││
│  │  Hidden Layers:     ☑ [64,64]  ☑ [128,64]  ☑ [256,128]  ☐ [512,256]   ││
│  │  Window Size:       [20       ] to [100      ]                          ││
│  │                                                                          ││
│  │  ─── Search Settings ─────────────────────────────────────────────────  ││
│  │  Number of Trials:  [50        ]                                        ││
│  │  Optimize For:      [Sharpe Ratio        ▼]                             ││
│  │  Pruning:           ☑ Stop bad trials early (saves time)                ││
│  │  Parallel Trials:   [1         ] (increase if GPU available)            ││
│  │                                                                          ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  [← Back to Features]    [Start Training]    [Start Optuna Search]          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.5 Optuna Search Results UI

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HYPERPARAMETER SEARCH RESULTS                           │
│                                                                              │
│  Study: "EURUSD_DQN_search_20250102"         Status: ✅ Completed           │
│  Trials: 50/50                                Duration: 4h 23m              │
│                                                                              │
│  ┌─ BEST TRIAL (#37) ──────────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  Sharpe Ratio: 1.87    Win Rate: 58.3%    Max Drawdown: 8.2%           ││
│  │                                                                          ││
│  │  Hyperparameters:                                                        ││
│  │  ├─ learning_rate:  0.000234                                            ││
│  │  ├─ gamma:          0.973                                               ││
│  │  ├─ batch_size:     128                                                 ││
│  │  ├─ hidden_layers:  [256, 128]                                          ││
│  │  └─ window_size:    65                                                  ││
│  │                                                                          ││
│  │  [Use These Values]  [View Full Training]  [Export Config]              ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ TOP 5 TRIALS ──────────────────────────────────────────────────────────┐│
│  │  #   │ Sharpe │ Win Rate │ LR       │ Gamma │ Batch │ Layers           ││
│  │  ────┼────────┼──────────┼──────────┼───────┼───────┼──────────────────││
│  │  #37 │ 1.87   │ 58.3%    │ 0.000234 │ 0.973 │ 128   │ [256, 128]       ││
│  │  #42 │ 1.72   │ 56.1%    │ 0.000189 │ 0.981 │ 64    │ [256, 128]       ││
│  │  #29 │ 1.65   │ 54.8%    │ 0.000312 │ 0.969 │ 128   │ [128, 64]        ││
│  │  #48 │ 1.58   │ 55.2%    │ 0.000156 │ 0.977 │ 128   │ [256, 128]       ││
│  │  #31 │ 1.51   │ 53.9%    │ 0.000278 │ 0.985 │ 64    │ [256, 128]       ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ PARAMETER IMPORTANCE ──────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  learning_rate  ████████████████████████░░░░  78%  ← Most important!   ││
│  │  gamma          ████████████░░░░░░░░░░░░░░░░  42%                       ││
│  │  hidden_layers  ████████░░░░░░░░░░░░░░░░░░░░  31%                       ││
│  │  batch_size     █████░░░░░░░░░░░░░░░░░░░░░░░  18%                       ││
│  │  window_size    ███░░░░░░░░░░░░░░░░░░░░░░░░░  12%                       ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Training Pipeline

### 11.1 Training Modes

| Mode | Description | Data Source | Use Case |
|------|-------------|-------------|----------|
| **Live Training** | Model learns from real-time tick data | MT5 live feed | Primary mode, no historical data needed |
| **Historical Backtest** | Replay stored data for testing | Database/DVC | Validation once data collected |
| **Paper Trading** | Real orders on MT5 broker demo account | MT5 demo account | Real execution validation, no real money |

### 11.2 Training Requirements

#### FR-10: Live Training

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-10.1 | Train on real-time tick data from MT5 | P0 |
| FR-10.2 | Use only selected features from experiment config | P0 |
| FR-10.3 | Log metrics to MLflow in real-time | P0 |
| FR-10.4 | Support pause/resume training | P0 |
| FR-10.5 | Save checkpoints at configurable intervals | P0 |
| FR-10.6 | Display training progress in dashboard | P0 |

#### FR-11: Historical Backtest (When Data Available)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-11.1 | Load historical data from database or DVC | P1 |
| FR-11.2 | Event-driven tick replay | P1 |
| FR-11.3 | Deterministic with seed for reproducibility | P1 |
| FR-11.4 | Configurable slippage model | P1 |
| FR-11.5 | Generate performance report at end | P1 |

#### FR-12: Paper Trading

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-12.1 | Connect to MT5 broker demo/paper account | P0 |
| FR-12.2 | Execute real orders on demo account (no real money) | P0 |
| FR-12.3 | Track real P&L and positions on demo account | P0 |
| FR-12.4 | Run for configurable duration (e.g., 7 days minimum) | P0 |
| FR-12.5 | Generate validation report with real execution metrics | P0 |
| FR-12.6 | Capture real slippage and broker conditions | P0 |

---

## 12. Model Lifecycle

### 12.1 Lifecycle Stages

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MODEL LIFECYCLE                                    │
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ TRAINING │───▶│  STAGING │───▶│  PAPER   │───▶│PRODUCTION│              │
│  │          │    │          │    │ TRADING  │    │          │              │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘              │
│       │               │               │               │                     │
│       ▼               ▼               ▼               ▼                     │
│  Training run    Model saved     Real-time      Live trading               │
│  in progress     to registry     validation      with real $               │
│                                                                              │
│  Gate: None      Gate: Training  Gate: Paper     Gate: User                │
│                  complete        results OK      approval + 2FA            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Model Registry Requirements

#### FR-13: Model Registry

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-13.1 | Register trained models with version | P0 |
| FR-13.2 | Support stages: Training, Staging, Paper, Production, Archived | P0 |
| FR-13.3 | Store model metadata (features, hyperparameters, metrics) | P0 |
| FR-13.4 | Link model to experiment configuration | P0 |
| FR-13.5 | Link model to MLflow run | P0 |
| FR-13.6 | Promote model between stages | P0 |
| FR-13.7 | Require paper trading validation before Production | P0 |
| FR-13.8 | Require 2FA for Production promotion | P0 |
| FR-13.9 | Rollback to previous Production model | P0 |

### 12.3 Promotion Gates

| From | To | Gate Requirements |
|------|-----|-------------------|
| Training | Staging | Training completed successfully |
| Staging | Paper | User initiates paper trading |
| Paper | Production | Paper trading shows positive results + User approval + 2FA |
| Production | Archived | User archives or replaces with new model |

---

## 13. Live Performance Tracking

### 13.1 Overview

The platform provides comprehensive live performance tracking for models executing real trades. This includes:
1. **Portfolio Performance** - Cumulative performance across all deployed models
2. **Model Performance** - Detailed analytics for each individual model
3. **Real-time Metrics** - Live updates via WebSocket
4. **Historical Analysis** - Performance over time with various timeframes

### 13.2 Portfolio Performance Requirements

#### FR-14: Portfolio Performance Dashboard

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-14.1 | Display cumulative P&L across all active models | P0 |
| FR-14.2 | Show portfolio equity curve (real-time + historical) | P0 |
| FR-14.3 | Display portfolio-level Sharpe ratio | P0 |
| FR-14.4 | Show portfolio maximum drawdown | P0 |
| FR-14.5 | Display total win rate across all models | P0 |
| FR-14.6 | Show profit factor (gross profit / gross loss) | P0 |
| FR-14.7 | Display asset allocation (% per currency pair) | P0 |
| FR-14.8 | Show contribution by model (which model contributes most) | P0 |
| FR-14.9 | Display daily/weekly/monthly/yearly P&L breakdown | P0 |
| FR-14.10 | Export portfolio report (PDF/CSV) | P1 |

### 13.3 Model-Specific Performance Requirements

#### FR-15: Individual Model Performance

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-15.1 | Display model P&L (total, today, this week, this month) | P0 |
| FR-15.2 | Show model equity curve with drawdown overlay | P0 |
| FR-15.3 | Display model-specific Sharpe ratio | P0 |
| FR-15.4 | Show model win rate and average win/loss | P0 |
| FR-15.5 | Display model maximum drawdown and recovery time | P0 |
| FR-15.6 | Show profit factor | P0 |
| FR-15.7 | Display average trade duration | P0 |
| FR-15.8 | Show trade distribution by hour/day/session | P1 |
| FR-15.9 | Display P&L by currency pair (for multi-pair models) | P0 |
| FR-15.10 | Show action distribution (buy/sell/hold percentages) | P0 |
| FR-15.11 | Display recent trades with entry/exit details | P0 |
| FR-15.12 | Show model configuration (features, hyperparameters) | P0 |
| FR-15.13 | Compare with paper trading performance | P1 |
| FR-15.14 | Export model report (PDF/CSV) | P1 |

### 13.4 Performance Metrics Calculated

| Metric | Formula/Description | Update Frequency |
|--------|---------------------|------------------|
| **Net P&L** | Sum of all closed trade profits/losses | Real-time |
| **Unrealized P&L** | Current value of open positions | Real-time |
| **Total P&L** | Net P&L + Unrealized P&L | Real-time |
| **Win Rate** | Winning trades / Total trades × 100 | Per trade |
| **Profit Factor** | Gross profit / Gross loss | Per trade |
| **Sharpe Ratio** | (Mean return - Risk-free) / Std deviation | Daily recalc |
| **Sortino Ratio** | (Mean return - Risk-free) / Downside deviation | Daily recalc |
| **Max Drawdown** | Largest peak-to-trough decline | Real-time |
| **Recovery Factor** | Net profit / Max drawdown | Daily recalc |
| **Expectancy** | (Win% × Avg Win) - (Loss% × Avg Loss) | Per trade |
| **Average Trade** | Total P&L / Number of trades | Per trade |
| **Avg Win / Avg Loss** | Mean of winning trades / Mean of losing trades | Per trade |
| **Longest Win Streak** | Maximum consecutive wins | Per trade |
| **Longest Loss Streak** | Maximum consecutive losses | Per trade |
| **Time in Market** | % of time with open positions | Hourly |

### 13.5 Portfolio Performance UI Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PORTFOLIO PERFORMANCE                                │
│                                                                              │
│  Time Range: [Today ▼] [This Week] [This Month] [This Year] [All Time]      │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      📈 PORTFOLIO EQUITY CURVE                         │  │
│  │                                                                        │  │
│  │  $12,000 ┤                                              ╭──────        │  │
│  │          │                                        ╭─────╯              │  │
│  │  $11,000 ┤                              ╭────────╯                     │  │
│  │          │                    ╭─────────╯                              │  │
│  │  $10,000 ┤────────────────────╯                                        │  │
│  │          │                                                             │  │
│  │   $9,000 ┤                                                             │  │
│  │          └─────────────────────────────────────────────────────────    │  │
│  │           Jan    Feb    Mar    Apr    May    Jun    Jul                │  │
│  │                                                                        │  │
│  │  ── Equity   ── Drawdown                                              │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────┐│
│  │ 💰 TOTAL P&L    │ │ 📊 SHARPE RATIO │ │ 📉 MAX DRAWDOWN │ │ 🎯 WIN RATE ││
│  │                 │ │                 │ │                 │ │             ││
│  │ +$2,456.78      │ │ 1.87            │ │ -8.2%           │ │ 58.3%       ││
│  │ +24.57%         │ │ Excellent       │ │ -$820           │ │ 142/244     ││
│  │ ▲ +$127 today   │ │                 │ │ Recovery: 12d   │ │             ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────┘│
│                                                                              │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────┐│
│  │ 📈 PROFIT FACTOR│ │ 💹 EXPECTANCY   │ │ ⏱️ AVG DURATION │ │ 📊 TRADES   ││
│  │                 │ │                 │ │                 │ │             ││
│  │ 1.82            │ │ $10.07          │ │ 2h 34m          │ │ 244 total   ││
│  │ Good            │ │ per trade       │ │                 │ │ 18 today    ││
│  └─────────────────┘ └─────────────────┘ └─────────────────┘ └─────────────┘│
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════════│
│                                                                              │
│  ┌─ MODEL CONTRIBUTIONS ───────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  Model         │ P&L        │ Win Rate │ Sharpe │ Trades │ Contribution ││
│  │  ──────────────┼────────────┼──────────┼────────┼────────┼──────────────││
│  │  🟢 v3.2.1     │ +$1,234.56 │ 62.1%    │ 2.14   │ 87     │ ████████ 50% ││
│  │  🟢 v3.1.0     │ +$892.22   │ 55.8%    │ 1.65   │ 102    │ ██████ 36%   ││
│  │  🟡 v2.8.3     │ +$330.00   │ 51.2%    │ 1.21   │ 55     │ ██ 14%       ││
│  │                                                                          ││
│  │  🟢 = Production   🟡 = Being monitored   🔴 = Underperforming          ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ P&L BREAKDOWN ─────────────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  Period      │ P&L        │ Win Rate │ Trades │ Best Day   │ Worst Day  ││
│  │  ────────────┼────────────┼──────────┼────────┼────────────┼────────────││
│  │  Today       │ +$127.45   │ 66.7%    │ 18     │ -          │ -          ││
│  │  This Week   │ +$543.21   │ 59.2%    │ 72     │ +$187.30   │ -$45.20    ││
│  │  This Month  │ +$1,892.33 │ 57.8%    │ 186    │ +$234.50   │ -$156.80   ││
│  │  This Year   │ +$2,456.78 │ 58.3%    │ 244    │ +$312.00   │ -$189.50   ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ CURRENCY PAIR ALLOCATION ──────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  EURUSD  ████████████████████████████████░░░░░░░░  62%   +$1,523.20     ││
│  │  GBPUSD  ██████████████░░░░░░░░░░░░░░░░░░░░░░░░░░  28%   +$687.58      ││
│  │  USDJPY  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10%   +$246.00      ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  [📥 Export Report]  [📊 Detailed Analytics]                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 13.6 Model Performance UI Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MODEL PERFORMANCE: v3.2.1                               │
│                                                                              │
│  Status: 🟢 Production    Since: Jan 15, 2025    [⚙️ Config] [📥 Export]   │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                      📈 MODEL EQUITY CURVE                             │  │
│  │                                                                        │  │
│  │  $11,500 ┤                                              ╭──────        │  │
│  │          │                                        ╭─────╯              │  │
│  │  $11,000 ┤                              ╭────────╯                     │  │
│  │          │                    ╭─────────╯                              │  │
│  │  $10,500 ┤────────────────────╯                                        │  │
│  │          │                                                             │  │
│  │  $10,000 ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ (starting balance)   │  │
│  │          └─────────────────────────────────────────────────────────    │  │
│  │           Week 1    Week 2    Week 3    Week 4    Week 5               │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────┐ ┌──────────────────────────┐  │
│  │ 💰 PERFORMANCE SUMMARY                    │ │ 📊 RISK METRICS          │  │
│  │                                           │ │                          │  │
│  │  Total P&L:        +$1,234.56  (+12.35%) │ │  Sharpe Ratio:    2.14   │  │
│  │  Today:            +$87.32     (+0.87%)  │ │  Sortino Ratio:   2.89   │  │
│  │  This Week:        +$312.45    (+3.12%)  │ │  Max Drawdown:    -4.2%  │  │
│  │  This Month:       +$892.11    (+8.92%)  │ │  Recovery Factor: 2.94   │  │
│  │                                           │ │  Win Streak:      8      │  │
│  │  Unrealized P&L:   +$45.20               │ │  Loss Streak:     3      │  │
│  │  Open Positions:   2                      │ │                          │  │
│  └──────────────────────────────────────────┘ └──────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────┐ ┌──────────────────────────┐  │
│  │ 🎯 TRADE STATISTICS                       │ │ ⏱️ TIMING ANALYSIS       │  │
│  │                                           │ │                          │  │
│  │  Total Trades:     87                     │ │  Avg Duration:   1h 45m  │  │
│  │  Winning:          54 (62.1%)             │ │  Shortest:       12m     │  │
│  │  Losing:           33 (37.9%)             │ │  Longest:        8h 22m  │  │
│  │                                           │ │                          │  │
│  │  Average Win:      +$34.21                │ │  Time in Market: 34%     │  │
│  │  Average Loss:     -$18.43                │ │  Trades/Day:     4.2     │  │
│  │  Largest Win:      +$156.80               │ │                          │  │
│  │  Largest Loss:     -$67.30                │ │  Best Hour:      14:00   │  │
│  │                                           │ │  Best Day:       Tuesday │  │
│  │  Profit Factor:    1.98                   │ │                          │  │
│  │  Expectancy:       $14.19/trade           │ │                          │  │
│  └──────────────────────────────────────────┘ └──────────────────────────┘  │
│                                                                              │
│  ┌─ ACTION DISTRIBUTION ───────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  BUY   ████████████████████████████████████████░░░░░  78 (45%)          ││
│  │  SELL  ██████████████████████████████░░░░░░░░░░░░░░░  62 (36%)          ││
│  │  HOLD  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  34 (19%)          ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ P&L BY CURRENCY PAIR ──────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  Pair     │ P&L        │ Trades │ Win Rate │ Avg Trade │ Contribution   ││
│  │  ─────────┼────────────┼────────┼──────────┼───────────┼────────────────││
│  │  EURUSD   │ +$845.30   │ 52     │ 65.4%    │ +$16.26   │ ████████ 68%   ││
│  │  GBPUSD   │ +$389.26   │ 35     │ 57.1%    │ +$11.12   │ ████ 32%       ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ RECENT TRADES ─────────────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  Time       │ Pair   │ Action │ Entry    │ Exit     │ P&L     │ Duration││
│  │  ───────────┼────────┼────────┼──────────┼──────────┼─────────┼─────────││
│  │  14:32:15   │ EURUSD │ BUY    │ 1.08234  │ 1.08312  │ +$78.00 │ 1h 12m  ││
│  │  12:15:42   │ GBPUSD │ SELL   │ 1.26543  │ 1.26421  │ +$45.20 │ 45m     ││
│  │  10:08:33   │ EURUSD │ BUY    │ 1.08156  │ 1.08089  │ -$23.50 │ 2h 5m   ││
│  │  08:22:11   │ EURUSD │ SELL   │ 1.08312  │ 1.08256  │ +$56.00 │ 1h 45m  ││
│  │                                                                          ││
│  │  [View All Trades →]                                                     ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ MODEL CONFIGURATION ───────────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  Features:     price_mid, rsi_14, macd_signal, macd_hist                 ││
│  │  Pairs:        EURUSD, GBPUSD                                            ││
│  │  Architecture: DQN with Attention                                       ││
│  │  Hidden:       [256, 128]                                                ││
│  │  Learning Rate: 0.000234                                                 ││
│  │  Gamma:        0.973                                                     ││
│  │  Window Size:  65                                                        ││
│  │                                                                          ││
│  │  [View Full Config]  [Compare with Paper Trading]                        ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─ PAPER VS LIVE COMPARISON ──────────────────────────────────────────────┐│
│  │                                                                          ││
│  │  Metric         │ Paper (Demo) │ Live Account │ Difference             ││
│  │  ────────────────┼──────────────┼──────────────┼────────────────────────││
│  │  Sharpe Ratio   │ 2.28         │ 2.14         │ -0.14 (minor diff)     ││
│  │  Win Rate       │ 64.2%        │ 62.1%        │ -2.1% (acceptable)     ││
│  │  Profit Factor  │ 2.12         │ 1.98         │ -0.14 (acceptable)     ││
│  │  Avg Trade      │ +$15.82      │ +$14.19      │ -$1.63 (diff)          ││
│  │                                                                          ││
│  │  ✅ Live performance within expected range of paper trading (demo)      ││
│  │  Note: Both use real MT5 execution, demo account vs live account        ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. MT5 Account Management

### 14.1 Overview

The MT5 Account Management system enables connecting multiple MT5 trading accounts via Expert Advisors (EAs) and assigning trained models to execute trades. Each MT5 terminal can connect independently, allowing you to run different models on different accounts simultaneously (e.g., demo account for testing, live account for trading).

#### Key Capabilities

| Capability | Description |
|------------|-------------|
| **Auto-Registration** | MT5 accounts auto-register when EA connects |
| **Multiple Accounts** | Support for multiple MT5 terminals/accounts simultaneously |
| **Manual Assignment** | Assign models to accounts through dashboard UI |
| **Connection Monitoring** | Real-time visibility of EA connection status for all accounts |
| **Assignment Audit Trail** | Full history of which models ran on which accounts |
| **Safety Validation** | Prevents dangerous assignments (e.g., untested model → live account) |

### 14.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                   MT5 ACCOUNT MANAGEMENT FLOW                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────┐                                                 │
│  │  MT5 Terminal  │                                                 │
│  │  + EA Attached │                                                 │
│  └────────┬───────┘                                                 │
│           │ 1. Connect & Auth                                       │
│           │ (sends account_login, broker, type)                     │
│           ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Python Server (terminal_manager.py)                        │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │ 2. Register/Update Account in Database               │   │   │
│  │  │    - Create mt5_accounts record if new               │   │   │
│  │  │    - Log connection in mt5_connections               │   │   │
│  │  │    - Update last_seen_at timestamp                   │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  │  ┌──────────────────────────────────────────────────────┐   │   │
│  │  │ 3. Check for Model Assignment                        │   │   │
│  │  │    - Query account_model_assignments table           │   │   │
│  │  │    - If assigned: Load model + Start trading         │   │   │
│  │  │    - If not: Wait for user assignment               │   │   │
│  │  └──────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│           │                                                          │
│           │ 4. Account appears in Dashboard                         │
│           ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Dashboard UI - MT5 Accounts Page                          │   │
│  │  ┌────────────────────────────────────────────────────┐    │   │
│  │  │ Account  │ Type │ Status    │ Model    │ Trading  │    │   │
│  │  │ ────────┼──────┼───────────┼──────────┼──────────│    │   │
│  │  │ 12345678│ Demo │ Connected │ v3.2.1   │ Active   │    │   │
│  │  │ 87654321│ Live │ Connected │ None     │ Paused   │    │   │
│  │  │          [Assign Model] [Pause] [Resume]          │    │   │
│  │  └────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│           │                                                          │
│           │ 5. User Assigns Model                                   │
│           ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Assignment Dialog                                          │   │
│  │  ┌────────────────────────────────────────────────────┐    │   │
│  │  │ Select Model:                                      │    │   │
│  │  │ ● v3.2.1 (Production) - Sharpe: 2.14             │    │   │
│  │  │ ○ v3.3.0 (Paper)      - Sharpe: 2.28             │    │   │
│  │  │ ○ v3.1.0 (Archived)   - Sharpe: 1.87             │    │   │
│  │  │                                                    │    │   │
│  │  │ [Confirm with 2FA]                                │    │   │
│  │  └────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│           │                                                          │
│           │ 6. Server Loads Model & Starts Trading                  │
│           ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  AI Trading System                                          │   │
│  │  - Load model weights from MLflow                           │   │
│  │  - Initialize environment for account                       │   │
│  │  - Start inference loop                                     │   │
│  │  - Execute trades via MT5 EA                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 14.3 Requirements

#### FR-16: MT5 Account Registration

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-16.1 | Auto-register MT5 accounts when EA connects | P0 |
| FR-16.2 | Store account details (login, type, broker, currency, leverage) | P0 |
| FR-16.3 | Track connection status (connected/disconnected) | P0 |
| FR-16.4 | Update last_seen_at timestamp on each connection | P0 |
| FR-16.5 | Log connection history with IP and EA version | P1 |
| FR-16.6 | Support multiple concurrent connections (different accounts) | P0 |

#### FR-17: Model Assignment

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-17.1 | Allow users to assign models to accounts via dashboard | P0 |
| FR-17.2 | Support one active model per account at a time | P0 |
| FR-17.3 | Store assignment history with user audit trail | P0 |
| FR-17.4 | Validate assignments (prevent untested model → live account) | P0 |
| FR-17.5 | Require 2FA for live account assignments | P0 |
| FR-17.6 | Support assignment notes/comments | P1 |
| FR-17.7 | Allow model hot-swapping (change model while trading) | P1 |

#### FR-18: Trading Control

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-18.1 | Start trading automatically when model is assigned | P0 |
| FR-18.2 | Support pause/resume trading per account | P0 |
| FR-18.3 | Stop trading when model is unassigned | P0 |
| FR-18.4 | Gracefully handle EA disconnection | P0 |
| FR-18.5 | Prevent trading if no model assigned | P0 |
| FR-18.6 | Log all trading state changes | P0 |

#### FR-19: Assignment Validation

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-19.1 | Block staging models from live accounts | P0 |
| FR-19.2 | Warn when assigning production model to demo account | P1 |
| FR-19.3 | Require paper trading results before live assignment | P0 |
| FR-19.4 | Check model performance thresholds before assignment | P1 |
| FR-19.5 | Validate model compatibility with account currency | P1 |

### 14.4 Database Schema

```sql
-- MT5 Accounts registered in the system
CREATE TABLE mt5_accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_login BIGINT UNIQUE NOT NULL,
    account_type VARCHAR(20) NOT NULL,  -- 'demo', 'live'
    broker_name VARCHAR(100),
    broker_server VARCHAR(100),
    account_currency VARCHAR(10),
    account_leverage INT,
    account_name VARCHAR(100),  -- User-friendly name (editable)
    is_active BOOLEAN DEFAULT TRUE,
    last_seen_at TIMESTAMP NULL,  -- Last time EA connected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_login (account_login),
    INDEX idx_active (is_active),
    INDEX idx_type (account_type)
);

-- Model assignments to MT5 accounts
CREATE TABLE account_model_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    model_id INT NOT NULL,
    trading_mode VARCHAR(20) NOT NULL,  -- 'paper', 'live'
    is_active BOOLEAN DEFAULT TRUE,  -- Only one active assignment per account
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by INT,  -- dashboard_users.id
    deactivated_at TIMESTAMP NULL,
    deactivated_by INT NULL,
    notes TEXT,
    FOREIGN KEY (account_id) REFERENCES mt5_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (model_id) REFERENCES models(id),
    FOREIGN KEY (assigned_by) REFERENCES dashboard_users(id),
    FOREIGN KEY (deactivated_by) REFERENCES dashboard_users(id),
    UNIQUE KEY unique_active_account (account_id, is_active),
    INDEX idx_model (model_id),
    INDEX idx_active (is_active),
    INDEX idx_assigned_at (assigned_at)
);

-- Connection status tracking
CREATE TABLE mt5_connections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    ea_version VARCHAR(50),
    connection_ip VARCHAR(45),
    connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMP NULL,
    disconnect_reason VARCHAR(100),
    is_connected BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (account_id) REFERENCES mt5_accounts(id) ON DELETE CASCADE,
    INDEX idx_account_connected (account_id, is_connected),
    INDEX idx_connected_at (connected_at)
);
```

### 14.5 EA Authentication Protocol

**Updated authentication message from EA:**

```json
{
  "auth_code": 2,
  "login": 12345678,
  "account_type": 0,  // 0=Demo, 2=Real
  "broker_name": "IC Markets",
  "broker_server": "ICMarkets-Demo",
  "currency": "USD",
  "leverage": 500,
  "ea_version": "1.00"
}
```

**Server response:**

```json
{
  "auth_status": 0,  // 0=Success
  "terminal_id": 1,
  "has_model_assigned": true,
  "model_version": "v3.2.1",
  "trading_enabled": true
}
```

### 14.6 API Endpoints

#### Account Management

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/mt5-accounts` | List all registered MT5 accounts | None (local deployment) |
| GET | `/mt5-accounts/{id}` | Get account details with assignment history | None |
| PUT | `/mt5-accounts/{id}` | Update account name/settings | None |
| DELETE | `/mt5-accounts/{id}` | Remove account (soft delete) | None (confirmation required) |

#### Model Assignment

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/mt5-accounts/{id}/assign-model` | Assign model to account | JWT + 2FA |
| GET | `/mt5-accounts/{id}/assignment` | Get current assignment | JWT |
| GET | `/mt5-accounts/{id}/assignment-history` | Get assignment history | JWT |
| DELETE | `/mt5-accounts/{id}/assignment` | Unassign current model | JWT + 2FA |

#### Trading Control

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/mt5-accounts/{id}/pause` | Pause trading on account | None (local deployment) |
| POST | `/mt5-accounts/{id}/resume` | Resume trading on account | None (confirmation required) |
| GET | `/mt5-accounts/{id}/status` | Get real-time trading status | None |

#### Connection Monitoring

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/mt5-accounts/{id}/connections` | Get connection history | None (local deployment) |
| GET | `/mt5-accounts/connected` | List currently connected accounts | None |

### 14.7 Dashboard UI

#### MT5 Accounts Page

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MT5 ACCOUNTS MANAGEMENT                            │
│                                                                              │
│  Connected EAs will appear here automatically  [Refresh] [Connection Guide] │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                        │  │
│  │  Account     │ Type │ Broker     │ Status      │ Model    │ Trading  │  │
│  │  ────────────┼──────┼────────────┼─────────────┼──────────┼──────────│  │
│  │  12345678    │ Demo │ ICMarkets  │ 🟢 Connected│ v3.2.1   │🟢 Active │  │
│  │  My Demo Acc │      │            │ 2m ago      │          │          │  │
│  │              │      │            │             │ [Change] │ [Pause]  │  │
│  │  ────────────┼──────┼────────────┼─────────────┼──────────┼──────────│  │
│  │  87654321    │ Live │ Pepperstone│ 🟢 Connected│ v3.1.0   │🟢 Active │  │
│  │  Live Account│      │            │ 15s ago     │          │          │  │
│  │              │      │            │             │ [Change] │ [Pause]  │  │
│  │  ────────────┼──────┼────────────┼─────────────┼──────────┼──────────│  │
│  │  11223344    │ Demo │ ICMarkets  │ ⚪ Offline  │ v3.3.0   │⏸️ Paused │  │
│  │  Test Acc    │      │            │ 2h ago      │          │          │  │
│  │              │      │            │             │ [Change] │ [Resume] │  │
│  │  ────────────┼──────┼────────────┼─────────────┼──────────┼──────────│  │
│  │  99887766    │ Demo │ XM Global  │ ⚪ Offline  │ None     │ -        │  │
│  │  Backup      │      │            │ 3d ago      │          │          │  │
│  │              │      │            │             │ [Assign] │ -        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  [+ Connection Instructions]                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Assign Model Dialog

```
┌─────────────────────────────────────────────────────────────────┐
│  Assign Model to Account                                   [×]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  MT5 Account: 12345678 (Demo - ICMarkets)                      │
│  Current Model: v3.2.1 (Production)                             │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Select New Model:                                          │ │
│  │                                                            │ │
│  │ ○ v3.3.0 (Paper)                                          │ │
│  │   Sharpe: 2.28  Win Rate: 64.2%  Trades: 156             │ │
│  │   Paper trading: 7 days  ✅ Validated                     │ │
│  │                                                            │ │
│  │ ● v3.2.1 (Production)  [Currently Active]                │ │
│  │   Sharpe: 2.14  Win Rate: 62.1%  Trades: 244             │ │
│  │   Live trading: 18 days  ✅ Performing well              │ │
│  │                                                            │ │
│  │ ○ v3.1.0 (Archived)                                       │ │
│  │   Sharpe: 1.87  Win Rate: 58.3%  Trades: 187             │ │
│  │   Archived 5 days ago                                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Notes: [Optional notes about this assignment_____________]     │
│                                                                  │
│  ⚠️ This is a DEMO account. Safe for testing new models.        │
│                                                                  │
│  [Cancel]  [Assign Model]                                       │
└─────────────────────────────────────────────────────────────────┘
```

#### Assignment History View

```
┌─────────────────────────────────────────────────────────────────┐
│  Assignment History - Account 12345678                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Date       │ Model   │ Assigned By │ Duration  │ Performance   │
│  ──────────┼─────────┼─────────────┼───────────┼───────────────│
│  2025-01-02│ v3.2.1  │ admin       │ Active    │ Sharpe: 2.14  │
│  14:32     │ Paper   │             │ 2 days    │ Win: 62.1%    │
│  ──────────┼─────────┼─────────────┼───────────┼───────────────│
│  2024-12-31│ v3.1.0  │ admin       │ 2 days    │ Sharpe: 1.92  │
│  09:15     │ Paper   │             │           │ Win: 59.8%    │
│  ──────────┼─────────┼─────────────┼───────────┼───────────────│
│  2024-12-29│ v3.0.1  │ admin       │ 1 day     │ Sharpe: 1.65  │
│  11:20     │ Paper   │             │           │ Win: 54.2%    │
│                                                                  │
│  [Export History]  [Close]                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 14.8 Safety Validations

#### Assignment Validation Rules

```python
def validate_model_assignment(account: MT5Account, model: Model) -> ValidationResult:
    """
    Validate if a model can be assigned to an account
    """
    errors = []
    warnings = []
    
    # CRITICAL: Block staging models from live accounts
    if account.account_type == 'live' and model.stage == 'staging':
        errors.append("Cannot assign staging model to live account")
    
    # CRITICAL: Require paper trading before live
    if account.account_type == 'live' and model.stage not in ['paper', 'production']:
        errors.append("Model must complete paper trading before live assignment")
    
    # CRITICAL: Check if model has paper trading results
    if account.account_type == 'live' and not model.paper_trading_results:
        errors.append("Model has no paper trading validation results")
    
    # WARNING: Production model on demo account (unusual)
    if account.account_type == 'demo' and model.stage == 'production':
        warnings.append("Assigning production model to demo account (usually reversed)")
    
    # WARNING: Check performance thresholds
    if model.paper_trading_results:
        sharpe = model.paper_trading_results.get('sharpe_ratio', 0)
        win_rate = model.paper_trading_results.get('win_rate', 0)
        
        if sharpe < 1.5:
            warnings.append(f"Model Sharpe ratio ({sharpe}) below recommended 1.5")
        
        if win_rate < 0.55:
            warnings.append(f"Model win rate ({win_rate}) below recommended 55%")
    
    # WARNING: Currency mismatch
    if hasattr(model, 'trained_currency') and model.trained_currency != account.account_currency:
        warnings.append(f"Model trained on {model.trained_currency}, account uses {account.account_currency}")
    
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
```

### 14.9 User Workflow

#### Complete Workflow: From EA Connection to Trading

**Step 1: Connect EA**
1. User starts MT5 terminal with EA attached
2. EA connects to Python server (sends account details)
3. Server auto-registers account in `mt5_accounts` table
4. Connection logged in `mt5_connections` table

**Step 2: View in Dashboard**
1. User navigates to "MT5 Accounts" page
2. Sees newly connected account with status "🟢 Connected"
3. Model column shows "None" (no assignment yet)

**Step 3: Assign Model**
1. User clicks "Assign Model" button
2. Modal opens showing available models
3. User selects model (e.g., v3.2.1)
4. System validates assignment (safety checks)
5. User confirms (2FA required for live accounts)
6. Assignment saved in `account_model_assignments` table

**Step 4: Trading Starts**
1. Server receives assignment event
2. Loads model weights from MLflow
3. Initializes environment for account
4. Starts inference loop
5. Begins executing trades via EA

**Step 5: Monitor Performance**
1. User views real-time performance in "Performance" page
2. Can pause/resume trading anytime
3. Can change model by assigning a different one
4. Can view assignment history

### 14.10 Connection Instructions

**Instructions shown in dashboard for users:**

```markdown
## How to Connect Your MT5 Account

1. **Download the EA**
   - Download `mt5_trading_operation.mq5` from the dashboard
   - Place it in your MT5 data folder: `MQL5/Experts/`

2. **Configure EA Settings**
   - Open MT5 terminal
   - Drag EA onto a chart (any symbol, any timeframe)
   - Set these parameters:
     - `ip`: Server IP address (provided below)
     - `port`: 8080

3. **Enable AutoTrading**
   - Click "AutoTrading" button in MT5 toolbar (must be green)
   - Go to Tools > Options > Expert Advisors
   - Enable "Allow algorithmic trading"

4. **Verify Connection**
   - Check MT5 Experts tab for "Established connection" message
   - Your account will appear in this dashboard within seconds
   - Status will show "🟢 Connected"

5. **Assign a Model**
   - Click "Assign Model" button next to your account
   - Select which model you want to trade with
   - Confirm assignment (2FA required for live accounts)

6. **Start Trading**
   - Trading begins automatically once model is assigned
   - Monitor performance in the "Performance" page

**Your Server Details:**
- IP: `192.168.1.100`
- Port: `8080`
- Status: 🟢 Online
```

---

## 15. Dashboard Specifications

### 14.1 Dashboard Pages

| Page | Purpose | Priority |
|------|---------|----------|
| **Dashboard** | Overview of system status, live trading metrics | P0 |
| **Portfolio Performance** | Cumulative performance across all models | P0 |
| **Model Performance** | Detailed analytics for individual models | P0 |
| **Experiment Builder** | Create new experiments (feature + config) | P0 |
| **Training Monitor** | Watch training progress, metrics, charts | P0 |
| **Hyperparameter Search** | Optuna search progress and results | P0 |
| **Feature Catalog** | Browse all available features | P0 |
| **Model Registry** | Manage models through lifecycle | P0 |
| **Paper Trading** | Monitor paper trading validation | P0 |
| **MT5 Accounts** | Manage MT5 account connections and model assignments | P0 |
| **Live Trading** | Control and monitor live trading | P0 |
| **Trade History** | View historical trades | P1 |
| **Settings** | System configuration | P1 |

### 13.2 Dashboard Overview Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ┌──────┐  THE ALCHEMIST           🟢 Live   EURUSD    [Settings] │
│ │ Logo │  AI Forex Platform                                             │
├──┴──────┴────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │                                                                      │ │
│ │                     📈 PRICE CHART (TradingView)                     │ │
│ │                         Real-time candlesticks                       │ │
│ │                     With AI decision markers                         │ │
│ │                                                                      │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌──────────┐│
│ │ 💰 ACCOUNT      │ │ 🤖 AI STATUS    │ │ ⚡ CONTROLS     │ │ 📊 PERF  ││
│ │                 │ │                 │ │                 │ │          ││
│ │ Balance         │ │ Mode: Training  │ │ [AI Trading]    │ │ Win: 62% ││
│ │ $10,245.50      │ │ Steps: 1,442    │ │   ○ OFF  ● ON   │ │          ││
│ │                 │ │ Epsilon: 0.15   │ │                 │ │ Sharpe   ││
│ │ Equity          │ │ Model: v3.2.1   │ │ [Live Training] │ │ 1.42     ││
│ │ $10,312.20      │ │                 │ │   ● ON   ○ OFF  │ │          ││
│ │                 │ │ Optuna: Idle    │ │                 │ │ DD: 8.2% ││
│ │ Today's P&L     │ │ Best Sharpe:1.87│ │ ┌─────────────┐ │ │          ││
│ │ +$67.70 (+0.66%)│ │                 │ │ │ 🚨 KILL     │ │ │          ││
│ └─────────────────┘ └─────────────────┘ │ └─────────────┘ │ └──────────┘│
│                                         └─────────────────┘              │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ 🧪 RECENT EXPERIMENTS                              [View All →]      │ │
│ │ ┌──────────┬───────────────┬──────────┬─────────┬───────────────────┐│ │
│ │ │ Name     │ Features      │ Status   │ Sharpe  │ Actions           ││ │
│ │ ├──────────┼───────────────┼──────────┼─────────┼───────────────────┤│ │
│ │ │ exp_v3.2 │ 4 features    │ Training │ 1.42    │ [View] [Stop]     ││ │
│ │ │ exp_v3.1 │ 6 features    │ Paper    │ 1.28    │ [View] [Promote]  ││ │
│ │ │ exp_v3.0 │ 4 features    │ Live     │ 1.15    │ [View] [Archive]  ││ │
│ │ └──────────┴───────────────┴──────────┴─────────┴───────────────────┘│ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ ┌────────────────────────────┐ ┌────────────────────────────────────────┐│
│ │ 🔧 SYSTEM HEALTH           │ │ ⚠️ CIRCUIT BREAKERS                    ││
│ │ MT5: 🟢 Connected          │ │ Daily Loss:    ██░░░░░ 28% / 100%      ││
│ │ DB:  🟢 Connected          │ │ Consec Loss:   ██░░░░░ 2 / 5           ││
│ │ MLflow: 🟢 Running         │ │ Drawdown:      ███░░░░ 8.2% / 20%      ││
│ │ Ticks: 45/min              │ │ Volatility:    █░░░░░░ LOW             ││
│ └────────────────────────────┘ └────────────────────────────────────────┘│
│                                                                          │
│  [+ New Experiment]  [🔍 Search Hyperparameters]  [📊 Feature Catalog]  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 14.3 Navigation Sidebar

```
┌────────────────────┐
│ THE ALCHEMIST      │
├────────────────────┤
│                    │
│ 📊 Dashboard       │
│                    │
│ ── PERFORMANCE     │
│ 💰 Portfolio       │
│ 📈 Model Analytics │
│                    │
│ ── EXPERIMENTATION │
│ 🧪 New Experiment  │
│ 🏋️ Training        │
│ 🔍 Optuna Search   │
│ 📋 Feature Catalog │
│                    │
│ ── MODELS          │
│ 📦 Model Registry  │
│ 📄 Paper Trading   │
│                    │
│ ── TRADING         │
│ 🔌 MT5 Accounts    │
│ ⚡ Live Trading    │
│ 📜 Trade History   │
│                    │
│ ── SYSTEM          │
│ ⚙️ Settings        │
│ 🔒 Security        │
│                    │
└────────────────────┘
```

---

## 16. API Specification

### 15.1 Base URL

```
http://192.168.x.x:8000/api/v1
ws://192.168.x.x:8000/ws
```

### 15.2 Feature Catalog Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/features` | List all available features | None (local deployment) |
| GET | `/features/{name}` | Get feature details | None |
| GET | `/features/sources` | List data sources | None |
| GET | `/features/sources/{id}/health` | Get source health | None |

### 15.3 Experiment Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/experiments` | List all experiments | None (local deployment) |
| POST | `/experiments` | Create new experiment | None |
| GET | `/experiments/{id}` | Get experiment details | None |
| POST | `/experiments/{id}/start` | Start training | None |
| POST | `/experiments/{id}/stop` | Stop training | None |
| POST | `/experiments/{id}/clone` | Clone experiment | None |
| DELETE | `/experiments/{id}` | Delete experiment | None |

### 15.4 Hyperparameter Search Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/hyperparameters/search` | Start Optuna search | None (local deployment) |
| GET | `/hyperparameters/search/{id}` | Get search status | None |
| GET | `/hyperparameters/search/{id}/trials` | Get all trials | None |
| GET | `/hyperparameters/search/{id}/best` | Get best trial | None |
| POST | `/hyperparameters/search/{id}/stop` | Stop search | None |
| GET | `/hyperparameters/search/{id}/importance` | Get param importance | None |

### 15.5 Model Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/models` | List registered models | JWT |
| GET | `/models/{version}` | Get model details | JWT |
| POST | `/models/{version}/promote` | Promote model stage | JWT + 2FA |
| POST | `/models/{version}/archive` | Archive model | JWT |
| POST | `/models/{version}/rollback` | Rollback to model | JWT + 2FA |

### 15.6 Trading Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/trading/status` | Get trading status | None (local deployment) |
| POST | `/trading/start` | Start live trading | None (confirmation required) |
| POST | `/trading/stop` | Stop trading | None |
| POST | `/trading/kill` | Emergency kill switch | None (confirmation required) |
| GET | `/trading/positions` | Get open positions | None |
| GET | `/trading/history` | Get trade history | None |

### 15.7 Paper Trading Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/paper-trading/start` | Start paper trading | JWT |
| POST | `/paper-trading/stop` | Stop paper trading | JWT |
| GET | `/paper-trading/status` | Get paper trading status | JWT |
| GET | `/paper-trading/results` | Get paper trading results | JWT |

### 15.8 Performance Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/performance/portfolio` | Get portfolio performance summary | None (local deployment) |
| GET | `/performance/portfolio/equity-curve` | Get portfolio equity curve data | None |
| GET | `/performance/portfolio/breakdown` | Get P&L breakdown by period | None |
| GET | `/performance/portfolio/allocation` | Get allocation by pair/model | None |
| GET | `/performance/portfolio/export` | Export portfolio report (PDF/CSV) | None |
| GET | `/performance/models` | List all model performance summaries | None |
| GET | `/performance/models/{version}` | Get detailed model performance | None |
| GET | `/performance/models/{version}/equity-curve` | Get model equity curve | None |
| GET | `/performance/models/{version}/trades` | Get model trade history | None |
| GET | `/performance/models/{version}/statistics` | Get model statistics | None |
| GET | `/performance/models/{version}/comparison` | Compare with paper trading | None |
| GET | `/performance/models/{version}/export` | Export model report | None |
| GET | `/performance/metrics/realtime` | Get real-time performance metrics | None |

### 15.9 WebSocket Channels

| Endpoint | Description | Message Format |
|----------|-------------|----------------|
| `/ws/ticks` | Real-time tick data | `{ symbol, bid, ask, time }` |
| `/ws/training` | Training progress | `{ step, loss, reward, epsilon }` |
| `/ws/optuna` | Optuna search progress | `{ trial, params, value, best }` |
| `/ws/positions` | Position updates | `{ positions: [...] }` |
| `/ws/metrics` | P&L, balance updates | `{ balance, equity, pnl }` |
| `/ws/alerts` | Alert notifications | `{ type, message, severity }` |
| `/ws/performance` | Real-time performance updates | `{ portfolio_pnl, model_pnl, sharpe, drawdown }` |
| `/ws/trades` | Real-time trade notifications | `{ model, symbol, action, pnl, time }` |

---

## 16. Database Schema

### 16.1 New Tables

```sql
-- Feature catalog
CREATE TABLE features (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    data_type VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,
    description TEXT,
    is_available BOOLEAN DEFAULT TRUE,
    statistics JSON,  -- min, max, mean, std
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Data source providers
CREATE TABLE data_providers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    provider_class VARCHAR(200) NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    health_status VARCHAR(20) DEFAULT 'unknown',
    last_health_check TIMESTAMP NULL,
    config JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Experiments
CREATE TABLE experiments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    features JSON NOT NULL,  -- List of feature names
    currency_pairs JSON NOT NULL,  -- List of pairs
    hyperparameters JSON NOT NULL,
    training_mode VARCHAR(20) NOT NULL,  -- 'live', 'historical'
    status VARCHAR(20) NOT NULL DEFAULT 'created',  -- created, training, completed, failed
    mlflow_run_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL
);

-- Optuna studies
CREATE TABLE optuna_studies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    experiment_id INT,
    study_name VARCHAR(200) NOT NULL,
    n_trials INT NOT NULL,
    optimize_metric VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    best_trial_number INT,
    best_value DECIMAL(10, 6),
    best_params JSON,
    param_importance JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);

-- Optuna trials
CREATE TABLE optuna_trials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    study_id INT NOT NULL,
    trial_number INT NOT NULL,
    params JSON NOT NULL,
    value DECIMAL(10, 6),
    state VARCHAR(20) NOT NULL,  -- running, complete, pruned, failed
    metrics JSON,  -- sharpe, win_rate, drawdown, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (study_id) REFERENCES optuna_studies(id)
);

-- Model registry
CREATE TABLE models (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version VARCHAR(50) UNIQUE NOT NULL,
    experiment_id INT,
    stage VARCHAR(20) NOT NULL DEFAULT 'staging',  -- staging, paper, production, archived
    features JSON NOT NULL,
    hyperparameters JSON NOT NULL,
    metrics JSON,
    mlflow_model_uri VARCHAR(500),
    paper_trading_results JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    promoted_at TIMESTAMP NULL,
    promoted_by INT,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);

-- Paper trading sessions
CREATE TABLE paper_trading_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    start_balance DECIMAL(15, 2),
    current_balance DECIMAL(15, 2),
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    pnl DECIMAL(15, 2) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    FOREIGN KEY (model_id) REFERENCES models(id)
);

-- Dashboard users (unchanged)
CREATE TABLE dashboard_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    totp_secret VARCHAR(32),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL
);

-- Audit log (unchanged)
CREATE TABLE audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES dashboard_users(id)
);

-- Kill switch events (unchanged)
CREATE TABLE kill_switch_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trigger_source VARCHAR(50) NOT NULL,
    triggered_by INT,
    positions_closed INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL
);

-- Circuit breaker events (unchanged)
CREATE TABLE circuit_breaker_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    breaker_type VARCHAR(50) NOT NULL,
    trigger_value DECIMAL(10, 4),
    threshold_value DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resumed_at TIMESTAMP NULL
);

-- ============================================================================
-- LIVE PERFORMANCE TRACKING TABLES
-- ============================================================================

-- Live trading sessions (tracks when a model is deployed to production)
CREATE TABLE live_trading_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, paused, stopped
    start_balance DECIMAL(15, 2) NOT NULL,
    current_balance DECIMAL(15, 2) NOT NULL,
    high_water_mark DECIMAL(15, 2) NOT NULL,  -- For drawdown calculation
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    ended_reason VARCHAR(100),  -- 'user_stopped', 'kill_switch', 'replaced', etc.
    FOREIGN KEY (model_id) REFERENCES models(id)
);

-- Individual trades executed by models
CREATE TABLE model_trades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    model_id INT NOT NULL,
    order_uuid VARCHAR(36) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL,  -- 'BUY', 'SELL'
    entry_price DECIMAL(15, 5) NOT NULL,
    exit_price DECIMAL(15, 5),
    volume DECIMAL(10, 4) NOT NULL,
    pnl DECIMAL(15, 2),
    pnl_pips DECIMAL(10, 2),
    commission DECIMAL(10, 2) DEFAULT 0,
    swap DECIMAL(10, 2) DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'open',  -- 'open', 'closed', 'cancelled'
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP NULL,
    duration_seconds INT,
    FOREIGN KEY (session_id) REFERENCES live_trading_sessions(id),
    FOREIGN KEY (model_id) REFERENCES models(id)
);

-- Daily performance snapshots (for charts and historical analysis)
CREATE TABLE daily_performance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT,  -- NULL for portfolio-level
    session_id INT,
    date DATE NOT NULL,
    starting_balance DECIMAL(15, 2) NOT NULL,
    ending_balance DECIMAL(15, 2) NOT NULL,
    pnl DECIMAL(15, 2) NOT NULL,
    pnl_pct DECIMAL(10, 4) NOT NULL,
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    losing_trades INT DEFAULT 0,
    gross_profit DECIMAL(15, 2) DEFAULT 0,
    gross_loss DECIMAL(15, 2) DEFAULT 0,
    max_drawdown DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_model_date (model_id, date),
    FOREIGN KEY (model_id) REFERENCES models(id),
    FOREIGN KEY (session_id) REFERENCES live_trading_sessions(id)
);

-- Real-time performance metrics (updated frequently)
CREATE TABLE performance_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT,  -- NULL for portfolio-level
    session_id INT,
    metric_type VARCHAR(50) NOT NULL,  -- 'sharpe', 'sortino', 'win_rate', 'profit_factor', etc.
    value DECIMAL(15, 6) NOT NULL,
    period VARCHAR(20) NOT NULL,  -- 'realtime', 'daily', 'weekly', 'monthly', 'yearly', 'all_time'
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_metric (model_id, metric_type, period),
    FOREIGN KEY (model_id) REFERENCES models(id),
    FOREIGN KEY (session_id) REFERENCES live_trading_sessions(id)
);

-- Equity curve data points (for chart rendering)
CREATE TABLE equity_curve (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_id INT,  -- NULL for portfolio-level
    session_id INT,
    timestamp TIMESTAMP NOT NULL,
    equity DECIMAL(15, 2) NOT NULL,
    balance DECIMAL(15, 2) NOT NULL,
    drawdown_pct DECIMAL(10, 4) NOT NULL,
    unrealized_pnl DECIMAL(15, 2) DEFAULT 0,
    INDEX idx_model_timestamp (model_id, timestamp),
    FOREIGN KEY (model_id) REFERENCES models(id),
    FOREIGN KEY (session_id) REFERENCES live_trading_sessions(id)
);

-- Portfolio allocation tracking
CREATE TABLE portfolio_allocation (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_id INT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    position_value DECIMAL(15, 2) NOT NULL,
    allocation_pct DECIMAL(10, 4) NOT NULL,
    FOREIGN KEY (model_id) REFERENCES models(id)
);
```

---

## 18. Security Requirements

### 18.1 Security Overview

For local desktop deployment, the platform focuses on **trading safety** rather than user authentication. All security measures are designed to protect against trading losses and system failures.

### 18.2 Safety Features

| Feature | Description | Priority |
|---------|-------------|----------|
| **Kill Switch** | Emergency stop for all trading operations | P0 |
| **Circuit Breakers** | Automatic halt on loss thresholds | P0 |
| **Order Management System** | Prevents duplicate orders and position mismatches | P0 |
| **Risk Limits** | Configurable position sizing and drawdown limits | P0 |
| **Audit Logging** | Complete history of all trading operations | P0 |

### 18.3 Sensitive Operations

The following operations require explicit confirmation in the dashboard:

| Operation | Confirmation Required |
|-----------|----------------------|
| Enable live trading | Yes (warning banner) |
| Promote model to production | Yes (paper trading validation required) |
| Emergency kill switch | Yes (immediate action) |
| Modify risk parameters | Yes (during active trading) |

### 18.4 API Security

- **No authentication required** for local deployment
- All sensitive endpoints require explicit confirmation
- Complete audit logging of all operations
- Rate limiting on trading endpoints (if needed)

---

## 18. Technical Specifications

### 18.1 Performance Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | Dashboard load time | < 2 seconds |
| NFR-2 | WebSocket latency | < 100ms (local) |
| NFR-3 | API response time (p95) | < 200ms |
| NFR-4 | Optuna trial execution | < 5 min/trial |
| NFR-5 | Kill switch activation | < 500ms |

### 18.2 Reliability Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-6 | Auto-reconnect on WebSocket disconnect | Within 5s |
| NFR-7 | Training checkpoint frequency | Every 1000 steps |
| NFR-8 | Uptime during market hours | 99.9% |

### 18.3 Container Architecture

**Docker Compose Services:**

```yaml
services:
  # Trading Database
  mariadb:
    image: mariadb:10.9.5
    ports: ["3306:3306"]
    volumes:
      - mariadb_data:/var/lib/mysql
  
  # Trading Server (Python)
  server:
    build: ./src/mt5-python_server
    ports: ["8080:8080"]
    depends_on:
      - mariadb
    environment:
      DB_HOST: mariadb
  
  # FastAPI Service
  api:
    build: ./src/api
    ports: ["8000:8000"]
    depends_on:
      - mariadb
    environment:
      DATABASE_URL: mysql://forex_user:forex_password@mariadb/db_forex
  
  # MLflow Tracking
  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.10.0
    ports: ["5000:5000"]
    volumes:
      - mlflow_data:/mlflow
  
  # React Dashboard
  dashboard:
    build: ./src/dashboard
    ports: ["3000:80"]
    environment:
      VITE_API_URL: http://localhost:8000

volumes:
  mariadb_data:
  mlflow_data:
```

**Port Mapping:**

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| Dashboard | 3000 | http://localhost:3000 | React UI |
| FastAPI | 8000 | http://localhost:8000 | REST API + WebSocket |
| MLflow | 5000 | http://localhost:5000 | Experiment tracking |
| MariaDB | 3306 | localhost:3306 | Trading database |

---

## 20. Development Phases

### Phase 1: Safety Infrastructure (Week 1)

| Task | Priority | Estimate |
|------|----------|----------|
| Implement kill switch with all triggers | P0 | 4h |
| Implement circuit breakers | P0 | 4h |
| Implement OMS with idempotency | P0 | 6h |
| Integrate into trading controller | P0 | 4h |
| Write tests for safety module | P0 | 4h |

### Phase 2: Data Source Plugin System (Week 2)

| Task | Priority | Estimate |
|------|----------|----------|
| Create DataProviderRegistry | P0 | 4h |
| Implement feature auto-discovery | P0 | 4h |
| Create Feature model and catalog | P0 | 3h |
| Create indicator provider | P0 | 4h |
| Add database tables for features | P0 | 2h |
| Write provider extension documentation | P1 | 3h |

### Phase 3: Experiment & Optuna (Week 3)

| Task | Priority | Estimate |
|------|----------|----------|
| Create Experiment model and builder | P0 | 4h |
| Integrate Optuna for hyperparameter search | P0 | 8h |
| Create experiment runner | P0 | 4h |
| Add MLflow experiment tracking | P0 | 4h |
| Write tests for experiment module | P0 | 4h |

### Phase 4: FastAPI Service (Week 4)

| Task | Priority | Estimate |
|------|----------|----------|
| Set up FastAPI project | P0 | 2h |
| Implement feature catalog endpoints | P0 | 3h |
| Implement experiment endpoints | P0 | 4h |
| Implement hyperparameter endpoints | P0 | 4h |
| Implement model endpoints | P0 | 3h |
| Implement WebSocket channels | P0 | 6h |

### Phase 5: React Dashboard (Week 5-6)

| Task | Priority | Estimate |
|------|----------|----------|
| Initialize Vite + React + TypeScript | P0 | 1h |
| Set up Tailwind + shadcn/ui | P0 | 2h |
| Implement OAuth2 authentication flow with Authentik | P0 | 6h |
| Implement token refresh logic | P0 | 2h |
| Implement 2FA flow for sensitive operations | P0 | 3h |
| Implement dashboard layout | P0 | 4h |
| Implement Experiment Builder page | P0 | 8h |
| Implement Hyperparameter Search page | P0 | 6h |
| Implement Training Monitor page | P0 | 4h |
| Implement Feature Catalog page | P0 | 4h |
| Implement Model Registry page | P0 | 4h |
| Implement Live Trading page | P0 | 6h |

### Phase 6: Live Performance Tracking (Week 6-7)

| Task | Priority | Estimate |
|------|----------|----------|
| Create performance database tables | P0 | 3h |
| Implement trade logging and metrics calculation | P0 | 6h |
| Implement equity curve data collection | P0 | 4h |
| Create performance API endpoints | P0 | 6h |
| Implement Portfolio Performance page | P0 | 8h |
| Implement Model Performance page | P0 | 8h |
| Implement real-time WebSocket updates | P0 | 4h |
| Implement performance export (PDF/CSV) | P1 | 4h |
| Add paper vs live comparison | P1 | 3h |

### Phase 7: MLOps & Model Lifecycle (Week 8)

| Task | Priority | Estimate |
|------|----------|----------|
| Set up MLflow server | P0 | 2h |
| Implement model registry | P0 | 4h |
| Implement paper trading validation | P0 | 6h |
| Implement promotion workflow | P0 | 4h |
| Implement rollback functionality | P0 | 3h |

### Phase 8: Testing & Polish (Week 9)

| Task | Priority | Estimate |
|------|----------|----------|
| Write integration tests | P0 | 8h |
| Write E2E tests | P1 | 6h |
| Performance optimization | P1 | 4h |
| Bug fixes and polish | P0 | 8h |
| Documentation | P1 | 6h |

---

## 20. Testing Strategy

### 20.1 Test Coverage Targets

| Layer | Type | Tool | Target |
|-------|------|------|--------|
| Data Providers | Unit | pytest | 80% |
| Feature Catalog | Unit | pytest | 80% |
| Optuna Integration | Integration | pytest | Critical paths |
| FastAPI | Unit | pytest | 80% |
| FastAPI | E2E | pytest + httpx | All endpoints |
| React | Unit | Vitest | Components |
| React | E2E | Playwright | Critical flows |

### 20.2 Critical Test Cases

| Test Case | Description |
|-----------|-------------|
| `test_provider_auto_discovery` | Verify providers are discovered on startup |
| `test_feature_catalog_population` | Verify features are cataloged correctly |
| `test_optuna_search_completes` | Verify Optuna search runs and returns best params |
| `test_experiment_full_lifecycle` | Test create → train → paper → promote flow |
| `test_kill_switch_all_triggers` | Test all kill switch trigger mechanisms |
| `test_trade_logging` | Verify trades are logged with correct P&L |
| `test_equity_curve_calculation` | Verify equity curve updates correctly |
| `test_performance_metrics_accuracy` | Verify Sharpe, win rate, drawdown calculations |
| `test_portfolio_aggregation` | Verify multi-model portfolio metrics are correct |
| `test_paper_live_comparison` | Verify paper vs live comparison shows correctly |

---

## 22. Risk Assessment

### 21.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Optuna search takes too long | Medium | Medium | Pruning, parallel trials, time limits |
| Feature extraction performance | Medium | Medium | Caching, incremental calculation |
| Kill switch failure | Low | Critical | Multiple independent triggers |
| Data provider failure | Medium | Medium | Health checks, graceful degradation |

### 21.2 Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Bad model promoted to live | Medium | High | Paper trading validation required |
| Overfitting to live data | High | Medium | Regular validation, diverse features |
| No historical data for backtest | Certain (now) | Medium | Focus on live training, collect data |

---

## 22. Success Metrics

### 22.1 Platform KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Experiment creation time | < 5 minutes | UI timing |
| Feature discovery latency | < 1 second | Startup timing |
| Optuna trial throughput | 10+ trials/hour | MLflow logs |
| Model promotion success rate | 80%+ | Registry |

### 22.2 Trading KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Sharpe ratio (top model) | > 1.5 | Analytics |
| Win rate | > 55% | Trade history |
| Maximum drawdown | < 15% | Risk monitoring |

---

## 24. Deployment Strategy

### 23.1 Deployment Overview

#### Key Distinction

| Concept | Purpose | Controlled By |
|---------|---------|---------------|
| **Local Deployment** | Run the platform on your machine | User (this section) |
| **Trading Modes** | Execute trading strategies | User via UI |

**Local Deployment:**
- Single Docker Compose setup
- All services run on localhost
- No authentication required (single-user)
- All trading modes available (backtest/live training/paper/live)
- Optional monitoring for local debugging

**Trading Modes** (all available in local deployment):
- **Backtest** - Test on historical data (when available)
- **Live Training** - Train models with real-time data, no orders
- **Paper Trading** - Real orders on MT5 broker demo account (no real money)
- **Live Trading** - Real orders on MT5 live account (real money)

#### Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LOCAL SINGLE-USER DEPLOYMENT                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    LOCALHOST (Your Machine)                  │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │                                                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │   Server     │  │     API      │  │  Dashboard   │      │   │
│  │  │  (Python)    │  │   (FastAPI)  │  │   (React)     │      │   │
│  │  │  Port 1234   │  │  Port 8000   │  │  Port 3000    │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  │                                                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │   MariaDB    │  │    MLflow    │  │    Redis     │      │   │
│  │  │  Port 3306   │  │  Port 5000   │  │  Port 6379   │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  │                                                               │   │
│  │  All trading modes available in UI                           │   │
│  │  No authentication required (single-user)                     │   │
│  │  Optional: Local monitoring (Prometheus/Grafana)             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                   TRADING MODES (USER SELECTS IN UI)                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ BACKTEST  │  │LIVE TRAINING │  │PAPER TRADING │  │LIVE TRADING│ │
│  ├───────────┤  ├──────────────┤  ├──────────────┤  ├────────────┤ │
│  │Historical │  │Real-time data│  │Real-time data│  │Real orders │ │
│  │data replay│  │No orders     │  │Real orders   │  │Real money  │ │
│  │           │  │Train only    │  │Demo account  │  │Live account│ │
│  └───────────┘  └──────────────┘  └──────────────┘  └────────────┘ │
│        ▲               ▲                  ▲                 ▲        │
│        └───────────────┴──────────────────┴─────────────────┘        │
│                    User selects in Experiment UI                     │
│                      Available in Local Deployment                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Example workflow:**
1. User clones the repository and sets up environment variables
2. Runs `docker compose up` to start all services locally
3. Accesses dashboard at `http://localhost:3000`
4. Selects desired trading mode (backtest/paper/live) from the UI
5. Monitors performance and adjusts strategies as needed

### 23.2 Local Deployment Configuration

#### Local Environment (docker-compose.yml)

**Purpose:** Complete local single-user trading platform

**Services:**
- **MariaDB** (trading data storage)
- **Server** (Python MT5 trading server)
- **API** (FastAPI REST + WebSocket)
- **Dashboard** (React SPA)
- **MLflow** (experiment tracking)
- **Redis** (cache + pub/sub)
- **Optional:** Prometheus + Grafana (local monitoring)

**Characteristics:**
- All trading modes available (backtest/live training/paper/live)
- No authentication required (single-user local app)
- No SSL required (localhost only)
- Debug logging enabled
- Hot reload for development
- Optional monitoring stack for debugging

**Start Command:**
```bash
docker compose up -d --build
```

**Stop Command:**
```bash
docker compose down
```

**View Logs:**
```bash
docker compose logs -f
```

**Use cases:**
- Running the complete trading platform locally
- Developing new features
- Testing trading strategies
- Training and evaluating models
- Paper trading validation
- Live trading (with proper risk management)
- All trading modes accessible from UI

### 23.3 Container Stack Overview

| Service | Port | Purpose | Required |
|---------|------|---------|----------|
| **server** | 1234 | Python MT5 trading server | Yes |
| **api** | 8000 | FastAPI REST + WebSocket | Yes |
| **dashboard** | 3000 | React SPA | Yes |
| **mariadb** | 3306 | Trading database | Yes |
| **mlflow** | 5000 | Experiment tracking | Yes |
| **redis** | 6379 | Cache + Pub/Sub | Yes |
| **prometheus** | 9090 | Metrics collection | Optional |
| **grafana** | 3001 | Monitoring dashboards | Optional |

### 23.4 CI/CD Pipeline

#### Pipeline Strategy

The platform uses **GitHub Actions** with self-hosted runners on the VPS for security and data control.

#### Workflow Files

**`.github/workflows/ci.yml`** - Continuous Integration

```yaml
name: CI Pipeline

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [develop]

jobs:
  test:
    runs-on: self-hosted
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd src/mt5-python_server
          pip install -r requirements.txt
          pip install pytest pytest-cov bandit safety
      
      - name: Run unit tests
        run: |
          pytest tests/unit --cov=src --cov-report=xml
      
      - name: Run integration tests
        run: |
          pytest tests/integration
      
      - name: Security scan (Bandit)
        run: |
          bandit -r src/mt5-python_server/src -f json -o bandit-report.json
      
      - name: Dependency vulnerability scan
        run: |
          safety check --json
      
      - name: Build Docker images
        run: |
          docker-compose -f docker-compose.dev.yml build
      
      - name: Test containers
        run: |
          docker-compose -f docker-compose.dev.yml up -d
          sleep 10
          docker-compose -f docker-compose.dev.yml ps
          docker-compose -f docker-compose.dev.yml down
```

**`.github/workflows/deploy-staging.yml`** - Staging Deployment

```yaml
name: Deploy to Staging

on:
  push:
    branches: [develop]

jobs:
  deploy:
    runs-on: self-hosted
    environment: staging
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Build images
        run: |
          docker-compose -f docker-compose.staging.yml build
      
      - name: Backup database
        run: |
          docker-compose -f docker-compose.staging.yml run --rm backup
      
      - name: Run database migrations
        run: |
          docker-compose -f docker-compose.staging.yml run --rm api alembic upgrade head
      
      - name: Deploy services
        run: |
          docker-compose -f docker-compose.staging.yml up -d
      
      - name: Health check
        run: |
          sleep 15
          curl -f http://localhost/health || exit 1
      
      - name: Run smoke tests
        run: |
          pytest tests/smoke
      
      - name: Notify on Telegram
        if: always()
        run: |
          curl -X POST "https://api.telegram.org/bot${{ secrets.TELEGRAM_BOT_TOKEN }}/sendMessage" \
            -d chat_id="${{ secrets.TELEGRAM_CHAT_ID }}" \
            -d text="Staging deployment: ${{ job.status }}"
```

**`.github/workflows/deploy-production.yml`** - Production Deployment

```yaml
name: Deploy to Production

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  deploy:
    runs-on: self-hosted
    environment: production  # Requires manual approval in GitHub
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Verify paper trading results
        run: |
          python scripts/verify_paper_trading.py --min-sharpe=1.5 --min-winrate=0.55
      
      - name: Build production images
        run: |
          docker-compose -f docker-compose.prod.yml build
      
      - name: Backup database
        run: |
          docker-compose -f docker-compose.prod.yml run --rm backup
          
      - name: Run database migrations
        run: |
          docker-compose -f docker-compose.prod.yml run --rm api alembic upgrade head
      
      - name: Blue-green deployment
        run: |
          # Deploy new version alongside old
          docker-compose -f docker-compose.prod.yml up -d --no-deps --scale server=2 --scale api=2
          
          # Wait for new containers to be healthy
          sleep 30
          
          # Health check new containers
          docker-compose -f docker-compose.prod.yml ps | grep "Up (healthy)" || exit 1
          
          # Switch traffic to new containers
          docker-compose -f docker-compose.prod.yml up -d
          
          # Remove old containers
          docker system prune -f
      
      - name: Verify deployment
        run: |
          sleep 10
          curl -f https://your-domain.com/health || exit 1
          curl -f https://your-domain.com/api/v1/trading/status || exit 1
      
      - name: Rollback on failure
        if: failure()
        run: |
          echo "Deployment failed, rolling back..."
          git checkout HEAD~1
          docker-compose -f docker-compose.prod.yml up -d --build
      
      - name: Notify on success
        if: success()
        run: |
          curl -X POST "https://api.telegram.org/bot${{ secrets.TELEGRAM_BOT_TOKEN }}/sendMessage" \
            -d chat_id="${{ secrets.TELEGRAM_CHAT_ID }}" \
            -d text="✅ Production deployment successful: ${{ github.ref_name }}"
      
      - name: Notify on failure
        if: failure()
        run: |
          curl -X POST "https://api.telegram.org/bot${{ secrets.TELEGRAM_BOT_TOKEN }}/sendMessage" \
            -d chat_id="${{ secrets.TELEGRAM_CHAT_ID }}" \
            -d text="❌ Production deployment FAILED: ${{ github.ref_name }}"
```

### 23.5 Monitoring & Alerting

#### Metrics to Monitor

**Trading Metrics:**
- Real-time P&L
- Current drawdown percentage
- Win rate (rolling 24h, 7d, 30d)
- Open positions count
- Kill switch status
- Circuit breaker status
- Order execution latency

**System Metrics:**
- Container health (up/down)
- CPU usage per service
- Memory usage per service
- Database connection pool
- API response time (p50, p95, p99)
- WebSocket active connections
- Disk usage

**ML Metrics:**
- Training progress (steps/episode)
- Model inference latency
- Feature extraction time
- Optuna trial success rate
- MLflow tracking availability

#### Prometheus Configuration

**`src/monitoring/prometheus/prometheus.yml`**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - '/etc/prometheus/alerts/*.yml'

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  
  - job_name: 'api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
  
  - job_name: 'trading-server'
    static_configs:
      - targets: ['server:8080']
    metrics_path: '/metrics'
  
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
  
  - job_name: 'mariadb'
    static_configs:
      - targets: ['mariadb-exporter:9104']
  
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

#### Alert Rules

**`src/monitoring/prometheus/alerts/trading-alerts.yml`**

```yaml
groups:
  - name: trading_critical
    interval: 30s
    rules:
      - alert: DrawdownCritical
        expr: current_drawdown_pct > 15
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Critical drawdown reached: {{ $value }}%"
          description: "Trading drawdown has exceeded 15% threshold"
      
      - alert: KillSwitchActivated
        expr: kill_switch_active == 1
        labels:
          severity: critical
        annotations:
          summary: "Emergency kill switch activated"
          description: "All trading operations have been halted"
      
      - alert: TradingAPIDown
        expr: up{job="api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Trading API is unreachable"
          description: "API has been down for more than 1 minute"
      
      - alert: HighLatency
        expr: api_response_time_seconds{quantile="0.95"} > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API latency is high"
          description: "95th percentile response time: {{ $value }}s"
      
      - alert: DatabaseConnectionsHigh
        expr: mariadb_global_status_threads_connected / mariadb_global_variables_max_connections > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Database connection pool nearly exhausted"
          description: "{{ $value | humanizePercentage }} of max connections in use"
      
      - alert: UnusualTradeVolume
        expr: rate(trades_executed_total[5m]) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Unusually high trade execution rate"
          description: "{{ $value }} trades/second in the last 5 minutes"
```

#### Grafana Dashboards

**Trading Dashboard Panels:**
1. **Real-time P&L** (time series)
2. **Drawdown gauge** (0-20% range)
3. **Win rate** (stat panel)
4. **Open positions** (table)
5. **Kill switch status** (state indicator)
6. **Equity curve** (time series)
7. **Trade distribution** (bar chart)
8. **Model performance** (heatmap)

**System Dashboard Panels:**
1. **Container health** (status map)
2. **CPU usage** (gauge per service)
3. **Memory usage** (gauge per service)
4. **API response times** (heatmap)
5. **Database queries/sec** (time series)
6. **Active WebSocket connections** (time series)
7. **Disk usage** (gauge)
8. **Network I/O** (time series)

### 23.6 Secrets Management

#### Directory Structure

```
secrets/
├── .gitkeep
├── mariadb_root_password.txt
├── postgres_password.txt
├── authentik_secret_key.txt
├── grafana_admin_password.txt
├── redis_password.txt
├── telegram_bot_token.txt
└── oauth_client_secret.txt
```

**Important:** Add `secrets/` to `.gitignore` (except `.gitkeep`)

#### Generate Secrets

```bash
# Create secrets directory
mkdir -p secrets
chmod 700 secrets

# Generate strong passwords (50+ characters)
openssl rand -base64 48 > secrets/authentik_secret_key.txt
openssl rand -base64 32 > secrets/mariadb_root_password.txt
openssl rand -base64 32 > secrets/postgres_password.txt
openssl rand -base64 24 > secrets/redis_password.txt
openssl rand -base64 24 > secrets/grafana_admin_password.txt

# Restrict permissions
chmod 600 secrets/*.txt
```

### 23.7 Deployment Procedures

#### Initial Production Deployment

**Prerequisites:**
- VPS with Docker and Docker Compose installed
- Domain name pointing to VPS IP
- Ports 80, 443, 22 open on firewall
- MT5 live account credentials
- 7+ days of successful paper trading

**Step-by-Step:**

```bash
# 1. Clone repository on VPS
ssh user@your-vps
cd /opt
sudo git clone <your-repo> alchemist
cd alchemist
sudo chown -R $USER:$USER .

# 2. Set up secrets
mkdir secrets
chmod 700 secrets
./scripts/generate-secrets.sh

# 3. Configure environment
cp .env.example .env.prod
nano .env.prod  # Edit with production values

# 4. Initialize databases
docker-compose -f docker-compose.prod.yml up -d mariadb postgresql redis
sleep 30  # Wait for databases to initialize

# 5. Run database migrations
docker-compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# 6. Set up Authentik
docker-compose -f docker-compose.prod.yml up -d authentik-server authentik-worker
sleep 30
# Follow Appendix B: Authentik Initial Setup Guide

# 7. Set up SSL certificates
docker-compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot --webroot-path=/var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  -d your-domain.com

# 8. Start all services
docker-compose -f docker-compose.prod.yml up -d

# 9. Verify deployment
docker-compose -f docker-compose.prod.yml ps
curl -f https://your-domain.com/health
curl -f https://your-domain.com/api/v1/trading/status

# 10. Configure monitoring
# Access Grafana at https://your-domain.com/grafana
# Import dashboards from src/monitoring/grafana/dashboards/

# 11. Set up automated backups
# Backups run daily at 2 AM via cron in backup container
docker-compose -f docker-compose.prod.yml logs backup

# 12. Test alerts
# Trigger test alert and verify notification received
```

#### Regular Updates (Zero-Downtime)

**`scripts/deploy.sh`**

```bash
#!/bin/bash
set -e

ENVIRONMENT=${1:-production}
COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"

echo "Starting deployment to ${ENVIRONMENT}..."

# 1. Backup database
echo "Backing up database..."
docker-compose -f $COMPOSE_FILE run --rm backup

# 2. Pull latest code
echo "Pulling latest code..."
git pull origin main

# 3. Build new images
echo "Building Docker images..."
docker-compose -f $COMPOSE_FILE build

# 4. Run database migrations
echo "Running migrations..."
docker-compose -f $COMPOSE_FILE run --rm api alembic upgrade head

# 5. Rolling update (one service at a time)
SERVICES="server api dashboard"

for service in $SERVICES; do
  echo "Updating $service..."
  docker-compose -f $COMPOSE_FILE up -d --no-deps --build $service
  sleep 15
  
  # Health check
  if ! docker-compose -f $COMPOSE_FILE ps $service | grep -q "Up"; then
    echo "ERROR: $service failed to start, rolling back..."
    docker-compose -f $COMPOSE_FILE rollback $service
    exit 1
  fi
  
  # Application health check
  if [ "$service" = "api" ]; then
    if ! curl -f http://localhost/health > /dev/null 2>&1; then
      echo "ERROR: Health check failed for $service, rolling back..."
      docker-compose -f $COMPOSE_FILE rollback $service
      exit 1
    fi
  fi
  
  echo "$service updated successfully"
done

# 6. Prune old images
docker image prune -f

echo "Deployment complete!"

# 7. Send notification
if [ -f secrets/telegram_bot_token.txt ]; then
  TOKEN=$(cat secrets/telegram_bot_token.txt)
  CHAT_ID=$(cat secrets/telegram_chat_id.txt)
  MESSAGE="✅ Deployment to ${ENVIRONMENT} completed successfully"
  curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d chat_id="${CHAT_ID}" \
    -d text="${MESSAGE}"
fi
```

#### Rollback Procedure

**`scripts/rollback.sh`**

```bash
#!/bin/bash
set -e

ENVIRONMENT=${1:-production}
TAG=${2:-HEAD~1}
COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"

echo "Rolling back ${ENVIRONMENT} to ${TAG}..."

# 1. Confirm rollback
read -p "Are you sure you want to rollback to ${TAG}? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
  echo "Rollback cancelled"
  exit 0
fi

# 2. Stop services
echo "Stopping services..."
docker-compose -f $COMPOSE_FILE stop server api dashboard

# 3. Restore database backup (if needed)
read -p "Restore database backup? (yes/no): " restore_db
if [ "$restore_db" = "yes" ]; then
  read -p "Enter backup date (YYYY-MM-DD): " backup_date
  ./scripts/restore-backup.sh $backup_date
fi

# 4. Checkout previous version
echo "Checking out version ${TAG}..."
git checkout $TAG

# 5. Rebuild and start
echo "Rebuilding services..."
docker-compose -f $COMPOSE_FILE build server api dashboard

echo "Starting services..."
docker-compose -f $COMPOSE_FILE up -d

# 6. Verify rollback
sleep 15
if curl -f http://localhost/health > /dev/null 2>&1; then
  echo "Rollback successful!"
else
  echo "ERROR: Rollback verification failed!"
  exit 1
fi

# 7. Notify
if [ -f secrets/telegram_bot_token.txt ]; then
  TOKEN=$(cat secrets/telegram_bot_token.txt)
  CHAT_ID=$(cat secrets/telegram_chat_id.txt)
  MESSAGE="⚠️ Rolled back ${ENVIRONMENT} to ${TAG}"
  curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d chat_id="${CHAT_ID}" \
    -d text="${MESSAGE}"
fi
```

### 23.8 Backup & Recovery

#### Backup Strategy

**Automated Daily Backups:**
- **Schedule:** Daily at 2:00 AM
- **Retention:** 7 days (configurable)
- **What's backed up:**
  - MariaDB database (full dump)
  - PostgreSQL database (Authentik)
  - MLflow artifacts
  - Model checkpoints
  - Configuration files

**Backup Script** (`src/database/backup.py` - enhanced):

```python
import os
import subprocess
from datetime import datetime, timedelta
import boto3  # Optional: for S3 upload

BACKUP_DIR = os.getenv('DB_BACKUP_DIR', '/backups')
RETENTION_DAYS = int(os.getenv('DB_BACKUP_RETENTION_DAYS', 7))
S3_BUCKET = os.getenv('S3_BACKUP_BUCKET')  # Optional

def backup_mariadb():
    """Backup MariaDB database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"mariadb_backup_{timestamp}.sql.gz"
    filepath = os.path.join(BACKUP_DIR, filename)
    
    cmd = f"""
    mysqldump -h mariadb -u root -p{os.getenv('MYSQL_ROOT_PASSWORD')} \
      --all-databases --single-transaction --quick --lock-tables=false \
      | gzip > {filepath}
    """
    subprocess.run(cmd, shell=True, check=True)
    print(f"MariaDB backup created: {filepath}")
    return filepath

def backup_postgresql():
    """Backup PostgreSQL database"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"postgresql_backup_{timestamp}.sql.gz"
    filepath = os.path.join(BACKUP_DIR, filename)
    
    cmd = f"""
    PGPASSWORD={os.getenv('POSTGRES_PASSWORD')} pg_dump \
      -h postgresql -U authentik authentik \
      | gzip > {filepath}
    """
    subprocess.run(cmd, shell=True, check=True)
    print(f"PostgreSQL backup created: {filepath}")
    return filepath

def upload_to_s3(filepath):
    """Upload backup to S3 (optional)"""
    if not S3_BUCKET:
        return
    
    s3 = boto3.client('s3')
    filename = os.path.basename(filepath)
    s3.upload_file(filepath, S3_BUCKET, f"backups/{filename}")
    print(f"Uploaded to S3: s3://{S3_BUCKET}/backups/{filename}")

def cleanup_old_backups():
    """Remove backups older than retention period"""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    
    for filename in os.listdir(BACKUP_DIR):
        filepath = os.path.join(BACKUP_DIR, filename)
        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
        
        if file_time < cutoff:
            os.remove(filepath)
            print(f"Removed old backup: {filename}")

if __name__ == '__main__':
    print(f"Starting backup at {datetime.now()}")
    
    # Backup databases
    mariadb_backup = backup_mariadb()
    postgres_backup = backup_postgresql()
    
    # Upload to S3 (if configured)
    upload_to_s3(mariadb_backup)
    upload_to_s3(postgres_backup)
    
    # Cleanup old backups
    cleanup_old_backups()
    
    print(f"Backup completed at {datetime.now()}")
```

#### Recovery Procedure

**`scripts/restore-backup.sh`**

```bash
#!/bin/bash
set -e

BACKUP_DATE=$1
BACKUP_DIR="/backups"

if [ -z "$BACKUP_DATE" ]; then
  echo "Usage: ./restore-backup.sh YYYY-MM-DD"
  echo "Available backups:"
  ls -lh $BACKUP_DIR/*.sql.gz | awk '{print $9}' | xargs -n1 basename
  exit 1
fi

# Find backup file
MARIADB_BACKUP=$(find $BACKUP_DIR -name "mariadb_backup_${BACKUP_DATE}*.sql.gz" | head -n1)
POSTGRES_BACKUP=$(find $BACKUP_DIR -name "postgresql_backup_${BACKUP_DATE}*.sql.gz" | head -n1)

if [ -z "$MARIADB_BACKUP" ]; then
  echo "ERROR: No MariaDB backup found for ${BACKUP_DATE}"
  exit 1
fi

# Confirm restore
echo "Found backups:"
echo "  MariaDB: $MARIADB_BACKUP"
echo "  PostgreSQL: $POSTGRES_BACKUP"
read -p "Restore these backups? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
  echo "Restore cancelled"
  exit 0
fi

# Stop services
echo "Stopping services..."
docker-compose -f docker-compose.prod.yml stop server api dashboard

# Restore MariaDB
echo "Restoring MariaDB..."
gunzip < $MARIADB_BACKUP | docker exec -i mariadb mysql -u root -p${MYSQL_ROOT_PASSWORD}

# Restore PostgreSQL
if [ -n "$POSTGRES_BACKUP" ]; then
  echo "Restoring PostgreSQL..."
  gunzip < $POSTGRES_BACKUP | docker exec -i postgresql psql -U authentik authentik
fi

# Restart services
echo "Restarting services..."
docker-compose -f docker-compose.prod.yml up -d

echo "Restore complete!"
```

### 23.9 Pre-Deployment Checklist

#### Security Checklist

- [ ] All secrets generated and secured (600 permissions)
- [ ] Secrets excluded from Git (in `.gitignore`)
- [ ] SSL certificates installed and auto-renewal configured
- [ ] Firewall configured (only ports 80, 443, 22 open)
- [ ] Authentik fully configured with 2FA enabled
- [ ] Strong passwords for all database users
- [ ] OAuth2 client secret secured
- [ ] API rate limiting configured
- [ ] Security headers configured in Nginx
- [ ] Database users follow principle of least privilege

#### Testing Checklist

- [ ] All unit tests passing (`pytest tests/unit`)
- [ ] All integration tests passing (`pytest tests/integration`)
- [ ] Security scan completed (Bandit, Safety)
- [ ] Kill switch functionality tested
- [ ] Circuit breakers functionality tested
- [ ] Backup and restore tested
- [ ] Rollback procedure tested
- [ ] Health checks working on all services
- [ ] Monitoring dashboards configured
- [ ] Alerts tested and notifications received
- [ ] All trading modes accessible from UI (backtest, live training, paper, live)
- [ ] Model lifecycle transitions working (train → paper → live)
- [ ] WebSocket real-time updates working
- [ ] Authentication flow working (OAuth2 + 2FA)
- [ ] Database migrations tested

#### Infrastructure Checklist

- [ ] VPS meets minimum requirements (4 CPU, 8GB RAM, 100GB SSD)
- [ ] Docker and Docker Compose installed
- [ ] Domain name configured and DNS propagated
- [ ] Let's Encrypt rate limits checked
- [ ] Disk space sufficient for logs and backups
- [ ] Network bandwidth adequate (100+ Mbps)
- [ ] Time zone configured correctly
- [ ] NTP configured for accurate timestamps
- [ ] Monitoring stack configured (Prometheus, Grafana)
- [ ] Log aggregation configured (Loki)
- [ ] MT5 terminal connection tested (for all trading modes)

#### Documentation Checklist

- [ ] Deployment runbook updated
- [ ] Environment variables documented
- [ ] API documentation generated
- [ ] Monitoring dashboard guide created
- [ ] Troubleshooting guide updated
- [ ] Rollback procedure documented
- [ ] Contact information for emergencies
- [ ] MT5 broker connection details documented

### 23.10 Local Setup Timeline

**Initial Setup (First Time):**

| Step | Activity | Time |
|------|----------|------|
| **1** | Install Docker and Docker Compose | 15 min |
| **2** | Clone repository and configure `.env` | 10 min |
| **3** | Start services with `docker compose up` | 5 min |
| **4** | Wait for services to initialize | 5 min |
| **5** | Verify services are running | 5 min |
| **6** | Configure MT5 connection | 10 min |
| **7** | Test trading modes (start with paper) | 30 min |
| **Total** | **Complete local setup** | **~1.5 hours** |

**Regular Updates:**

| Step | Activity | Time |
|------|----------|------|
| **1** | Backup database (recommended) | 2 min |
| **2** | Pull latest code | 1 min |
| **3** | Rebuild and restart services | 5 min |
| **4** | Run migrations (if any) | 1 min |
| **5** | Verify services | 2 min |
| **Total** | **Update deployment** | **~10 minutes** |

**Note on Trading Modes:**
- All trading modes (backtest, live training, paper, live) are available immediately after setup
- Users select trading mode through the UI
- Model validation (paper trading before live) is a **user workflow**, not a deployment step
- Always test with paper trading before switching to live mode

---

## 24. Future Roadmap

### v4.0 (Future)

- [ ] Cryptocurrency market support (Binance, Bybit)
- [ ] Cross-market strategies (Forex + Crypto)
- [ ] On-chain data providers
- [ ] Advanced model architectures (Transformer, LSTM)
- [ ] Portfolio optimization
- [ ] Mobile app (React Native)
- [ ] Multi-user support
- [ ] Telegram/Discord bot integration

---

## 26. Appendix

### A. Environment Variables

```env
# Server Configuration
SERVER_IP=0.0.0.0
SERVER_PORT=1234

# Database (Trading)
DB_HOST=mariadb
DB_PORT=3306
DB_NAME=db_forex
DB_USER=forex_user
DB_PASSWORD=forex_password

# MyFxBook (Optional)
MYFXBOOK_EMAIL=your_email@example.com
MYFXBOOK_PASSWORD=your_password
URL_MYFXBOOK=https://www.myfxbook.com/

# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000

# Redis
REDIS_URL=redis://redis:6379

# Optuna (uses MariaDB)
OPTUNA_STORAGE=mysql://forex_user:forex_password@mariadb:3306/db_forex

# Risk Management (Optional - defaults in code)
CIRCUIT_BREAKER_DAILY_LOSS_PCT=5.0
CIRCUIT_BREAKER_MAX_CONSECUTIVE_LOSSES=5
CIRCUIT_BREAKER_MAX_DRAWDOWN_PCT=20.0
```

**Note:** For local single-user deployment, authentication is not required. All environment variables are stored in `.env` file (never commit to Git).

### B. Data Provider Extension Guide

To add a new data source:

1. Create a new file in `src/mt5-python_server/src/data_providers/`
2. Implement the `DataProvider` base class
3. Define features with metadata
4. Register with the provider registry
5. Restart server - features auto-appear in dashboard

See `docs/data-source-guide/` for detailed instructions.

### D. References

- [Authentik Documentation](https://docs.goauthentik.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FastAPI OAuth2 with JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [Optuna Documentation](https://optuna.org/)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [DVC Documentation](https://dvc.org/doc)
- [Vite Documentation](https://vitejs.dev/)
- [shadcn/ui Components](https://ui.shadcn.com/)
- [OAuth 2.0 + PKCE](https://oauth.net/2/pkce/)
- [OpenID Connect](https://openid.net/connect/)

---

**Document History**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-31 | Dev Team | Initial dashboard PRD |
| 2.0 | 2025-01-02 | Dev Team | Complete platform PRD with MLOps |
| 3.0 | 2025-01-02 | Dev Team | AI Experimentation Platform with data source plugins, feature catalog, experiment builder, and Optuna hyperparameter tuning |
| 3.1 | 2025-01-02 | Dev Team | Added comprehensive live performance tracking: portfolio performance dashboard, model-specific analytics, equity curves, trade statistics, and paper vs live comparison |
| 3.2 | 2025-01-02 | Dev Team | Replaced custom JWT authentication with Authentik IAM. Added OAuth2/OIDC integration, 2FA policies, PostgreSQL + Redis infrastructure, and comprehensive setup guide |
| 4.0 | 2025-01-02 | Dev Team | Added comprehensive deployment strategy: 3-tier environments (dev/staging/prod), CI/CD pipelines with GitHub Actions, monitoring/alerting stack (Prometheus/Grafana/Loki), backup/recovery procedures, secrets management, zero-downtime deployment scripts, and 12-week deployment timeline |
| 5.1 | 2025-01-02 | Dev Team | Simplified deployment strategy for local single-user app: removed multi-environment setup, CI/CD pipelines, VPS deployment, authentication requirements. Focused on local Docker Compose deployment with optional monitoring. Updated all deployment procedures, backup/recovery, and checklists for local use. |
| 4.1 | 2025-01-02 | Dev Team | Clarified paper trading implementation: uses real MT5 broker demo/paper account with real order execution (not simulated), capturing actual slippage and broker conditions. Updated trading mode descriptions and comparison metrics. |
| 5.0 | 2025-01-02 | Dev Team | Added MT5 Account Management system: user-controlled account-model assignment, auto-registration when EA connects, assignment validation with safety rules, connection monitoring, assignment history/audit trail, dedicated dashboard page with assign/pause/resume controls, and 2FA requirement for live account assignments. Includes 3 new database tables and 11 new API endpoints. |

---

*This PRD is a living document and will be updated as requirements evolve.*
