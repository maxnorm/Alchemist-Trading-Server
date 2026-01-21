# Phase 5: React Dashboard Implementation

## Overview

Phase 5 implements the complete React dashboard UI that serves as the control center for The Alchemist platform. This dashboard enables users to create experiments, configure hyperparameters, monitor training in real-time, manage model lifecycle, control live trading, and view performance metrics.

## Architecture

The React dashboard will:

- Run as a separate Docker container on port 3000
- Connect to FastAPI service (Phase 4) via REST API and WebSocket
- Use modern React patterns with TypeScript for type safety
- Implement 2FA for sensitive operations (model promotion, live account assignment, kill switch)
- Provide real-time updates via WebSocket channels
- Support local deployment without full authentication (2FA only for sensitive operations)

## Project Structure

```
dashboard/
├── Dockerfile
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
├── .env.example
├── public/
│   └── favicon.ico
└── src/
    ├── main.tsx                 # App entry point
    ├── App.tsx                  # Root component with routing
    ├── components/
    │   ├── ui/                  # shadcn/ui components
    │   │   ├── button.tsx
    │   │   ├── card.tsx
    │   │   ├── dialog.tsx
    │   │   ├── table.tsx
    │   │   ├── chart.tsx
    │   │   └── ...
    │   ├── Layout/
    │   │   ├── Layout.tsx       # Main layout wrapper
    │   │   ├── Sidebar.tsx      # Navigation sidebar
    │   │   ├── Header.tsx       # Top header with status
    │   │   └── Footer.tsx       # Footer component
    │   ├── charts/
    │   │   ├── EquityCurveChart.tsx
    │   │   ├── MetricsChart.tsx
    │   │   └── PerformanceChart.tsx
    │   └── common/
    │       ├── LoadingSpinner.tsx
    │       ├── ErrorBoundary.tsx
    │       └── Toast.tsx
    ├── pages/
    │   ├── ExperimentBuilder.tsx
    │   ├── HyperparameterSearch.tsx
    │   ├── TrainingMonitor.tsx
    │   ├── FeatureCatalog.tsx
    │   ├── ModelRegistry.tsx
    │   ├── LiveTrading.tsx
    │   ├── MT5Accounts.tsx
    │   ├── PortfolioPerformance.tsx
    │   └── ModelPerformance.tsx
    ├── services/
    │   ├── api.ts               # Axios API client
    │   ├── websocket.ts         # WebSocket client
    │   └── 2fa.ts               # 2FA service for sensitive operations
    ├── stores/
    │   ├── experimentStore.ts
    │   ├── modelStore.ts
    │   ├── tradingStore.ts
    │   └── uiStore.ts
    ├── hooks/
    │   ├── useExperiments.ts
    │   ├── useModels.ts
    │   ├── useWebSocket.ts
    │   └── use2FA.ts
    ├── types/
    │   ├── experiment.ts
    │   ├── model.ts
    │   ├── feature.ts
    │   ├── trading.ts
    │   └── performance.ts
    └── utils/
        ├── formatters.ts
        ├── validators.ts
        └── constants.ts
```

## Dependencies

### Core Framework

- **Vite** (5.x) - Build tool and dev server
- **React** (18.x) - UI framework
- **TypeScript** (5.x) - Type safety
- **React Router** (6.x) - Client-side routing

### UI & Styling

- **Tailwind CSS** (3.x) - Utility-first CSS
- **shadcn/ui** - High-quality component library
- **Lucide React** - Icon library
- **clsx** - Conditional class names

### State Management

- **Zustand** (4.x) - Lightweight state management
- **TanStack Query** (5.x) - Server state management and caching

### Charts & Visualization

- **Lightweight Charts** (4.x) - TradingView charts for equity curves
- **Recharts** (2.x) - React charts for metrics visualization

### HTTP & WebSocket

- **Axios** (1.x) - HTTP client
- **ws** (8.x) - WebSocket client (or native browser WebSocket API)

### Forms & Validation

- **React Hook Form** (7.x) - Form management
- **Zod** (3.x) - Schema validation

### Utilities

- **date-fns** (3.x) - Date formatting
- **react-hot-toast** (2.x) - Toast notifications

## Implementation Tasks

### 5.1 Project Setup

**File**: `dashboard/package.json`, `dashboard/vite.config.ts`

- Initialize Vite project with React + TypeScript template
- Configure Tailwind CSS with custom theme
- Set up shadcn/ui component library
- Configure path aliases (`@/components`, `@/services`, etc.)
- Set up environment variables for API URL

