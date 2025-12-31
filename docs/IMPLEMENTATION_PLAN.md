# Implementation Plan
# The Alchemist Trading Dashboard

**Start Date:** January 2025  
**Estimated Duration:** 7 Weeks  
**Developer:** Solo Developer  

---

## Quick Start Commands

Once complete, the system will be started with:

```bash
# Start everything
docker compose up -d

# Access dashboard
# Local: http://192.168.1.100:3000
# Remote: Install Tailscale, then http://100.x.x.x:3000
```

---

## Phase Overview

| Phase | Duration | Focus Area |
|-------|----------|------------|
| **Phase 0** | Week 1 | Foundation & Setup |
| **Phase 1** | Week 2 | Core Dashboard |
| **Phase 2** | Week 3 | Real-time Features |
| **Phase 3** | Week 4 | Controls & Security |
| **Phase 4** | Week 5 | Analytics & History |
| **Phase 5** | Week 6 | Polish & Testing |
| **Phase 6** | Week 7 | Deployment |

---

## Phase 0: Foundation (Week 1)

### Goal
Set up the development environment with both FastAPI backend and Next.js frontend scaffolded and communicating.

### Tasks

#### Day 1-2: Project Setup

- [ ] **0.1** Create FastAPI project structure
  ```bash
  # In src/mt5-python_server/src/
  mkdir -p api/{auth,routes,websocket,schemas,middleware}
  touch api/__init__.py api/main.py api/config.py api/dependencies.py
  ```

- [ ] **0.2** Update requirements.txt with new dependencies
  ```
  fastapi>=0.109.0
  uvicorn[standard]>=0.27.0
  python-jose[cryptography]>=3.3.0
  passlib[bcrypt]>=1.7.4
  pyotp>=2.9.0
  python-multipart>=0.0.9
  slowapi>=0.1.9
  pydantic-settings>=2.0.0
  websockets>=12.0
  ```

- [ ] **0.3** Create Next.js project
  ```bash
  cd src
  npx create-next-app@latest dashboard --typescript --tailwind --eslint --app --src-dir
  cd dashboard
  npx shadcn-ui@latest init
  ```

- [ ] **0.4** Install frontend dependencies
  ```bash
  npm install lightweight-charts @tanstack/react-query zustand axios date-fns lucide-react
  npx shadcn-ui@latest add button card input label toast switch
  ```

#### Day 3: FastAPI Core

- [ ] **0.5** Implement `api/config.py` - Settings management
  ```python
  from pydantic_settings import BaseSettings
  
  class Settings(BaseSettings):
      api_host: str = "0.0.0.0"
      api_port: int = 8000
      jwt_secret_key: str
      jwt_algorithm: str = "HS256"
      jwt_expire_minutes: int = 30
      
      class Config:
          env_file = ".env"
  ```

- [ ] **0.6** Implement `api/main.py` - FastAPI app
  ```python
  from fastapi import FastAPI
  from fastapi.middleware.cors import CORSMiddleware
  
  app = FastAPI(title="Alchemist Dashboard API")
  
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:3000"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  
  @app.get("/api/health")
  async def health():
      return {"status": "healthy"}
  ```

- [ ] **0.7** Create Server Bridge class
  ```python
  # api/dependencies.py
  class ServerBridge:
      """Bridge between FastAPI and existing Server class"""
      _server_instance = None
      
      @classmethod
      def set_server(cls, server):
          cls._server_instance = server
      
      @classmethod
      def get_server(cls):
          return cls._server_instance
  ```

#### Day 4: Authentication

- [ ] **0.8** Implement `api/auth/password.py` - Password hashing
- [ ] **0.9** Implement `api/auth/jwt_handler.py` - JWT creation/verification
- [ ] **0.10** Implement `api/routes/auth.py` - Login endpoint
- [ ] **0.11** Create auth middleware for protected routes

#### Day 5: Docker & Integration

- [ ] **0.12** Create `Dockerfile.api` for FastAPI
- [ ] **0.13** Update `docker-compose.yml` with new services
- [ ] **0.14** Update `app.py` to start both Server and API
- [ ] **0.15** Test API health endpoint

### Deliverables Checklist
- [ ] FastAPI running on port 8000
- [ ] Next.js running on port 3000
- [ ] `/api/health` returns 200
- [ ] `/api/auth/login` accepts credentials
- [ ] JWT token returned on successful login
- [ ] Docker Compose starts all services

---

## Phase 1: Core Dashboard (Week 2)

### Goal
Build the main dashboard layout with account and AI status widgets, connected to real REST endpoints.

