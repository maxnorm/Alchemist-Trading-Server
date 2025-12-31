# Product Requirements Document (PRD)
# The Alchemist Trading Dashboard

**Version:** 1.0  
**Date:** December 31, 2024  
**Author:** Development Team  
**Status:** Draft  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Objectives](#3-goals--objectives)
4. [Target Users](#4-target-users)
5. [Functional Requirements](#5-functional-requirements)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [Technical Architecture](#7-technical-architecture)
8. [Security Requirements](#8-security-requirements)
9. [UI/UX Specifications](#9-uiux-specifications)
10. [API Specification](#10-api-specification)
11. [Database Schema](#11-database-schema)
12. [Development Phases](#12-development-phases)
13. [File Structure](#13-file-structure)
14. [Dependencies](#14-dependencies)
15. [Risk Assessment](#15-risk-assessment)
16. [Success Metrics](#16-success-metrics)
17. [Future Enhancements](#17-future-enhancements)
18. [Appendix](#18-appendix)

---

## 1. Executive Summary

### 1.1 Overview

The Alchemist Trading Dashboard is a secure, real-time web application for monitoring and controlling an AI-powered forex trading system integrated with MetaTrader 5. The dashboard provides comprehensive visibility into trading performance, AI agent behavior, and system health while enabling secure remote management of trading operations.

### 1.2 Key Deliverables

| Deliverable | Description |
|-------------|-------------|
| **FastAPI Backend** | REST API + WebSocket layer for dashboard communication |
| **Next.js Frontend** | Real-time trading dashboard with professional charts |
| **Authentication System** | JWT + 2FA security for secure access |
| **Real-time Streaming** | WebSocket-based tick and metrics streaming |
| **Control Interface** | Enable/disable AI trading, configure risk parameters |

### 1.3 Technology Stack

| Layer | Technology | Justification |
|-------|------------|---------------|
| **Frontend** | Next.js 14 + TypeScript | SSR, excellent DX, React ecosystem |
| **UI Components** | shadcn/ui + Tailwind CSS | Beautiful, accessible, customizable |
| **Charts** | Lightweight Charts (TradingView) | Industry-standard trading charts |
| **State Management** | Zustand + TanStack Query | Simple, performant, real-time ready |
| **Backend API** | FastAPI (Python) | Async, WebSocket support, auto-docs |
| **Real-time** | WebSockets | Low latency for tick streaming |
| **Authentication** | JWT + TOTP (2FA) | Secure remote access |
| **Deployment** | Local Network + Tailscale VPN | Zero internet exposure |

---

## 2. Problem Statement

### 2.1 Current Challenges

| Challenge | Impact |
|-----------|--------|
| **No visual monitoring** | Must read console logs to understand system state |
| **No remote control** | Must SSH/RDP to enable/disable trading |
| **No performance analytics** | Limited visibility into AI agent performance |
| **No real-time charts** | Cannot visualize price action alongside AI decisions |
| **No alert system** | No notifications when important events occur |

### 2.2 Solution

Build a comprehensive web-based dashboard that provides:
- Real-time visibility into all trading operations
- One-click controls for AI trading management
- Performance analytics and historical data
- Secure remote access without exposing to internet
- Instant notifications for critical events

---

## 3. Goals & Objectives

### 3.1 Primary Goals

| Goal | Success Criteria |
|------|------------------|
| **G1: Real-time Monitoring** | View all metrics with < 1s latency |
| **G2: Remote Control** | Toggle AI trading from any device securely |
| **G3: Performance Analytics** | Track win rate, Sharpe ratio, drawdown |
| **G4: Security** | Zero unauthorized access incidents |

### 3.2 Secondary Goals

| Goal | Success Criteria |
|------|------------------|
| **G5: Alert System** | Notifications for trades and anomalies |
| **G6: Historical Analysis** | Query past trading sessions |
| **G7: Multi-Account Support** | Monitor multiple MT5 accounts |

### 3.3 Out of Scope (v1.0)

- Mobile native apps (iOS/Android)
- Multi-user access / team collaboration
- Automated report generation
- Third-party integrations (Telegram, Discord)
- Backtesting interface

---

## 4. Target Users

### 4.1 Primary User Profile

| Attribute | Description |
|-----------|-------------|
| **Role** | System Owner & Primary Operator |
| **Technical Level** | High (Developer) |
| **Goals** | Monitor AI trading, optimize performance, minimize risk |
| **Pain Points** | Lack of visibility, manual intervention required |
| **Devices** | Desktop (primary), Laptop, Mobile (read-only) |

### 4.2 Use Cases

| ID | Use Case | Priority |
|----|----------|----------|
| UC1 | View real-time account balance and P&L | P0 |
| UC2 | Toggle AI trading on/off | P0 |
| UC3 | View live price chart with AI decisions | P0 |
| UC4 | Monitor AI agent training metrics | P1 |
| UC5 | Adjust risk parameters | P1 |
| UC6 | View trade history with filtering | P1 |
| UC7 | Receive alerts for executed trades | P2 |
| UC8 | Analyze historical performance | P2 |
| UC9 | Export trading data | P3 |

---

## 5. Functional Requirements

### 5.1 Dashboard Core (P0)

#### FR-1: Account Overview Widget

| ID | Requirement |
|----|-------------|
| FR-1.1 | Display real-time account balance |
| FR-1.2 | Show current equity (balance + unrealized P&L) |
| FR-1.3 | Display today's P&L with percentage |
| FR-1.4 | Show connection status (MT5, Database) |
| FR-1.5 | Update every 1 second via WebSocket |

#### FR-2: AI Status Widget

| ID | Requirement |
|----|-------------|
| FR-2.1 | Show AI training status (Running/Stopped) |
| FR-2.2 | Display current epsilon (exploration rate) |
| FR-2.3 | Show total training steps |
| FR-2.4 | Display replay buffer size |
| FR-2.5 | Show average reward (last 100 steps) |

#### FR-3: Trading Controls

| ID | Requirement |
|----|-------------|
| FR-3.1 | Toggle AI trading on/off with confirmation |
| FR-3.2 | Toggle live training on/off |
| FR-3.3 | Emergency stop button (closes all positions) |
| FR-3.4 | Visual indicator for trading mode (SIM/LIVE) |
| FR-3.5 | Require 2FA confirmation for enabling live trading |

#### FR-4: Price Chart

| ID | Requirement |
|----|-------------|
| FR-4.1 | Display real-time candlestick chart |
| FR-4.2 | Show bid/ask spread |
| FR-4.3 | Mark AI trade entry/exit points |
| FR-4.4 | Support multiple timeframes (M1, M5, M15, H1, D1) |
| FR-4.5 | Display current open position line |

### 5.2 Analytics (P1)

#### FR-5: Performance Metrics

| ID | Requirement |
|----|-------------|
| FR-5.1 | Calculate and display win rate |
| FR-5.2 | Show Sharpe ratio (rolling 30-day) |
| FR-5.3 | Display maximum drawdown |
| FR-5.4 | Show profit factor |
| FR-5.5 | Display total trades count |
| FR-5.6 | Calculate average trade duration |

#### FR-6: Trade History

| ID | Requirement |
|----|-------------|
| FR-6.1 | List all executed trades in table format |
| FR-6.2 | Filter by date range |
| FR-6.3 | Filter by symbol |
| FR-6.4 | Filter by outcome (win/loss) |
| FR-6.5 | Show trade details (entry, exit, P&L, duration) |
| FR-6.6 | Export to CSV |

#### FR-7: Risk Management Display

| ID | Requirement |
|----|-------------|
| FR-7.1 | Show current risk parameters |
| FR-7.2 | Display daily loss limit usage |
| FR-7.3 | Show maximum drawdown limit |
| FR-7.4 | Display position size settings |
| FR-7.5 | Allow adjustment of risk parameters (with 2FA) |

### 5.3 Alerts & Notifications (P2)

#### FR-8: Alert System

| ID | Requirement |
|----|-------------|
| FR-8.1 | Browser notification on trade execution |
| FR-8.2 | Alert when daily loss limit approached (80%) |
| FR-8.3 | Alert when connection lost |
| FR-8.4 | Alert when AI training paused |
| FR-8.5 | In-app notification center with history |

### 5.4 System Health (P1)

#### FR-9: System Status

| ID | Requirement |
|----|-------------|
| FR-9.1 | Display MT5 connection status |
| FR-9.2 | Show database connection status |
| FR-9.3 | Display tick streamer health (ticks/min) |
| FR-9.4 | Show server uptime |
| FR-9.5 | Display memory usage |
| FR-9.6 | Show last model checkpoint timestamp |

---

## 6. Non-Functional Requirements

### 6.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | Dashboard load time | < 2 seconds |
| NFR-2 | WebSocket latency | < 100ms (local network) |
| NFR-3 | Chart rendering | < 500ms for 1000 candles |
| NFR-4 | API response time | < 200ms |
| NFR-5 | Continuous operation | 24/7 |

### 6.2 Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-6 | Auto-reconnect on WebSocket disconnect | Within 5s |
| NFR-7 | Graceful degradation if backend offline | Fallback UI |
| NFR-8 | No data loss on network interruption | 100% |
| NFR-9 | Uptime during market hours | 99.9% |

### 6.3 Usability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-10 | Responsive design | 1920px → 768px |
| NFR-11 | Dark theme optimized | Default |
| NFR-12 | Keyboard shortcuts | Common actions |
| NFR-13 | Accessibility | WCAG 2.1 AA |

### 6.4 Security

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-14 | All endpoints require authentication | 100% |
| NFR-15 | JWT token expiration | 30 minutes |
| NFR-16 | 2FA for sensitive operations | Required |
| NFR-17 | Rate limiting | 100 req/min |
| NFR-18 | No sensitive data in URLs | 100% |
| NFR-19 | HTTPS only | No HTTP fallback |

---

## 7. Technical Architecture

### 7.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      Next.js Frontend                               │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐│ │
│  │  │Dashboard │  │  Charts  │  │ Controls │  │  Analytics           ││ │
│  │  │  Widgets │  │(TradingV)│  │  Panel   │  │  & History           ││ │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘│ │
│  │       │              │             │                   │            │ │
│  │  ┌────▼──────────────▼─────────────▼───────────────────▼──────────┐│ │
│  │  │              State Management (Zustand)                        ││ │
│  │  │              API Client (TanStack Query)                       ││ │
│  │  └────────────────────────────┬───────────────────────────────────┘│ │
│  └───────────────────────────────┼────────────────────────────────────┘ │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │     HTTPS + WebSocket       │
                    │   (JWT Authentication)      │
                    └──────────────┬──────────────┘
                                   │
┌──────────────────────────────────┼──────────────────────────────────────┐
│                              API LAYER                                   │
│  ┌───────────────────────────────▼──────────────────────────────────┐   │
│  │                         FastAPI Server                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │   │
│  │  │    Auth     │  │   REST      │  │  WebSocket  │  │  Metrics │ │   │
│  │  │  Middleware │  │  Endpoints  │  │   Manager   │  │  Exporter│ │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────┬─────┘ │   │
│  │         │                │                │               │       │   │
│  │  ┌──────▼────────────────▼────────────────▼───────────────▼─────┐│   │
│  │  │                    Server Bridge                              ││   │
│  │  │              (Connects to existing Server class)              ││   │
│  │  └──────────────────────────┬────────────────────────────────────┘│   │
│  └─────────────────────────────┼─────────────────────────────────────┘   │
└────────────────────────────────┼─────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────────────┐
│                           CORE LAYER (Existing)                           │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                         Server (server.py)                         │   │
│  │  ┌────────────┐  ┌─────────────┐  ┌────────────┐  ┌─────────────┐ │   │
│  │  │   Tick     │  │    AI       │  │  Trading   │  │   Live      │ │   │
│  │  │  Streamer  │  │Integration  │  │ Controller │  │  Trainer    │ │   │
│  │  └─────┬──────┘  └──────┬──────┘  └─────┬──────┘  └──────┬──────┘ │   │
│  │        │                │               │                │        │   │
│  │  ┌─────▼────────────────▼───────────────▼────────────────▼──────┐ │   │
│  │  │                    Socket Connections                         │ │   │
│  │  └───────────────────────────┬───────────────────────────────────┘ │   │
│  └──────────────────────────────┼────────────────────────────────────┘   │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
             ┌──────▼──────┐             ┌──────▼──────┐
             │  MetaTrader │             │   MariaDB   │
             │      5      │             │  Database   │
             └─────────────┘             └─────────────┘
```

### 7.2 Network Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         YOUR LOCAL NETWORK                               │
│                                                                          │
│    ┌─────────────────┐           ┌─────────────────────────────────────┐│
│    │   Your Desktop  │           │        Old Desktop (Server)         ││
│    │    (Browser)    │◄─────────►│                                     ││
│    └─────────────────┘   LAN     │  ┌─────────────┐ ┌───────────────┐  ││
│                                  │  │ Python      │ │ Next.js       │  ││
│    ┌─────────────────┐           │  │ Server      │ │ Dashboard     │  ││
│    │     Phone       │◄─────────►│  │ :5000       │ │ :3000         │  ││
│    │   (Browser)     │   WiFi    │  └─────────────┘ └───────────────┘  ││
│    └─────────────────┘           │                                     ││
│                                  │  ┌─────────────┐ ┌───────────────┐  ││
│                                  │  │ FastAPI     │ │ MariaDB       │  ││
│                                  │  │ API :8000   │ │ :3306         │  ││
│                                  │  └─────────────┘ └───────────────┘  ││
│                                  └─────────────────────────────────────┘│
│                                           │                              │
│                                    LAN IP: 192.168.x.x                  │
└───────────────────────────────────────────┼─────────────────────────────┘
                                            │
                                     ❌ FIREWALL ❌
                                            │
                              ┌─────────────┴─────────────┐
                              │      INTERNET             │
                              │   (Blocked - No Access)   │
                              └───────────────────────────┘
                                            │
                                   ┌────────▼────────┐
                                   │   Tailscale    │
                                   │   VPN (Secure  │
                                   │   Remote Only) │
                                   └────────────────┘
```

---

## 8. Security Requirements

### 8.1 Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AUTHENTICATION FLOW                             │
│                                                                      │
│  ┌─────────┐    1. Login Request    ┌──────────────────────────────┐│
│  │ Browser │ ──────────────────────►│  POST /api/auth/login        ││
│  │         │    (username, pass)    │  - Validate credentials      ││
│  └─────────┘                        │  - Return { require_2fa }    ││
│       │                             └──────────────────────────────┘│
│       │                                           │                  │
│       │    2. 2FA Code Request                    │                  │
│       │◄──────────────────────────────────────────┘                  │
│       │                                                              │
│  ┌────▼────┐    3. Submit TOTP      ┌──────────────────────────────┐│
│  │  Enter  │ ──────────────────────►│  POST /api/auth/verify-2fa   ││
│  │  Code   │    (6-digit code)      │  - Verify TOTP               ││
│  └─────────┘                        │  - Generate JWT              ││
│       │                             │  - Return { access_token }   ││
│       │    4. JWT Token             └──────────────────────────────┘│
│       │◄─────────────────────────────────────────┘                   │
│       │                                                              │
│  ┌────▼────┐    5. API Requests     ┌──────────────────────────────┐│
│  │Dashboard│ ──────────────────────►│  Any Protected Endpoint      ││
│  │   UI    │  Authorization: Bearer │  - Validate JWT              ││
│  └─────────┘                        │  - Check expiration          ││
│                                     │  - Return data               ││
│                                     └──────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

### 8.2 Security Layers

| Layer | Implementation |
|-------|----------------|
| **Network Isolation** | Bind to local IP (192.168.x.x) only |
| **Firewall** | Block external access to API ports |
| **Remote Access** | Tailscale VPN only |
| **HTTPS** | Self-signed cert for local |
| **CORS** | Restrict to dashboard origin only |
| **Rate Limiting** | 100 req/min per IP, 5 login attempts/min |
| **JWT Expiration** | Access: 30 min, Refresh: 7 days |
| **2FA Required** | For enabling live trading |
| **Input Validation** | Pydantic schemas for all inputs |

### 8.3 Sensitive Operations Matrix

| Operation | Auth Required |
|-----------|---------------|
| View dashboard | JWT token |
| View account details | JWT token |
| Toggle live training | JWT token |
| **Enable live trading** | JWT + 2FA |
| **Modify risk parameters** | JWT + 2FA |
| **Emergency close all** | JWT + 2FA |

### 8.4 Security Checklist

- [ ] JWT tokens with short expiry (30 min)
- [ ] Refresh token rotation
- [ ] Bcrypt password hashing (cost factor 12)
- [ ] TOTP 2FA with backup codes
- [ ] Session invalidation on password change
- [ ] HTTPS only (TLS 1.3)
- [ ] Bind to local network IP only
- [ ] Windows Firewall configured
- [ ] Tailscale VPN for remote access
- [ ] CORS whitelist (local origins only)
- [ ] SQL injection prevention
- [ ] XSS prevention (CSP headers)
- [ ] Environment variables for secrets
- [ ] Failed login attempts logged

---

## 9. UI/UX Specifications

### 9.1 Design System

#### Color Palette

```css
:root {
  /* Dark Theme (Default) */
  --bg-primary: #0a0e14;
  --bg-secondary: #151a21;
  --bg-tertiary: #1c232d;
  
  /* Accent Colors */
  --accent-profit: #00d26a;
  --accent-loss: #ff4757;
  --accent-buy: #2196f3;
  --accent-sell: #ff9800;
  --accent-neutral: #7c3aed;
  
  /* Text */
  --text-primary: #e6edf3;
  --text-secondary: #8b949e;
  --text-muted: #5a5a6a;
  
  /* Borders */
  --border-default: #30363d;
  --border-active: #3b82f6;
  
  /* Chart Colors */
  --chart-green: #26a69a;
  --chart-red: #ef5350;
}
```

#### Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| Headings | Geist / SF Pro | 24-32px | 600-700 |
| Body | Inter | 14-16px | 400 |
| Numbers/Data | JetBrains Mono | 13-14px | 500 |
| Labels | Inter | 12px | 500 |

### 9.2 Dashboard Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ┌──────┐  THE ALCHEMIST           🟢 Live   EURUSD    [Settings] [User] │
│ │ Logo │                                                                 │
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
│ │ Balance         │ │ Status: Running │ │ [AI Trading]    │ │ Win: 62% ││
│ │ $10,245.50      │ │ Steps: 1,442    │ │   ○ OFF  ● ON   │ │          ││
│ │                 │ │ Epsilon: 0.15   │ │                 │ │ Sharpe   ││
│ │ Equity          │ │ Memory: 5,230   │ │ [Live Training] │ │ 1.42     ││
│ │ $10,312.20      │ │ Episode: 3      │ │   ● ON   ○ OFF  │ │          ││
│ │                 │ │                 │ │                 │ │ DD: 8.2% ││
│ │ Today's P&L     │ │ Avg Reward      │ │ ┌─────────────┐ │ │          ││
│ │ +$67.70 (+0.66%)│ │ 0.0234          │ │ │ 🚨 EMERGENCY│ │ │          ││
│ │ ▲               │ │ Loss: 0.0089    │ │ │    STOP     │ │ │          ││
│ └─────────────────┘ └─────────────────┘ │ └─────────────┘ │ └──────────┘│
│                                         └─────────────────┘              │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ 📜 RECENT TRADES                                    [View All →]     │ │
│ │ ┌──────┬──────────┬───────┬────────┬──────────┬────────────────────┐ │ │
│ │ │ Time │ Symbol   │ Type  │ Lots   │ P&L      │ Status             │ │ │
│ │ ├──────┼──────────┼───────┼────────┼──────────┼────────────────────┤ │ │
│ │ │14:32 │ EURUSD   │ BUY   │ 0.10   │ +$12.50  │ Closed (AI)        │ │ │
│ │ │13:15 │ EURUSD   │ SELL  │ 0.10   │ -$8.20   │ Closed (AI)        │ │ │
│ │ │11:45 │ EURUSD   │ BUY   │ 0.10   │ +$22.10  │ Closed (AI)        │ │ │
│ │ └──────┴──────────┴───────┴────────┴──────────┴────────────────────┘ │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ ┌────────────────────────────┐ ┌────────────────────────────────────────┐│
│ │ 🔧 SYSTEM HEALTH           │ │ ⚠️ RISK MANAGEMENT                     ││
│ │ MT5: 🟢 Connected          │ │ Daily Loss: ██████░░░░ 62% / 5%        ││
│ │ DB:  🟢 Connected          │ │ Max Position: 0.1 lots                 ││
│ │ Ticks: 45/min              │ │ Stop Loss: 2%  Take Profit: 4%         ││
│ │ Uptime: 3d 14h 22m         │ │ Max Drawdown: 8.2% / 20%               ││
│ └────────────────────────────┘ └────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Desktop XL | ≥1536px | Full layout, 4 columns |
| Desktop | ≥1280px | Full layout, 3 columns |
| Laptop | ≥1024px | Reduced sidebar, 2 columns |
| Tablet | ≥768px | Collapsed sidebar, stacked cards |
| Mobile | <768px | Hidden sidebar, single column |

---

## 10. API Specification

### 10.1 Authentication Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/auth/login` | Login with credentials | None |
| POST | `/api/auth/verify-2fa` | Verify TOTP code | Partial |
| POST | `/api/auth/refresh` | Refresh access token | Refresh |
| POST | `/api/auth/logout` | Invalidate session | JWT |

### 10.2 Account Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/accounts` | List connected accounts | JWT |
| GET | `/api/accounts/{login}` | Get account details | JWT |
| GET | `/api/accounts/{login}/balance` | Get real-time balance | JWT |
| GET | `/api/accounts/{login}/positions` | Get open positions | JWT |

### 10.3 Trading Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/trading/status` | Get trading status | JWT |
| POST | `/api/trading/enable` | Enable live trading | JWT + 2FA |
| POST | `/api/trading/disable` | Disable live trading | JWT |
| POST | `/api/trading/emergency-close` | Close all positions | JWT + 2FA |

### 10.4 AI Agent Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/ai/status` | Get AI agent status | JWT |
| POST | `/api/ai/training/start` | Start live training | JWT |
| POST | `/api/ai/training/stop` | Stop live training | JWT |
| GET | `/api/ai/metrics` | Get training metrics | JWT |
| GET | `/api/ai/checkpoints` | List model checkpoints | JWT |
| POST | `/api/ai/checkpoints/{id}/load` | Load checkpoint | JWT + 2FA |

### 10.5 Trades Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/trades` | List trade history | JWT |
| GET | `/api/trades/{id}` | Get trade details | JWT |
| GET | `/api/trades/export` | Export trades (CSV) | JWT |

### 10.6 Metrics Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/metrics/performance` | Get performance metrics | JWT |
| GET | `/api/metrics/risk` | Get risk metrics | JWT |
| PUT | `/api/metrics/risk` | Update risk params | JWT + 2FA |

### 10.7 System Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/system/health` | Get system health | JWT |
| GET | `/api/system/logs` | Get recent logs | JWT |

### 10.8 WebSocket Endpoints

| Endpoint | Description | Message Format |
|----------|-------------|----------------|
| `/ws/ticks` | Real-time tick streaming | `{ symbol, bid, ask, time }` |
| `/ws/metrics` | Live metrics updates | `{ balance, equity, pnl, ... }` |
| `/ws/ai` | AI agent updates | `{ action, reward, step, ... }` |
| `/ws/alerts` | Real-time alerts | `{ type, message, severity }` |

---

## 11. Database Schema

### 11.1 New Tables

```sql
-- Dashboard users table
CREATE TABLE dashboard_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    totp_secret VARCHAR(32),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL
);

-- Audit log for security
CREATE TABLE audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES dashboard_users(id)
);

-- Dashboard settings
CREATE TABLE dashboard_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNIQUE,
    theme VARCHAR(10) DEFAULT 'dark',
    refresh_interval INT DEFAULT 1000,
    chart_preferences JSON,
    notification_settings JSON,
    FOREIGN KEY (user_id) REFERENCES dashboard_users(id)
);

-- Alert history
CREATE TABLE alert_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    alert_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    severity ENUM('info', 'warning', 'error', 'critical') DEFAULT 'info',
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 12. Development Phases

### Phase 1: Foundation (Week 1-2)

**Objective**: Set up secure API layer and basic authentication

| Task | Description | Priority | Estimate |
|------|-------------|----------|----------|
| 1.1 | Create FastAPI application structure | P0 | 2h |
| 1.2 | Implement JWT authentication system | P0 | 4h |
| 1.3 | Add password hashing (bcrypt) | P0 | 1h |
| 1.4 | Implement rate limiting middleware | P0 | 2h |
| 1.5 | Set up CORS configuration | P0 | 1h |
| 1.6 | Create secure environment configuration | P0 | 1h |
| 1.7 | Add 2FA with TOTP | P1 | 3h |
| 1.8 | Integrate API with existing Server class | P0 | 4h |

**Deliverables**:
- [ ] Secure FastAPI backend running
- [ ] User authentication working
- [ ] API documentation via Swagger UI

### Phase 2: Core API Endpoints (Week 2-3)

**Objective**: Expose all server functionality via REST API

| Task | Description | Priority | Estimate |
|------|-------------|----------|----------|
| 2.1 | Account endpoints (list, details, balance) | P0 | 3h |
| 2.2 | Trading endpoints (positions, history) | P0 | 4h |
| 2.3 | AI control endpoints (start/stop/status) | P0 | 3h |
| 2.4 | Risk management endpoints | P1 | 2h |
| 2.5 | WebSocket for real-time ticks | P0 | 4h |
| 2.6 | WebSocket for trade notifications | P1 | 3h |
| 2.7 | Performance metrics endpoint | P1 | 3h |
| 2.8 | System health endpoint | P2 | 1h |

**Deliverables**:
- [ ] Full REST API operational
- [ ] Real-time WebSocket streaming
- [ ] API fully documented

### Phase 3: Frontend Foundation (Week 3-4)

**Objective**: Create Next.js dashboard with core UI

| Task | Description | Priority | Estimate |
|------|-------------|----------|----------|
| 3.1 | Initialize Next.js with TypeScript | P0 | 1h |
| 3.2 | Set up Tailwind CSS + shadcn/ui | P0 | 2h |
| 3.3 | Create authentication pages | P0 | 4h |
| 3.4 | Implement auth context + protected routes | P0 | 3h |
| 3.5 | Create main dashboard layout | P0 | 3h |
| 3.6 | Build navigation sidebar | P1 | 2h |
| 3.7 | Create WebSocket connection hook | P0 | 3h |
| 3.8 | Set up API client with interceptors | P0 | 2h |

**Deliverables**:
- [ ] Next.js app with authentication
- [ ] Responsive dashboard layout
- [ ] Real-time connection established

### Phase 4: Dashboard Features (Week 4-6)

**Objective**: Build all dashboard components

| Task | Description | Priority | Estimate |
|------|-------------|----------|----------|
| 4.1 | Account overview cards | P0 | 3h |
| 4.2 | TradingView Lightweight Charts | P0 | 6h |
| 4.3 | Real-time position table | P0 | 4h |
| 4.4 | Trade history with filtering | P1 | 4h |
| 4.5 | AI control panel | P0 | 4h |
| 4.6 | Risk management settings UI | P1 | 3h |
| 4.7 | Performance metrics charts | P1 | 4h |
| 4.8 | Economic calendar display | P2 | 3h |
| 4.9 | System logs viewer | P2 | 3h |
| 4.10 | Alerts/notifications system | P1 | 4h |

**Deliverables**:
- [ ] Fully functional trading dashboard
- [ ] All charts and visualizations
- [ ] AI controls operational

### Phase 5: Polish & Security (Week 6-7)

**Objective**: Production-ready application

| Task | Description | Priority | Estimate |
|------|-------------|----------|----------|
| 5.1 | Security audit | P0 | 4h |
| 5.2 | Error handling and fallbacks | P0 | 3h |
| 5.3 | Loading states and skeletons | P1 | 2h |
| 5.4 | Mobile responsive adjustments | P1 | 3h |
| 5.5 | Dark/light theme toggle | P2 | 2h |
| 5.6 | Performance optimization | P1 | 3h |
| 5.7 | Logging and monitoring | P1 | 2h |
| 5.8 | Documentation | P1 | 2h |

**Deliverables**:
- [ ] Production-ready application
- [ ] Security measures verified
- [ ] Documentation complete

### Phase 6: Deployment (Week 7-8)

**Objective**: Secure local deployment

| Task | Description | Priority | Estimate |
|------|-------------|----------|----------|
| 6.1 | Configure Windows Firewall | P0 | 1h |
| 6.2 | Set up Tailscale VPN | P0 | 2h |
| 6.3 | Create startup scripts | P1 | 2h |
| 6.4 | SSL certificate generation | P0 | 1h |
| 6.5 | Docker compose update | P1 | 2h |
| 6.6 | Backup strategy | P2 | 1h |
| 6.7 | Monitoring setup | P1 | 2h |
| 6.8 | Final testing | P0 | 4h |

**Deliverables**:
- [ ] Application running on local network
- [ ] VPN access configured
- [ ] Auto-start on system boot

---

## 13. File Structure

### 13.1 Backend (FastAPI)

```
src/mt5-python_server/
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application
│   │   ├── config.py               # Configuration
│   │   ├── dependencies.py         # Dependency injection
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── jwt.py              # JWT handling
│   │   │   ├── password.py         # Password hashing
│   │   │   └── totp.py             # 2FA logic
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py             # Auth endpoints
│   │   │   ├── accounts.py         # Account endpoints
│   │   │   ├── trading.py          # Trading endpoints
│   │   │   ├── ai.py               # AI control endpoints
│   │   │   └── risk.py             # Risk endpoints
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── rate_limit.py       # Rate limiting
│   │   │   └── security.py         # Security headers
│   │   ├── websockets/
│   │   │   ├── __init__.py
│   │   │   ├── manager.py          # Connection manager
│   │   │   └── handlers.py         # WS event handlers
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── auth.py             # Auth schemas
│   │       ├── account.py          # Account schemas
│   │       └── trading.py          # Trading schemas
│   ├── server.py                   # Existing server
│   └── ...                         # Existing files
├── .env
├── .env.example
└── requirements.txt
```

### 13.2 Frontend (Next.js)

```
src/dashboard/
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout
│   │   ├── page.tsx                # Redirect to dashboard
│   │   ├── login/
│   │   │   └── page.tsx            # Login page
│   │   ├── verify-2fa/
│   │   │   └── page.tsx            # 2FA verification
│   │   └── (dashboard)/
│   │       ├── layout.tsx          # Dashboard layout
│   │       ├── page.tsx            # Main dashboard
│   │       ├── accounts/
│   │       │   └── page.tsx
│   │       ├── trading/
│   │       │   └── page.tsx
│   │       ├── ai/
│   │       │   └── page.tsx
│   │       ├── history/
│   │       │   └── page.tsx
│   │       └── settings/
│   │           └── page.tsx
│   ├── components/
│   │   ├── ui/                     # shadcn/ui components
│   │   ├── charts/
│   │   │   ├── PriceChart.tsx
│   │   │   └── PerformanceChart.tsx
│   │   ├── dashboard/
│   │   │   ├── AccountCard.tsx
│   │   │   ├── PositionsTable.tsx
│   │   │   ├── TradeHistory.tsx
│   │   │   └── AIControlPanel.tsx
│   │   └── layout/
│   │       ├── Sidebar.tsx
│   │       ├── Header.tsx
│   │       └── Footer.tsx
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useWebSocket.ts
│   │   └── useApi.ts
│   ├── lib/
│   │   ├── api.ts
│   │   ├── auth.ts
│   │   └── utils.ts
│   ├── stores/
│   │   ├── authStore.ts
│   │   └── tradingStore.ts
│   └── types/
│       ├── api.ts
│       ├── trading.ts
│       └── auth.ts
├── public/
├── tailwind.config.ts
├── next.config.js
├── package.json
└── tsconfig.json
```

---

## 14. Dependencies

### 14.1 Backend (Python)

```txt
# Add to requirements.txt

# API Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0

# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pyotp==2.9.0
qrcode==7.4.2

# Security
slowapi==0.1.9
python-multipart==0.0.6

# WebSocket
websockets==12.0

# Validation
pydantic==2.5.3
email-validator==2.1.0
```

### 14.2 Frontend (Node.js)

```json
{
  "dependencies": {
    "next": "14.1.0",
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "typescript": "5.3.3",
    "tailwindcss": "3.4.1",
    "@radix-ui/react-icons": "1.3.0",
    "class-variance-authority": "0.7.0",
    "clsx": "2.1.0",
    "tailwind-merge": "2.2.0",
    "lightweight-charts": "4.1.0",
    "zustand": "4.5.0",
    "socket.io-client": "4.7.4",
    "date-fns": "3.3.1",
    "lucide-react": "0.321.0",
    "@tanstack/react-query": "5.17.0"
  }
}
```

---

## 15. Risk Assessment

### 15.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| WebSocket instability | Medium | High | Auto-reconnect, fallback polling |
| JWT security breach | Low | Critical | Short expiry, 2FA |
| Database connection issues | Low | High | Connection pooling |
| Chart performance | Medium | Medium | Data windowing |
| Server integration issues | Medium | High | Thorough testing |

### 15.2 Security Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Unauthorized access | Low | Critical | 2FA, VPN, rate limiting |
| Data breach | Low | Critical | Local network only |
| Brute force attack | Medium | Medium | Rate limiting, lockout |
| XSS vulnerability | Low | High | CSP headers, React |
| CSRF attack | Low | Medium | SameSite cookies |

### 15.3 Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| System failure during trading | Medium | Critical | Graceful degradation |
| Data loss | Low | High | Regular backups |
| API breaking changes | Low | Medium | API versioning |

---

## 16. Success Metrics

### 16.1 Performance KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Dashboard load time | < 2s | Lighthouse |
| WebSocket latency | < 100ms | Monitoring |
| API response time (p95) | < 200ms | Metrics |
| Uptime | 99.9% | Health checks |

### 16.2 User Experience KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to view balance | < 5s from login | Testing |
| Time to toggle trading | < 10s | Testing |
| Error recovery time | < 30s | Monitoring |

### 16.3 Security KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Unauthorized access | 0 | Security logs |
| Failed login blocks | 100% after 5 tries | Rate limiter |
| 2FA adoption | 100% | User records |

---

## 17. Future Enhancements

### v2.0 Roadmap

- [ ] Mobile app (React Native)
- [ ] Email/SMS trade notifications
- [ ] Multi-user support with permissions
- [ ] Backtesting visualization
- [ ] Strategy builder UI
- [ ] AI model training interface
- [ ] Portfolio analytics
- [ ] Risk calculator tools
- [ ] TradingView signals integration
- [ ] Telegram bot integration

---

## 18. Appendix

### A. Environment Variables

```env
# Server Configuration
SERVER_IP=192.168.1.100
SERVER_PORT=5000
API_PORT=8000
DASHBOARD_PORT=3000

# Security
JWT_SECRET_KEY=your-256-bit-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# Database
DATABASE_URL=mysql://user:password@localhost:3306/trading

# MT5 Configuration
MT5_LOGIN=your-login
MT5_PASSWORD=your-password
MT5_SERVER=your-broker-server

# AI Configuration
AI_TRADING_ENABLED=false
AI_LIVE_TRAINING_ENABLED=true
AI_AUTO_START=false

# External Services
MYFXBOOK_EMAIL=your-email
MYFXBOOK_PASSWORD=your-password
```

### B. Useful Commands

```bash
# Start backend API
cd src/mt5-python_server
python -m uvicorn src.api.main:app --host 192.168.1.100 --port 8000

# Start frontend dashboard
cd src/dashboard
npm run dev

# Generate SSL certificates
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up
```

### C. References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [shadcn/ui Components](https://ui.shadcn.com/)
- [Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [Tailscale VPN](https://tailscale.com/)

---

**Document History**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-31 | Dev Team | Initial draft |

---

*This PRD is a living document and will be updated as requirements evolve.*