**Dependencies to install**:

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "zustand": "^4.4.7",
    "@tanstack/react-query": "^5.12.0",
    "axios": "^1.6.2",
    "react-hook-form": "^7.48.2",
    "zod": "^3.22.4",
    "lightweight-charts": "^4.1.3",
    "recharts": "^2.10.3",
    "date-fns": "^3.0.0",
    "react-hot-toast": "^2.4.1",
    "lucide-react": "^0.294.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.1.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.43",
    "@types/react-dom": "^18.2.17",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.8",
    "tailwindcss": "^3.3.6",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32"
  }
}
```

### 5.2 Routing Setup

**File**: `dashboard/src/App.tsx`

- Set up React Router with routes for all pages
- Implement route protection (if needed for future)
- Add navigation guards for sensitive operations
- Configure route-based code splitting (lazy loading)

**Routes**:

- `/` - Dashboard home (redirects to experiments)
- `/experiments` - Experiment Builder
- `/experiments/:id` - Experiment details
- `/hyperparameters` - Hyperparameter Search
- `/training` - Training Monitor
- `/features` - Feature Catalog
- `/models` - Model Registry
- `/trading` - Live Trading
- `/accounts` - MT5 Accounts
- `/performance` - Portfolio Performance
- `/performance/:modelId` - Model Performance

### 5.3 API Client Service

**File**: `dashboard/src/services/api.ts`

- Create Axios instance with base URL from environment
- Set up request/response interceptors
- Implement error handling and retry logic
- Add request cancellation support
- Type-safe API methods for all endpoints

**Key Methods**:

```typescript
// Features
getFeatures(filters?: FeatureFilters): Promise<Feature[]>
getFeature(id: number): Promise<Feature>

// Experiments
getExperiments(): Promise<Experiment[]>
createExperiment(data: CreateExperimentDto): Promise<Experiment>
startExperiment(id: number): Promise<void>
stopExperiment(id: number): Promise<void>
cloneExperiment(id: number): Promise<Experiment>

// Hyperparameters
startOptunaSearch(experimentId: number, config: OptunaConfig): Promise<Study>
getOptunaStatus(experimentId: number): Promise<StudyStatus>
getOptunaTrials(experimentId: number): Promise<Trial[]>

// Models
getModels(): Promise<Model[]>
promoteModel(modelId: number, stage: ModelStage, totpCode: string): Promise<Model>
rollbackModel(modelId: number, totpCode: string): Promise<Model>

// Trading
getTradingStatus(): Promise<TradingStatus>
triggerKillSwitch(totpCode: string): Promise<void>
resetKillSwitch(totpCode: string): Promise<void>
getCircuitBreakerStatus(): Promise<CircuitBreakerStatus>

// MT5 Accounts
getMT5Accounts(): Promise<MT5Account[]>
assignModel(accountId: number, modelId: number, totpCode: string): Promise<void>
pauseTrading(accountId: number): Promise<void>
resumeTrading(accountId: number): Promise<void>