### Tasks

#### Day 1: Dashboard Layout

- [ ] **1.1** Create root layout with dark theme
  ```tsx
  // src/app/layout.tsx
  export default function RootLayout({ children }) {
    return (
      <html lang="en" className="dark">
        <body className="bg-[#0a0a0f] text-[#f0f0f5]">
          {children}
        </body>
      </html>
    );
  }
  ```

- [ ] **1.2** Create Header component with logo and status
- [ ] **1.3** Create Sidebar component (collapsible)
- [ ] **1.4** Create main dashboard grid layout

#### Day 2: Login Page

- [ ] **1.5** Create login page UI
- [ ] **1.6** Create auth store with Zustand
  ```tsx
  // src/stores/authStore.ts
  interface AuthStore {
    token: string | null;
    user: User | null;
    login: (username: string, password: string) => Promise<void>;
    logout: () => void;
  }
  ```
- [ ] **1.7** Connect login form to API
- [ ] **1.8** Implement protected route wrapper

#### Day 3: Account Widget

- [ ] **1.9** Implement `GET /api/accounts` endpoint
- [ ] **1.10** Implement `GET /api/accounts/{login}` endpoint
- [ ] **1.11** Create AccountWidget component
  ```tsx
  // Components: balance, equity, today's P&L
  // Auto-refresh every 5 seconds
  ```
- [ ] **1.12** Create useAccount hook with TanStack Query

#### Day 4: AI Status Widget

- [ ] **1.13** Implement `GET /api/ai/status` endpoint
  ```python
  @router.get("/status")
  async def get_ai_status():
      return {
          "is_running": trainer.is_running,
          "trading_enabled": trainer.trading_enabled,
          "training_enabled": trainer.training_enabled,
          "total_steps": trainer.total_steps,
          "epsilon": agent.epsilon,
          "memory_size": len(agent.memory),
          "current_episode": trainer.current_episode
      }
  ```
- [ ] **1.14** Create AIStatusWidget component
- [ ] **1.15** Add status indicators (running/stopped)

#### Day 5: Integration & Polish

- [ ] **1.16** Connect all widgets to API
- [ ] **1.17** Add loading skeletons
- [ ] **1.18** Add error states
- [ ] **1.19** Test full flow: login -> dashboard -> data display

### Deliverables Checklist
- [ ] Login page working
- [ ] Dashboard layout complete
- [ ] Account balance displaying
- [ ] AI status displaying
- [ ] Data refreshing every 5 seconds

---

## Phase 2: Real-time Features (Week 3)

### Goal
Implement WebSocket streaming for live ticks and metrics, plus TradingView chart integration.

### Tasks

#### Day 1: WebSocket Server

- [ ] **2.1** Create WebSocket manager class
  ```python
  # api/websocket/manager.py
  class ConnectionManager:
      def __init__(self):
          self.active_connections: List[WebSocket] = []
      
      async def connect(self, websocket: WebSocket):
          await websocket.accept()
          self.active_connections.append(websocket)
      
      async def broadcast(self, message: dict):
          for connection in self.active_connections:
              await connection.send_json(message)
  ```

- [ ] **2.2** Create tick streaming endpoint `/ws/ticks`
- [ ] **2.3** Connect tick stream to existing tick data

#### Day 2: Metrics Streaming

- [ ] **2.4** Create metrics streaming endpoint `/ws/metrics`
- [ ] **2.5** Broadcast account updates in real-time
- [ ] **2.6** Broadcast AI status updates
- [ ] **2.7** Add authentication to WebSocket connections

#### Day 3: Frontend WebSocket

- [ ] **2.8** Create useWebSocket hook
  ```tsx
  // src/hooks/useWebSocket.ts
  export function useWebSocket(endpoint: string) {
    const [data, setData] = useState(null);
    const [connected, setConnected] = useState(false);
    
    useEffect(() => {
      const ws = new WebSocket(`${WS_URL}${endpoint}`);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (e) => setData(JSON.parse(e.data));
      ws.onclose = () => {
        setConnected(false);
        // Auto-reconnect logic
      };
      return () => ws.close();
    }, [endpoint]);
    
    return { data, connected };
  }
  ```

- [ ] **2.9** Update AccountWidget to use WebSocket
- [ ] **2.10** Update AIStatusWidget to use WebSocket

#### Day 4: TradingView Chart

- [ ] **2.11** Install and configure Lightweight Charts
- [ ] **2.12** Create TradingViewChart component
  ```tsx
  // src/components/charts/TradingViewChart.tsx
  import { createChart, IChartApi } from 'lightweight-charts';
  
  export function TradingViewChart() {
    const chartRef = useRef<HTMLDivElement>(null);
    const chartApi = useRef<IChartApi | null>(null);
    
    useEffect(() => {
      if (chartRef.current) {
        chartApi.current = createChart(chartRef.current, {
          layout: {
            background: { color: '#0a0a0f' },
            textColor: '#f0f0f5',
          },
          grid: {
            vertLines: { color: '#1a1a24' },
            horzLines: { color: '#1a1a24' },
          },
        });
      }
    }, []);
    
    return <div ref={chartRef} className="h-[400px]" />;
  }
  ```

- [ ] **2.13** Connect chart to tick WebSocket
- [ ] **2.14** Add candlestick aggregation (1m, 5m, 15m, 1h)

#### Day 5: Chart Features

- [ ] **2.15** Add trade markers on chart (entry/exit points)
- [ ] **2.16** Add current position line
- [ ] **2.17** Add bid/ask lines
- [ ] **2.18** Add timeframe selector
- [ ] **2.19** Test real-time updates

### Deliverables Checklist
- [ ] WebSocket connections working
- [ ] Real-time tick streaming (< 100ms latency)
- [ ] TradingView chart displaying
- [ ] Candlesticks updating in real-time
- [ ] Trade markers visible on chart

---

## Phase 3: Controls & Security (Week 4)

### Goal
Implement trading controls with proper security (2FA) for sensitive operations.

### Tasks

#### Day 1: Control Panel UI

- [ ] **3.1** Create ControlPanel component
- [ ] **3.2** Create Toggle component for AI trading
- [ ] **3.3** Create Toggle component for live training
- [ ] **3.4** Create Emergency Stop button with warning styling
- [ ] **3.5** Add confirmation dialog component

#### Day 2: Control Endpoints

- [ ] **3.6** Implement `POST /api/trading/enable`
  ```python
  @router.post("/enable")
  async def enable_trading(
      totp_code: str,
      current_user: User = Depends(get_current_user)
  ):
      if not verify_totp(current_user.totp_secret, totp_code):
          raise HTTPException(401, "Invalid 2FA code")
      
      server.ai_integration.enable_trading()
      return {"status": "enabled"}
  ```

- [ ] **3.7** Implement `POST /api/trading/disable`
- [ ] **3.8** Implement `POST /api/ai/training/start`
- [ ] **3.9** Implement `POST /api/ai/training/stop`
- [ ] **3.10** Implement `POST /api/trading/emergency-close`

#### Day 3: 2FA Implementation

- [ ] **3.11** Implement TOTP generation
  ```python
  # api/auth/totp.py
  import pyotp
  
  def generate_totp_secret() -> str:
      return pyotp.random_base32()
  
  def get_totp_uri(secret: str, username: str) -> str:
      return pyotp.TOTP(secret).provisioning_uri(
          name=username,
          issuer_name="Alchemist Dashboard"
      )
  
  def verify_totp(secret: str, code: str) -> bool:
      totp = pyotp.TOTP(secret)
      return totp.verify(code, valid_window=1)
  ```

- [ ] **3.12** Create 2FA setup endpoint
- [ ] **3.13** Create QR code generation for authenticator apps
- [ ] **3.14** Add 2FA verification to sensitive endpoints

#### Day 4: Frontend 2FA

- [ ] **3.15** Create 2FA setup page
- [ ] **3.16** Create 2FA verification modal
- [ ] **3.17** Connect toggle controls with 2FA requirement
- [ ] **3.18** Store 2FA state in auth store

#### Day 5: Rate Limiting & Testing

- [ ] **3.19** Implement rate limiting middleware
  ```python
  from slowapi import Limiter
  from slowapi.util import get_remote_address
  
  limiter = Limiter(key_func=get_remote_address)
  
  @app.post("/api/auth/login")
  @limiter.limit("5/minute")
  async def login(request: Request):
      ...
  ```

- [ ] **3.20** Add rate limiting to all endpoints
- [ ] **3.21** Test control flows
- [ ] **3.22** Test 2FA flows
- [ ] **3.23** Test emergency stop

### Deliverables Checklist
- [ ] AI trading toggle working with 2FA
- [ ] Live training toggle working
- [ ] Emergency stop button closes all positions
- [ ] 2FA setup flow complete
- [ ] Rate limiting active
- [ ] All sensitive operations require 2FA

---

## Phase 4: Analytics & History (Week 5)

### Goal
Build trade history table and performance analytics dashboard.