// Performance
getPortfolioMetrics(period: string): Promise<PortfolioMetrics>
getModelMetrics(modelId: number, period: string): Promise<ModelMetrics>
getEquityCurve(modelId?: number, period: string): Promise<EquityPoint[]>
```

### 5.4 WebSocket Client Service

**File**: `dashboard/src/services/websocket.ts`

- Create WebSocket connection manager
- Implement reconnection logic
- Handle channel subscriptions
- Type-safe message handling
- Connection state management

**WebSocket Channels** (from Phase 4):

- `/ws/experiments/{id}/progress` - Training progress updates
- `/ws/training/metrics` - Real-time training metrics
- `/ws/optuna/{studyId}/trials` - Optuna trial updates
- `/ws/trading/status` - Trading status changes
- `/ws/trading/positions` - Position updates
- `/ws/performance/updates` - Performance metric updates
- `/ws/alerts` - System alerts and notifications

**Implementation**:

```typescript
class WebSocketService {
  connect(): void
  disconnect(): void
  subscribe(channel: string, callback: (data: any) => void): () => void
  unsubscribe(channel: string): void
  send(channel: string, message: any): void
}
```

### 5.5 2FA Service

**File**: `dashboard/src/services/2fa.ts`

**Note**: For local deployment, we implement a simple TOTP-based 2FA for sensitive operations only. No full authentication system required.

- Generate TOTP secret on first use (store in localStorage)
- Display QR code for TOTP setup (using authenticator apps)
- Validate TOTP codes for sensitive operations
- Store 2FA state (enabled/disabled per operation type)

**Sensitive Operations Requiring 2FA**:

- Model promotion to Production
- Model assignment to live MT5 accounts
- Kill switch trigger/reset
- Circuit breaker reset
- Model rollback

**Implementation**:

```typescript
class TwoFactorService {
  generateSecret(): string
  getQRCode(secret: string, label: string): string
  verifyCode(secret: string, code: string): boolean
  isEnabled(): boolean
  enable(secret: string): void
  disable(): void
}
```

### 5.6 State Management

**Files**: `dashboard/src/stores/*.ts`

Use Zustand for global client state:

**experimentStore.ts**:

- Active experiments list
- Selected experiment
- Experiment status updates

**modelStore.ts**:

- Models list
- Model lifecycle state
- Promotion history

**tradingStore.ts**:

- Trading status (active/paused)
- Kill switch state
- Circuit breaker state
- Active positions

**uiStore.ts**:

- Theme (light/dark)
- Sidebar collapsed state
- Toast notifications queue
- Loading states

### 5.7 Layout Component

**File**: `dashboard/src/components/Layout/Layout.tsx`

- Main layout wrapper with sidebar and header
- Responsive design (mobile sidebar collapse)
- Navigation menu with active route highlighting
- Status indicators in header (trading status, kill switch, etc.)
- Breadcrumb navigation

**Sidebar Navigation**:

- 🧪 Experiments
- 🔍 Hyperparameter Search
- 📊 Training Monitor
- 📋 Feature Catalog
- 🤖 Model Registry
- 💹 Live Trading
- 🏦 MT5 Accounts
- 📈 Performance

### 5.8 Experiment Builder Page

**File**: `dashboard/src/pages/ExperimentBuilder.tsx`

**Features**:

- Multi-select feature picker with search and filtering
- Currency pair selection (multi-select)
- Training mode selection (Live Training / Historical Backtest)
- Hyperparameter configuration:
    - Manual mode: Form inputs for all hyperparameters
    - Optuna mode: Link to Hyperparameter Search page
- Form validation with Zod schemas
- Save draft functionality
- Start training button

**UI Components**:

- Feature selection with categories and sources
- Currency pair chips
- Training mode toggle
- Hyperparameter form sections
- Action buttons (Save, Start Training, Cancel)

### 5.9 Hyperparameter Search Page

**File**: `dashboard/src/pages/HyperparameterSearch.tsx`

**Features**:

- Optuna study configuration form
- Search space definition (ranges, choices)
- Real-time trial progress (WebSocket)
- Trial results table with sorting
- Parameter importance visualization
- Best trial display with "Use These Values" button
- Study status (running/completed/failed)

**UI Components**:

- Search space builder
- Trial progress chart
- Trial results table
- Parameter importance bars
- Best trial card

### 5.10 Training Monitor Page

**File**: `dashboard/src/pages/TrainingMonitor.tsx`

**Features**:

- List of active experiments with status
- Real-time metrics charts (loss, reward, Sharpe ratio)
- Training progress indicators
- Stop/pause controls per experiment
- Experiment details modal
- MLflow run links

**UI Components**:

- Experiment cards/list
- Real-time metrics charts (Recharts)
- Progress bars
- Control buttons (Stop, Pause, Resume)

### 5.11 Feature Catalog Page

**File**: `dashboard/src/pages/FeatureCatalog.tsx`

**Features**:

- Table of all available features
- Filtering by source, category, data type
- Search functionality
- Feature details modal (description, statistics, availability)
- Availability status indicators
- Feature usage count

**UI Components**:

- Data table (shadcn/ui Table)
- Filter dropdowns
- Search input
- Feature detail modal

### 5.12 Model Registry Page

**File**: `dashboard/src/pages/ModelRegistry.tsx`

**Features**:

- List of all models with lifecycle stages
- Model cards with key metrics
- Promotion controls (with 2FA prompt)
- Rollback functionality (with 2FA prompt)
- Model comparison view
- Paper trading validation status
- MLflow links

**UI Components**:

- Model cards/list
- Stage badges (Training, Staging, Paper, Production, Archived)
- Promotion dialog with 2FA input
- Model details modal
- Comparison view

### 5.13 Live Trading Page

**File**: `dashboard/src/pages/LiveTrading.tsx`

**Features**:

- Active positions display (real-time via WebSocket)
- Kill switch controls (with 2FA prompt)
- Circuit breaker status and reset (with 2FA)
- Trade history table
- Account balance and equity
- Real-time P&L updates

**UI Components**:

- Position cards/table
- Kill switch button (prominent, red)
- Circuit breaker status indicator
- Trade history table
- Account summary cards

### 5.14 MT5 Accounts Page

**File**: `dashboard/src/pages/MT5Accounts.tsx`

**Features**:

- List of registered MT5 accounts
- Connection status indicators
- Model assignment interface (with 2FA for live accounts)
- Assignment history view
- Pause/resume trading controls
- Account details (broker, type, leverage, currency)

**UI Components**:

- Account table/cards
- Connection status badges
- Model assignment dialog
- Assignment history modal
- Control buttons (Pause, Resume, Assign)

### 5.15 Performance Pages (Basic Structure)

**Files**:

- `dashboard/src/pages/PortfolioPerformance.tsx`
- `dashboard/src/pages/ModelPerformance.tsx`

**Note**: Full implementation with all metrics and charts will be completed in Phase 6. Phase 5 implements the basic structure and layout.

**Portfolio Performance**:

- Basic layout with placeholder sections
- Time range selector
- Placeholder for equity curve chart
- Placeholder for metrics cards

**Model Performance**:

- Basic layout with model selector
- Placeholder for model equity curve
- Placeholder for trade history table
- Placeholder for metrics

### 5.16 Charts Integration

**Files**: `dashboard/src/components/charts/*.tsx`

- **EquityCurveChart.tsx**: Lightweight Charts integration for equity curves
- **MetricsChart.tsx**: Recharts for training metrics (loss, reward)
- **PerformanceChart.tsx**: Recharts for performance metrics over time

**Lightweight Charts Setup**:

```typescript
import { createChart, ColorType } from 'lightweight-charts';

// Equity curve with drawdown overlay
// Real-time updates via WebSocket
// Time range selection
```

### 5.17 Error Handling

**Files**:

- `dashboard/src/components/common/ErrorBoundary.tsx`
- `dashboard/src/utils/errorHandler.ts`

- Global error boundary for React errors
- API error handling with user-friendly messages
- Toast notifications for errors
- Retry mechanisms for failed requests
- Network error detection and handling

### 5.18 Responsive Design

- Mobile-first approach with Tailwind breakpoints
- Collapsible sidebar on mobile
- Responsive tables (horizontal scroll or card view)
- Touch-friendly controls
- Responsive charts (resize on window change)

### 5.19 Docker Setup

**File**: `dashboard/Dockerfile`

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**File**: `docker-compose.yml` (update)

```yaml
dashboard:
  build: ./dashboard
  ports:
  - "3000:80"
  environment:
  - VITE_API_URL=http://localhost:8000
  - VITE_WS_URL=ws://localhost:8000
  depends_on:
  - api
```

## Integration Points

### With Phase 4 (FastAPI)

- All REST endpoints from Phase 4
- WebSocket channels from Phase 4
- Error response formats
- Authentication headers (if needed in future)

### With Phase 3 (Experiments)

- Experiment data models
- Optuna study/trial structures
- Model registry schemas

### With Phase 6 (Performance)

- Performance metrics structures
- Equity curve data format
- Trade history schemas

## Testing Strategy

### Unit Tests

- Component tests with React Testing Library
- Service tests (API client, WebSocket)
- Store tests (Zustand)
- Utility function tests

### Integration Tests

- Page navigation flows
- Form submissions
- WebSocket message handling
- 2FA flow

### E2E Tests (Future)

- Complete experiment creation flow
- Model promotion workflow
- Trading control operations

## Success Criteria

- ✅ All pages implemented and accessible via navigation
- ✅ API integration working for all endpoints
- ✅ WebSocket real-time updates functional
- ✅ 2FA prompts appear for sensitive operations
- ✅ Responsive design works on mobile/tablet/desktop
- ✅ Error handling provides user-friendly messages
- ✅ Charts render correctly with sample data
- ✅ Docker container builds and runs successfully
- ✅ Dashboard connects to FastAPI service

## Dependencies on Previous Phases

- **Phase 4 (FastAPI)**: Required - Dashboard depends on all API endpoints
- **Phase 3 (Experiments)**: Required - Experiment and model data structures
- **Phase 2 (Data Sources)**: Required - Feature catalog data
- **Phase 1 (Safety)**: Required - Trading control endpoints

## Next Steps After Phase 5

- **Phase 6**: Complete performance pages with full metrics and charts
- **Phase 7**: Enhance model lifecycle with paper trading validation
- **Phase 8**: Testing, optimization, and polish

---

## Notes

1. **2FA Implementation**: For local deployment, we use a simple TOTP-based 2FA system stored in localStorage. No full authentication infrastructure required. Users set up 2FA once, and it's used only for sensitive operations.

2. **Performance Pages**: Phase 5 implements the basic structure of performance pages. Full implementation with all metrics, charts, and real-time updates will be completed in Phase 6.

3. **WebSocket Reconnection**: Implement exponential backoff for WebSocket reconnection to handle network issues gracefully.

4. **Error Messages**: All error messages should be user-friendly and actionable. Avoid technical jargon in user-facing errors.

5. **Loading States**: All async operations should show loading indicators. Use skeleton screens for better UX.

6. **Form Validation**: Use Zod schemas for all form validation. Show validation errors inline.

7. **Accessibility**: Ensure all interactive elements are keyboard accessible and screen reader friendly.