### Tasks

#### Day 1: Trade History API

- [ ] **4.1** Create trades table schema (if not exists)
- [ ] **4.2** Implement `GET /api/trades` with pagination
  ```python
  @router.get("/")
  async def get_trades(
      page: int = 1,
      limit: int = 50,
      symbol: Optional[str] = None,
      start_date: Optional[datetime] = None,
      end_date: Optional[datetime] = None,
      outcome: Optional[str] = None  # 'win' | 'loss'
  ):
      ...
  ```

- [ ] **4.3** Implement `GET /api/trades/{id}` for trade details
- [ ] **4.4** Implement `GET /api/trades/export` for CSV export

#### Day 2: Trade History UI

- [ ] **4.5** Create TradeHistory component with table
- [ ] **4.6** Add date range picker filter
- [ ] **4.7** Add symbol filter dropdown
- [ ] **4.8** Add win/loss filter
- [ ] **4.9** Add pagination controls
- [ ] **4.10** Create trade detail modal

#### Day 3: Performance Metrics API

- [ ] **4.11** Create metrics calculation service
  ```python
  class MetricsCalculator:
      def calculate_win_rate(self, trades: List[Trade]) -> float:
          wins = sum(1 for t in trades if t.profit > 0)
          return wins / len(trades) if trades else 0
      
      def calculate_sharpe_ratio(self, returns: List[float]) -> float:
          if not returns:
              return 0
          mean_return = np.mean(returns)
          std_return = np.std(returns)
          return (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0
      
      def calculate_max_drawdown(self, equity_curve: List[float]) -> float:
          peak = equity_curve[0]
          max_dd = 0
          for equity in equity_curve:
              if equity > peak:
                  peak = equity
              dd = (peak - equity) / peak
              if dd > max_dd:
                  max_dd = dd
          return max_dd
  ```

- [ ] **4.12** Implement `GET /api/metrics/performance`
- [ ] **4.13** Implement `GET /api/metrics/risk`

#### Day 4: Performance UI

- [ ] **4.14** Create PerformanceMetrics component
  ```tsx
  // Display: win rate, Sharpe, max DD, profit factor
  ```
- [ ] **4.15** Create EquityCurve chart component
- [ ] **4.16** Add time range selector (7d, 30d, 90d, all)

#### Day 5: Analytics Page

- [ ] **4.17** Create dedicated analytics page `/analytics`
- [ ] **4.18** Add detailed performance breakdown
- [ ] **4.19** Add trade distribution charts
- [ ] **4.20** Implement CSV export functionality
- [ ] **4.21** Test all analytics features

### Deliverables Checklist
- [ ] Trade history table with filters
- [ ] Performance metrics displaying
- [ ] Equity curve chart
- [ ] CSV export working
- [ ] Analytics page complete

---

## Phase 5: Polish & Testing (Week 6)

### Goal
Add notifications, system health monitoring, responsive design, and thorough testing.

### Tasks

#### Day 1: Notification System

- [ ] **5.1** Create notification store
- [ ] **5.2** Create NotificationCenter component
- [ ] **5.3** Implement `/ws/alerts` WebSocket
- [ ] **5.4** Add browser notification permission request
- [ ] **5.5** Trigger notifications on trade execution

#### Day 2: System Health

- [ ] **5.6** Create SystemHealth component
- [ ] **5.7** Implement `GET /api/system/health`
  ```python
  @router.get("/health")
  async def get_system_health():
      return {
          "mt5_connected": bool(server.accounts),
          "database_connected": db.is_connected(),
          "tick_rate": calculate_tick_rate(),
          "uptime": get_uptime(),
          "memory_usage": get_memory_usage(),
          "last_checkpoint": get_last_checkpoint_time()
      }
  ```
- [ ] **5.8** Add connection status indicators
- [ ] **5.9** Add auto-refresh for health data

#### Day 3: Responsive Design

- [ ] **5.10** Test and fix tablet layout (768px - 1024px)
- [ ] **5.11** Test and fix mobile layout (< 768px)
- [ ] **5.12** Add mobile navigation menu
- [ ] **5.13** Ensure chart is responsive
- [ ] **5.14** Test all components at different sizes

#### Day 4: Error Handling

- [ ] **5.15** Create ErrorBoundary component
- [ ] **5.16** Add toast notifications for API errors
- [ ] **5.17** Add retry logic for failed requests
- [ ] **5.18** Create offline indicator
- [ ] **5.19** Test error scenarios

#### Day 5: Testing

- [ ] **5.20** Write API integration tests
- [ ] **5.21** Test authentication flow
- [ ] **5.22** Test WebSocket reconnection
- [ ] **5.23** Test 2FA flow
- [ ] **5.24** Security audit (check for vulnerabilities)
- [ ] **5.25** Performance testing

### Deliverables Checklist
- [ ] Notifications working
- [ ] System health displayed
- [ ] Fully responsive
- [ ] Error handling complete
- [ ] All tests passing
- [ ] Security audit passed

---

## Phase 6: Deployment (Week 7)

### Goal
Deploy production-ready system with secure remote access.

### Tasks

#### Day 1-2: Docker Production

- [ ] **6.1** Create production Dockerfiles
  ```dockerfile
  # Dockerfile.api
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY src/ ./src/
  CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

- [ ] **6.2** Create dashboard production build
  ```dockerfile
  # Dockerfile.dashboard
  FROM node:20-alpine AS builder
  WORKDIR /app
  COPY package*.json ./
  RUN npm ci
  COPY . .
  RUN npm run build
  
  FROM node:20-alpine
  WORKDIR /app
  COPY --from=builder /app/.next/standalone ./
  COPY --from=builder /app/.next/static ./.next/static
  CMD ["node", "server.js"]
  ```

- [ ] **6.3** Update docker-compose.yml for production
- [ ] **6.4** Configure environment variables

#### Day 3: HTTPS & Security

- [ ] **6.5** Generate self-signed SSL certificates
  ```bash
  openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout certs/key.pem \
    -out certs/cert.pem
  ```

- [ ] **6.6** Configure HTTPS in FastAPI
- [ ] **6.7** Update frontend to use HTTPS
- [ ] **6.8** Harden security settings

#### Day 4: VPN & Remote Access

- [ ] **6.9** Install Tailscale on server
  ```bash
  curl -fsSL https://tailscale.com/install.sh | sh
  tailscale up
  ```

- [ ] **6.10** Install Tailscale on mobile/remote devices
- [ ] **6.11** Configure firewall to only allow Tailscale
- [ ] **6.12** Test remote access via VPN

#### Day 5: Documentation & Backup

- [ ] **6.13** Write deployment documentation
- [ ] **6.14** Create backup scripts
  ```bash
  #!/bin/bash
  # backup.sh
  DATE=$(date +%Y%m%d)
  docker exec mariadb mysqldump -u root -p$DB_PASSWORD db_forex > backup_$DATE.sql
  cp -r models/ backup/models_$DATE/
  ```

- [ ] **6.15** Set up automatic model checkpoint backup
- [ ] **6.16** Create restore procedures
- [ ] **6.17** Final production testing

### Deliverables Checklist
- [ ] Docker production images built
- [ ] HTTPS configured
- [ ] Tailscale VPN working
- [ ] Remote access tested
- [ ] Documentation complete
- [ ] Backup procedures in place

---

## Post-Launch Checklist

### First Week After Launch

- [ ] Monitor system stability
- [ ] Check WebSocket connection reliability
- [ ] Verify all metrics are accurate
- [ ] Test emergency stop under real conditions
- [ ] Collect feedback and issues

### Security Maintenance

- [ ] Rotate JWT secret keys monthly
- [ ] Review access logs weekly
- [ ] Update dependencies monthly
- [ ] Run security scan quarterly

---

## Commands Reference

### Development

```bash
# Start backend (development)
cd src/mt5-python_server
python -m uvicorn src.api.main:app --reload --port 8000

# Start frontend (development)
cd src/dashboard
npm run dev

# Start everything with Docker
docker compose up -d
```

### Production

```bash
# Build production
docker compose -f docker-compose.prod.yml build

# Deploy
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose logs -f

# Backup
./scripts/backup.sh
```

### Tailscale

```bash
# Install
curl -fsSL https://tailscale.com/install.sh | sh

# Start
tailscale up

# Check status
tailscale status

# Get IP
tailscale ip
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Server crash during trading | Auto-disable trading on API disconnect |
| Database failure | Regular backups, transaction logging |
| WebSocket disconnect | Auto-reconnect with exponential backoff |
| Unauthorized access | 2FA + VPN + rate limiting |
| Model corruption | Checkpoint every 1000 steps, keep last 5 |

---

## Success Criteria

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Dashboard load time | < 2s | Chrome DevTools |
| WebSocket latency | < 100ms | Network tab |
| Uptime | 99.9% | Monitoring script |
| Zero security breaches | 0 | Access logs |
| All features working | 100% | Manual testing |

---

*Last updated: December 31, 2024*
