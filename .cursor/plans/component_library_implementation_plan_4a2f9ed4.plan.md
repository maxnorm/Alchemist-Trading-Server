---
name: Component Library Implementation Plan
overview: Systematic plan to build all design system components with priority-based implementation, proper TypeScript types, and seamless API/mock integration using a service abstraction layer.
todos: []
---

# Component Library Implementation Plan

## Architecture Overview

### Service Abstraction Layer

Create a service abstraction that allows seamless switching between real API and mocks:

```
src/dashboard/src/
├── services/
│   ├── api.ts (existing - real API client)
│   ├── api-mock.ts (new - mock API client)
│   ├── api-factory.ts (new - factory to switch between real/mock)
│   └── websocket-mock.ts (new - mock WebSocket service)
├── types/
│   ├── market.ts (new - market data types)
│   ├── orders.ts (new - order management types)
│   ├── charts.ts (new - chart data types)
│   └── ... (extend existing types)
└── components/
    ├── trading/ (new)
    ├── ml/ (new)
    ├── charts/ (expand)
    └── forms/ (expand)
```

### Type System Strategy

- All components use shared TypeScript types from `types/` directory
- Mock services return the same types as real API
- Types are defined before component implementation
- Use discriminated unions for variant types (e.g., order types)

### Mock Service Pattern

- Mock services implement the same interface as real API
- Use in-memory state for persistence during session
- WebSocket mocks use `setInterval` to simulate real-time updates
- Environment variable `VITE_USE_MOCK_API=true` to enable mocks

### Design System Compliance

All components MUST follow the terminal/print aesthetic design system:

**Color System:**

- Monochrome base: Use `mono-100` to `mono-800` CSS variables
- Orange accent: Use `orange-400` for focus, active states, primary actions only
- Never hard-code hex values - always use CSS variables or Tailwind tokens
- Status colors: Use semantic tokens (success, warning, destructive, info)

**Typography:**

- Numeric data: Use `font-mono-data` class for tabular numbers
- Technical labels: Use `text-technical` utility (uppercase, tracked)
- Body text: Default system font with tabular number support

**Density Variants:**

- All components support: `comfortable` (1.5rem), `dense` (1rem - default), `ultra-dense` (0.5rem)
- Default to `dense` for dashboard layouts
- Use `comfortable` for forms and detail pages

**Animations:**

- Use GSAP with `useGSAP` hook for entrance animations
- Apply to panels/cards, NOT to dense data (tables, lists)
- Respect `prefers-reduced-motion` - disable animations if user prefers
- Use motion tokens from `src/styles/motion.ts`

**Textures:**

- Halftone patterns: Use sparingly in page headers, empty states, side panels
- Forbidden: Tables, chart plot areas, dense text blocks

**Focus States:**

- All interactive elements have visible orange focus rings
- Use `focus:ring-2 focus:ring-orange-400`
- Never disable focus styles

**Theme Support:**

- All components automatically adapt to dark/light mode via CSS variables
- Test in both themes
- Orange accent adjusts for contrast in light mode

---

## Phase 1: Foundation & Types (Week 1)

### 1.1 Create Missing Type Definitions

**Files to create:**

- `src/dashboard/src/types/market.ts` - Market data types (OrderBook, PriceTick, OHLC, etc.)
- `src/dashboard/src/types/orders.ts` - Order management types (Order, OrderType, OrderStatus, etc.)
- `src/dashboard/src/types/charts.ts` - Chart data types (ChartPoint, CandleData, etc.)
- `src/dashboard/src/types/training.ts` - Training metrics types (TrainingMetrics, LogEntry, etc.)
- `src/dashboard/src/types/resources.ts` - Resource monitoring types (ResourceUsage, etc.)

**Key types to define:**

```typescript
// market.ts
export interface OrderBookEntry { price: number; volume: number }
export interface OrderBook { bids: OrderBookEntry[]; asks: OrderBookEntry[] }
export interface PriceTick { symbol: string; bid: number; ask: number; time: string }
export interface OHLC { open: number; high: number; low: number; close: number; time: string }

// orders.ts
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit'
export type OrderSide = 'buy' | 'sell'
export interface Order { id: number; symbol: string; type: OrderType; side: OrderSide; ... }

// charts.ts
export interface ChartPoint { x: number | string; y: number }
export interface CandleData extends OHLC { volume?: number }
```

### 1.2 Create Mock Service Infrastructure

**Files to create:**

- `src/dashboard/src/services/api-mock.ts` - Mock API client implementing same interface as `api.ts`
- `src/dashboard/src/services/api-factory.ts` - Factory to return real or mock API based on config
- `src/dashboard/src/services/websocket-mock.ts` - Mock WebSocket service with simulated updates

**Implementation pattern:**

```typescript
// api-factory.ts
const useMock = import.meta.env.VITE_USE_MOCK_API === 'true'
export const api = useMock ? createMockApi() : createRealApi()

// api-mock.ts
class MockApiClient {
  private orderBookData: Map<string, OrderBook> = new Map()
  private orders: Order[] = []
  // ... in-memory state
  
  async getOrderBook(symbol: string): Promise<OrderBook> {
    // Return mock data matching real API response type
  }
}
```

### 1.3 Extend Existing API Client

**File to modify:** `src/dashboard/src/services/api.ts`

- Add methods for new endpoints (order book, historical data, etc.)
- Methods should match mock API interface exactly
- Use existing patterns (axios, error handling, token injection)

---

## Phase 2: P0 Trading Components (Weeks 2-3)

### 2.1 PositionTable (Enhanced)

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/trading/PositionTable.tsx`

**Implementation:**

- Use existing `GET /api/trading/positions` endpoint
- Integrate WebSocket `/ws/positions` for real-time updates
- Add actions: close position, modify stop loss/take profit (if API supports)
- Use `DataTable` component as base with `density="dense"` default
- Add P&L color coding using semantic status colors (not hard-coded green/red)
- Use `font-mono-data` for all numeric values
- Type: `Position[]` from `types/trading.ts`

**Design System:**

- Density: `dense` (default)
- Numbers: Monospace font
- Status colors: Use semantic tokens for P&L indicators
- Focus: Orange ring on interactive rows

**Mock support:**

- Generate mock positions with realistic P&L values
- Simulate price updates via WebSocket mock

### 2.2 TradeHistory

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/trading/TradeHistory.tsx`

**Implementation:**

- Use `GET /api/trading/history` with filters
- Add filtering: symbol, date range, experiment_id
- Pagination support
- Export functionality
- Type: `Trade[]` from `types/performance.ts`

**Mock support:**

- Generate historical trades with realistic timestamps
- Support all filter parameters

### 2.3 PortfolioSummaryCard

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/trading/PortfolioSummaryCard.tsx`

**Implementation:**

- Use `GET /api/performance/portfolio`
- Use `GET /api/trading/status` for equity/balance
- Display: total equity, P&L, Sharpe ratio, max drawdown
- Use `KPICard` component for individual metrics
- Type: `PortfolioMetrics` from `types/performance.ts`

**Mock support:**

- Generate realistic portfolio metrics
- Simulate real-time equity updates

### 2.4 DrawdownChart

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/charts/DrawdownChart.tsx`

**Implementation:**

- Use `GET /api/performance/portfolio/equity-curve`
- Calculate drawdown from equity curve data
- Use Recharts for visualization
- Show underwater equity curve
- Type: `EquityPoint[]` from `types/performance.ts`

**Mock support:**

- Generate equity curve with realistic drawdown patterns

### 2.5 PriceTicker

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/trading/PriceTicker.tsx`

**Implementation:**

- Subscribe to WebSocket `/ws/ticks`
- Display: symbol, bid, ask, change, change %
- Animate price changes (green up, red down)
- Support multiple symbols
- Type: `PriceTick` from `types/market.ts`

**Mock support:**

- Simulate price ticks with random walk
- Update every 1-2 seconds

### 2.6 TimeAndSales

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/trading/TimeAndSales.tsx`

**Implementation:**

- Subscribe to WebSocket `/ws/trades` for real-time
- Use `GET /api/trading/history` for historical
- Display: time, symbol, price, volume, side
- Auto-scroll to latest trade
- Type: `Trade[]` from `types/performance.ts`

**Mock support:**

- Simulate trade feed with realistic intervals

---

## Phase 3: P0 ML Components (Weeks 4-5)

### 3.1 ExperimentListTable

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/ExperimentListTable.tsx`

**Implementation:**

- Use `GET /api/experiments` with status filter
- Sortable columns: name, status, created_at, metrics
- Row click to navigate to detail
- Use `DataTable` component
- Type: `Experiment[]` from `types/experiment.ts`

**Mock support:**

- Generate experiments with various statuses

### 3.2 TrainingMetricsChart

**Status:** ⚠️ Partial API (real-time only)

**File:** `src/dashboard/src/components/ml/TrainingMetricsChart.tsx`

**Implementation:**

- Subscribe to WebSocket `/ws/training` for real-time
- Multi-metric line chart (loss, reward, Sharpe, etc.)
- Metric selection toggle
- Smoothing slider
- Use Recharts LineChart
- Type: `TrainingMetrics[]` from `types/training.ts`

**Mock support:**

- Simulate training progress with decreasing loss
- Generate historical data if endpoint added later

### 3.3 HyperparameterSearchProgress

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/HyperparameterSearchProgress.tsx`

**Implementation:**

- Use `GET /api/hyperparameters/search/{id}`
- Subscribe to WebSocket `/ws/optuna`
- Progress bar: trials completed / total trials
- Display best value and parameters
- Type: `OptunaStudy` from `types/optuna.ts`

**Mock support:**

- Simulate trial progress over time

### 3.4 ParameterImportanceChart

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/ParameterImportanceChart.tsx`

**Implementation:**

- Use `GET /api/hyperparameters/search/{id}/importance`
- Horizontal bar chart showing importance scores
- Use Recharts BarChart
- Type: `ParameterImportanceResponse` from `types/optuna.ts`

**Mock support:**

- Generate importance scores for all parameters

### 3.5 ModelRegistryTable

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/ModelRegistryTable.tsx`

**Implementation:**

- Use `GET /api/models` with stage filter
- Sortable columns: version, stage, experiment_id, metrics
- Stage badges with colors
- Row click for details
- Type: `Model[]` from `types/model.ts`

**Mock support:**

- Generate models in different stages

### 3.6 ModelPerformanceMetrics

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/ModelPerformanceMetrics.tsx`

**Implementation:**

- Use `GET /api/performance/models/{model_id}`
- Display: Sharpe ratio, win rate, P&L, drawdown
- Use `KPICard` components
- Type: `ModelMetrics` from `types/performance.ts`

**Mock support:**

- Generate realistic performance metrics

---

## Phase 4: Chart Components (Week 6)

### Chart Design System Guidelines

All chart components MUST follow these design system rules:

**Colors:**

- Primary line/bar: Monochrome (`mono-400` to `mono-600`)
- Accent/highlight: Orange (`orange-400`) for key data points, best values
- Multiple series: Use monochrome shades (lighter to darker)
- Background: `mono-200` (dark mode) or `mono-100` (light mode)
- Grid lines: `mono-300` (subtle)
- No halftone textures in plot areas

**Typography:**

- Axis labels: `text-technical` (uppercase, tracked)
- Axis values: `font-mono-data` (monospace, tabular)
- Tooltip values: `font-mono-data`
- Chart title: Default system font

**Density:**

- Default: `dense` for dashboard charts
- `comfortable` for detail/analysis views
- Chart padding adapts to density

**Animations:**

- Entrance: Use `AnimatedPanel` wrapper (not on chart itself)
- Data updates: Subtle fade (respects reduced motion)
- No animations on data points during real-time updates

### 4.1 LineChart (Generic)

**Status:** ✅ Data Available

**File:** `src/dashboard/src/components/charts/LineChart.tsx`

**Implementation:**

- Generic reusable component using Recharts
- Props: `data: ChartPoint[]`, `xKey`, `yKey`, `color`, `density`, etc.
- Support multiple series
- Tooltip, legend, zoom
- Custom theme matching design system
- Type: `ChartPoint[]` from `types/charts.ts`

**Design System:**

- Colors: Monochrome lines with orange accent for highlights
- Typography: Monospace for values, technical for labels
- Density: `dense` default, supports all variants
- Theme: Custom Recharts theme matching terminal aesthetic

**Usage:**

- Equity curves, training metrics, optimization history

### 4.2 ScatterPlot

**Status:** ✅ Data Available

**File:** `src/dashboard/src/components/charts/ScatterPlot.tsx`

**Implementation:**

- Use Recharts ScatterChart
- Props: `data`, `xKey`, `yKey`, `colorKey`, `density`
- Tooltip with full data point info
- Custom theme matching design system
- Type: Generic data points

**Design System:**

- Points: Monochrome with orange accent for selected/highlighted
- Typography: Monospace for tooltip values
- Density: `dense` default

**Usage:**

- Parameter vs. metric relationships
- Trade analysis

### 4.3 Histogram

**Status:** ✅ Data Available

**File:** `src/dashboard/src/components/charts/Histogram.tsx`

**Implementation:**

- Use Recharts BarChart configured as histogram
- Calculate bins from data
- Props: `data`, `valueKey`, `bins`, `density`
- Custom theme matching design system
- Type: Generic numeric array

**Design System:**

- Bars: Monochrome with orange accent for mean/median indicator
- Typography: Monospace for bin values
- Density: `dense` default

**Usage:**

- Parameter distributions
- Trade P&L distribution

### 4.4 BarChart

**Status:** ✅ Data Available

**File:** `src/dashboard/src/components/charts/BarChart.tsx`

**Implementation:**

- Use Recharts BarChart
- Props: `data`, `xKey`, `yKey`, `orientation`, `density`
- Support grouped/stacked bars
- Custom theme matching design system
- Type: Generic categorical data

**Design System:**

- Bars: Monochrome with orange accent for highest value
- Typography: Monospace for values, technical for labels
- Density: `dense` default

**Usage:**

- Performance breakdown
- Allocation by pair/model

### 4.5 DistributionPlot

**Status:** ✅ Data Available

**File:** `src/dashboard/src/components/charts/DistributionPlot.tsx`

**Implementation:**

- Combine Histogram with density curve
- Use Recharts AreaChart for smooth curve
- Props: `data`, `density`
- Custom theme matching design system
- Type: Generic numeric array

**Design System:**

- Histogram: Monochrome bars
- Density curve: Orange accent line
- Typography: Monospace for values
- Density: `dense` default

**Usage:**

- Trade P&L distribution
- Parameter value distributions

---

## Phase 5: P0 Missing API Components (Week 7)

### 5.1 OrderBook (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/trading/OrderBook.tsx`

**Implementation:**

- Mock service only (no real API)
- Display bids/asks with depth
- Cumulative volume bars
- Click price to fill order form
- Real-time updates via WebSocket mock
- Type: `OrderBook` from `types/market.ts`

**Mock support:**

- Generate realistic order book with spread
- Simulate order book updates

### 5.2 PriceChart (Real-time Only)

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/trading/PriceChart.tsx`

**Implementation:**

- Real-time line chart from WebSocket `/ws/ticks`
- Use Lightweight Charts (TradingView) for better performance
- Support timeframes (if historical API added later)
- Mock historical data for development
- Type: `PriceTick[]` or `OHLC[]` from `types/market.ts`

**Mock support:**

- Generate OHLC data from tick data
- Simulate price movements

### 5.3 TrainingLogViewer (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/ml/TrainingLogViewer.tsx`

**Implementation:**

- Mock service only
- Scrollable log output
- Filter by log level (INFO, WARNING, ERROR)
- Auto-scroll to bottom
- Search functionality
- Type: `LogEntry[]` from `types/training.ts`

**Mock support:**

- Generate realistic training logs
- Simulate log streaming

---

## Phase 6: P1 Components (Weeks 8-9)

### 6.1 ExperimentComparison

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/ml/ExperimentComparison.tsx`

**Implementation:**

- Fetch multiple experiments: `GET /api/experiments`
- Fetch model performance for each: `GET /api/performance/models`
- Side-by-side metric comparison table
- Highlight best/worst values
- Type: `Experiment[]` + `ModelMetrics[]`

**Mock support:**

- Generate comparison data

### 6.2 ModelVersionComparison

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/ml/ModelVersionComparison.tsx`

**Implementation:**

- Fetch multiple models: `GET /api/models`
- Fetch performance for each: `GET /api/performance/models/{id}`
- Comparison table with diff highlighting
- Type: `Model[]` + `ModelMetrics[]`

**Mock support:**

- Generate version comparison data

### 6.3 PnLBreakdown

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/trading/PnLBreakdown.tsx`

**Implementation:**

- Use `GET /api/performance/portfolio/breakdown`
- Use `GET /api/trading/positions` for unrealized
- Use `GET /api/trading/history` for realized
- Display: realized vs. unrealized, by period
- Type: `PerformanceBreakdown[]` + `Position[]` + `Trade[]`

**Mock support:**

- Generate breakdown data

### 6.4 TradeDistributionChart

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/trading/TradeDistributionChart.tsx`

**Implementation:**

- Use `GET /api/trading/history`
- Calculate win/loss distribution
- Use Histogram component
- Show win rate, average win/loss
- Type: `Trade[]` from `types/performance.ts`

**Mock support:**

- Generate trade distribution

### 6.5 FeatureCatalogTable

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/FeatureCatalogTable.tsx`

**Implementation:**

- Use `GET /api/features`
- Sortable, filterable table
- Feature metadata display
- Type: `Feature[]` from `types/feature.ts`

**Mock support:**

- Generate feature catalog

---

## Phase 7: Form Components (Week 10)

### 7.1 Select (Enhanced Dropdown)

**File:** `src/dashboard/src/components/forms/Select.tsx`

- Based on shadcn/ui select
- Support multi-select variant
- Search/filter options
- Type: Generic with type parameters

### 7.2 Slider

**File:** `src/dashboard/src/components/forms/Slider.tsx`

- Range input for parameters
- Min/max/step props
- Value display
- Type: `number`

### 7.3 Toggle

**File:** `src/dashboard/src/components/forms/Toggle.tsx`

- Switch component
- On/off states
- Type: `boolean`

### 7.4 DatePicker

**File:** `src/dashboard/src/components/forms/DatePicker.tsx`

- Date selection
- Range selection support
- Use date-fns (already installed)
- Type: `Date | DateRange`

### 7.5 MultiSelect

**File:** `src/dashboard/src/components/forms/MultiSelect.tsx`

- Multiple option selection
- Tag display for selected items
- Search functionality
- Type: `T[]` generic

---

## Phase 8: Feedback Components (Week 11)

### 8.1 Alert

**File:** `src/dashboard/src/components/feedback/Alert.tsx`

- Alert banner component
- Variants: success, warning, error, info
- Dismissible
- Type: Alert props

### 8.2 ConfirmDialog

**File:** `src/dashboard/src/components/feedback/ConfirmDialog.tsx`

- Confirmation modal
- Title, message, confirm/cancel actions
- Use shadcn/ui dialog
- Type: Dialog props

### 8.3 ProgressBar

**File:** `src/dashboard/src/components/feedback/ProgressBar.tsx`

- Progress indicator
- Percentage display
- Variants: default, success, warning
- Type: `{ value: number; max?: number }`

### 8.4 NotificationCenter

**File:** `src/dashboard/src/components/feedback/NotificationCenter.tsx`

- Notification management panel
- List of notifications
- Mark as read, clear all
- Type: `Notification[]`

---

## Phase 9: Advanced Components (Weeks 12-13)

### 9.1 Watchlist (Basic - No Persistence)

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/trading/Watchlist.tsx`

**Implementation:**

- Use `GET /api/trading/currency-pairs` for available symbols
- Client-side state (no persistence)
- Add/remove symbols
- Display prices from PriceTicker
- Type: `string[]` (symbols)

**Note:** Full persistence requires API endpoint

### 9.2 RiskMetricsPanel (Basic)

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/trading/RiskMetricsPanel.tsx`

**Implementation:**

- Use `GET /api/performance/portfolio` for basic metrics
- Use `GET /api/trading/positions` for exposure calculation
- Display: current exposure, leverage (if calculable)
- Type: `PortfolioMetrics` + `Position[]`

**Note:** Advanced metrics (VaR) require API endpoint

### 9.3 ResourceMonitor (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/ml/ResourceMonitor.tsx`

**Implementation:**

- Mock service only
- Display: CPU, GPU, memory usage
- Real-time updates via WebSocket mock
- Type: `ResourceUsage` from `types/resources.ts`

**Mock support:**

- Simulate resource usage with realistic patterns

### 9.4 Hyperparameter Visualization Components

**Files:**

- `src/dashboard/src/components/ml/ParameterDistributionChart.tsx`
- `src/dashboard/src/components/ml/OptimizationHistoryChart.tsx`
- `src/dashboard/src/components/ml/ParallelCoordinatePlot.tsx`
- `src/dashboard/src/components/ml/ContourPlot.tsx`

**Implementation:**

- Use `GET /api/hyperparameters/search/{id}/trials`
- Transform trial data for each visualization
- Use Recharts or Plotly.js for complex plots
- Type: `OptunaTrial[]` from `types/optuna.ts`

**Design System:**

- Chart colors: Monochrome with orange accent for highlights
- Axis labels: Use `text-technical` for technical labels
- Numbers: Monospace font for axis values
- Background: No halftone textures in plot areas

**Mock support:**

- Generate trial data with various parameter combinations

---

## Phase 10: P1 Remaining Components (Weeks 14-15)

### 10.1 OrderEntryForm (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/trading/OrderEntryForm.tsx`

**Implementation:**

- Mock service only (no real API)
- Order type selector: market, limit, stop, stop_limit
- Quantity input with position size calculator
- Price input (for limit/stop orders)
- Risk warning for large positions
- 2FA confirmation for production orders
- Type: `Order` from `types/orders.ts`

**Design System:**

- Density: `comfortable` (form layout)
- Form fields: Use shadcn/ui Input with design system styling
- Buttons: Orange accent for primary action
- Focus: Orange ring on all inputs

**Mock support:**

- Simulate order placement with validation
- Generate order confirmation

### 10.2 OrderManagementTable (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/trading/OrderManagementTable.tsx`

**Implementation:**

- Mock service only
- Display pending orders with modify/cancel actions
- Use `DataTable` component
- Real-time updates via WebSocket mock
- Type: `Order[]` from `types/orders.ts`

**Design System:**

- Density: `dense` (default)
- Numbers: Monospace font
- Actions: Orange accent for primary actions

**Mock support:**

- Generate pending orders
- Simulate order execution/cancellation

### 10.3 QuickOrderPanel

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/trading/QuickOrderPanel.tsx`

**Implementation:**

- One-click order placement
- Compact form layout
- Pre-filled common order types
- Type: `Order` from `types/orders.ts`

**Design System:**

- Density: `ultra-dense` (compact panel)
- Orange accent for quick action buttons

**Mock support:**

- Simulate quick order placement

### 10.4 OrderConfirmationDialog

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/trading/OrderConfirmationDialog.tsx`

**Implementation:**

- 2FA-protected order confirmation
- Display order details
- TOTP code input
- Use shadcn/ui Dialog
- Type: `Order` + confirmation props

**Design System:**

- Dialog: Monochrome background with orange accent for confirm button
- Focus: Orange ring on TOTP input

**Mock support:**

- Simulate 2FA validation

### 10.5 PositionSizeCalculator

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/trading/PositionSizeCalculator.tsx`

**Implementation:**

- Client-side calculation (no API needed)
- Use `GET /api/trading/status` for equity/balance
- Risk-based position sizing
- Display: position size, risk amount, margin required
- Type: Calculator props

**Design System:**

- Density: `comfortable` (form layout)
- Numbers: Monospace font for all calculations
- Orange accent for calculate button

**Mock support:**

- Use mock equity data if API unavailable

### 10.6 WebSocketStatusIndicator

**Status:** ✅ Available (Client-side)

**File:** `src/dashboard/src/components/trading/WebSocketStatusIndicator.tsx`

**Implementation:**

- Monitor WebSocket connection state
- Display: connected, disconnected, reconnecting
- Use `HealthDot` component for status
- Type: Connection status props

**Design System:**

- Use `HealthDot` with appropriate status
- Orange accent when connected

### 10.7 DataLatencyMonitor

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/trading/DataLatencyMonitor.tsx`

**Implementation:**

- Calculate latency client-side from WebSocket timestamps
- Display: average latency, max latency, connection quality
- Real-time updates
- Type: Latency metrics

**Design System:**

- Density: `dense`
- Numbers: Monospace font
- Status colors: Green (good), orange (warning), red (poor)

**Mock support:**

- Simulate latency metrics

### 10.8 MarketStatusBadge (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/trading/MarketStatusBadge.tsx`

**Implementation:**

- Mock service only
- Display market open/closed status
- Use `StatusBadge` component
- Type: Market status props

**Design System:**

- Use `StatusBadge` with severity variants
- Orange accent for active market

**Mock support:**

- Simulate market hours (e.g., Forex 24/5)

### 10.9 LivePriceUpdate

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/trading/LivePriceUpdate.tsx`

**Implementation:**

- Subscribe to WebSocket `/ws/ticks`
- Animate price changes (fade/flash)
- Color coding: green up, red down
- Type: `PriceTick` from `types/market.ts`

**Design System:**

- Numbers: Monospace font
- Animation: Subtle fade (respects reduced motion)
- Status colors: Semantic for up/down

**Mock support:**

- Simulate price updates with animation

### 10.10 ExperimentTags (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/ml/ExperimentTags.tsx`

**Implementation:**

- Mock service only
- Tagging system for experiments
- Add/remove tags
- Filter by tags
- Type: `Tag[]` from `types/experiment.ts`

**Design System:**

- Tags: Monochrome background with orange accent on hover
- Density: `dense`

**Mock support:**

- Client-side tag storage (localStorage)

### 10.11 ModelArtifactBrowser (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/ml/ModelArtifactBrowser.tsx`

**Implementation:**

- Mock service only
- Browse saved model files
- File tree view
- Download artifacts
- Type: `Artifact[]` from `types/model.ts`

**Design System:**

- Density: `dense`
- File tree: Monochrome with orange accent for selected items
- Icons: Lucide icons

**Mock support:**

- Generate mock artifact list

### 10.12 FeatureImportanceChart (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/ml/FeatureImportanceChart.tsx`

**Implementation:**

- Mock service only
- Display feature importance scores
- Horizontal bar chart
- Use Recharts BarChart
- Type: `FeatureImportance[]` from `types/feature.ts`

**Design System:**

- Chart: Monochrome bars with orange accent for top features
- Numbers: Monospace font

**Mock support:**

- Generate importance scores

### 10.13 ExperimentCard

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/ExperimentCard.tsx`

**Implementation:**

- Use `GET /api/experiments/{id}`
- Compact experiment summary
- Key metrics display
- Use `DenseCard` component
- Type: `Experiment` from `types/experiment.ts`

**Design System:**

- Density: `dense`
- Use `KPICard` for metrics
- Orange accent for primary action

### 10.14 ExperimentDetailView

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/ExperimentDetailView.tsx`

**Implementation:**

- Use `GET /api/experiments/{id}`
- Use `GET /api/experiments/{id}/optuna/status`
- Use `GET /api/performance/models?experiment_id={id}`
- Full experiment information
- Related models display
- Type: `Experiment` + related data

**Design System:**

- Density: `comfortable` (detail page)
- Use `PageHeader` for title
- Use `DenseCard` for sections

### 10.15 ExperimentSearchFilter

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/ExperimentSearchFilter.tsx`

**Implementation:**

- Use `GET /api/experiments?status={status}`
- Advanced filtering UI
- Search by name, date range
- Use `FilterBar` component
- Type: Filter props

**Design System:**

- Use `FilterBar` component
- Density: `dense`

### 10.16 RealTimeMetricsDashboard

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/RealTimeMetricsDashboard.tsx`

**Implementation:**

- Subscribe to WebSocket `/ws/training`
- Subscribe to WebSocket `/ws/metrics`
- Live training metrics display
- Use `KPICard` components
- Type: `TrainingMetrics` from `types/training.ts`

**Design System:**

- Density: `dense`
- Use `KPICard` grid layout
- Numbers: Monospace font

### 10.17 TrainingStatusBadge

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/TrainingStatusBadge.tsx`

**Implementation:**

- Use `GET /api/experiments/{id}` for status
- Display: running, paused, completed, failed
- Use `StatusBadge` component
- Type: Training status props

**Design System:**

- Use `StatusBadge` with severity variants

### 10.18 EpochProgressBar

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/ml/EpochProgressBar.tsx`

**Implementation:**

- Subscribe to WebSocket `/ws/training` for progress
- Display: step/episode progress
- Use `ProgressBar` component
- Type: Progress props

**Design System:**

- Use `ProgressBar` component
- Orange accent for progress fill

### 10.19 HyperparameterDisplay

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/HyperparameterDisplay.tsx`

**Implementation:**

- Use `GET /api/experiments/{id}` for config
- Use `GET /api/hyperparameters/search/{id}` for best params
- Display current hyperparameter values
- Use `DataTable` or list format
- Type: Hyperparameter config

**Design System:**

- Density: `dense`
- Numbers: Monospace font
- Use `DenseCard` for grouping

### 10.20 TrialComparisonTable

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/TrialComparisonTable.tsx`

**Implementation:**

- Use `GET /api/hyperparameters/search/{id}/trials`
- Compare trial results side-by-side
- Sortable columns
- Use `DataTable` component
- Type: `OptunaTrial[]` from `types/optuna.ts`

**Design System:**

- Density: `dense`
- Numbers: Monospace font
- Highlight best trial with orange accent

### 10.21 ModelDeploymentStatus

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/ModelDeploymentStatus.tsx`

**Implementation:**

- Use `GET /api/models/{model_id}` for stage
- Use `GET /api/models/{model_id}/validation` for validation
- Subscribe to WebSocket `/ws/models/{model_id}/status`
- Display deployment status
- Type: Model deployment status

**Design System:**

- Use `StatusBadge` for stage indicators
- Use `HealthDot` for validation status

### 10.22 ModelLifecycleWorkflow

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/ModelLifecycleWorkflow.tsx`

**Implementation:**

- Use promotion endpoints: `POST /api/models/{id}/promote/{stage}`
- Display stage transitions: staging → paper → production
- Workflow visualization
- Action buttons for each stage
- Type: Model lifecycle props

**Design System:**

- Density: `comfortable` (workflow visualization)
- Orange accent for active stage
- Use `StatusBadge` for stage indicators

### 10.23 ModelValidationPanel

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/ModelValidationPanel.tsx`

**Implementation:**

- Use `GET /api/models/{model_id}/validation`
- Subscribe to WebSocket `/ws/models/{model_id}/validation`
- Display validation results
- Check list with pass/fail indicators
- Type: `ValidationResult` from `types/model.ts`

**Design System:**

- Density: `dense`
- Use semantic colors for pass/fail
- Orange accent for validation status

### 10.24 FeatureMetadataDisplay

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/FeatureMetadataDisplay.tsx`

**Implementation:**

- Use `GET /api/features/{name}`
- Display feature descriptions, types, statistics
- Use `DenseCard` for sections
- Type: `Feature` from `types/feature.ts`

**Design System:**

- Density: `comfortable` (detail view)
- Numbers: Monospace font for statistics

### 10.25 DataQualityMetrics

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/ml/DataQualityMetrics.tsx`

**Implementation:**

- Use `GET /api/data/quarantine` for rejection stats
- Display data quality metrics
- Use `KPICard` for metrics
- Type: Data quality metrics

**Design System:**

- Density: `dense`
- Use `KPICard` components
- Status colors for quality indicators

### 10.26 FeatureLineageGraph

**Status:** ✅ API Available

**File:** `src/dashboard/src/components/ml/FeatureLineageGraph.tsx`

**Implementation:**

- Use `GET /api/lineage/runs/{run_id}`
- Use `GET /api/lineage/datasets/{namespace}/{dataset_name}`
- Use `GET /api/lineage/jobs/{namespace}/{job_name}`
- Visualize feature dependencies
- Graph visualization (use D3.js or similar)
- Type: Lineage data

**Design System:**

- Graph: Monochrome nodes with orange accent for selected
- No halftone textures in graph area

---

## Phase 11: P2 Components (Weeks 16-18)

### 11.1 PositionSizeCalculator (Enhanced)

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/trading/PositionSizeCalculator.tsx`

**Implementation:**

- Enhanced version with risk parameters
- Multiple calculation methods
- Historical analysis
- Type: Enhanced calculator props

**Design System:**

- Density: `comfortable`
- Numbers: Monospace font
- Orange accent for calculate button

### 11.2 NewsFeed (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/trading/NewsFeed.tsx`

**Implementation:**

- Mock service only
- Financial news integration
- RSS feed display
- Filter by category
- Type: News article props

**Design System:**

- Density: `dense`
- Use `DenseCard` for news items
- Orange accent for read more links

**Mock support:**

- Generate mock news articles

### 11.3 AlertManagement (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/trading/AlertManagement.tsx`

**Implementation:**

- Mock service only
- Price/condition alerts
- Create, edit, delete alerts
- Alert notification center
- Type: Alert props

**Design System:**

- Density: `dense`
- Use `DenseCard` for alert list
- Orange accent for active alerts

**Mock support:**

- Client-side alert storage

### 11.4 ConfusionMatrix (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/ml/ConfusionMatrix.tsx`

**Implementation:**

- Mock service only
- Classification performance visualization
- Heatmap display
- Use Recharts or custom heatmap
- Type: Confusion matrix data

**Design System:**

- Chart: Monochrome with orange accent for diagonal
- Numbers: Monospace font
- No halftone textures

**Mock support:**

- Generate mock confusion matrix

### 11.5 ROCCurve (Mock Only)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/ml/ROCCurve.tsx`

**Implementation:**

- Mock service only
- ROC curve visualization
- Threshold analysis
- Use Recharts LineChart
- Type: ROC curve data

**Design System:**

- Chart: Monochrome with orange accent for curve
- Numbers: Monospace font

**Mock support:**

- Generate mock ROC data

### 11.6 Heatmap (Generic)

**Status:** ⚠️ Partial API

**File:** `src/dashboard/src/components/charts/Heatmap.tsx`

**Implementation:**

- Generic heatmap component
- Correlation matrices
- Use Recharts or custom implementation
- Type: Heatmap data

**Design System:**

- Chart: Monochrome gradient with orange accent for highlights
- Numbers: Monospace font for values

**Usage:**

- Correlation matrices (calculate from available data)
- Confusion matrices (if classification data available)

### 11.7 CandlestickChart

**Status:** ❌ Missing API (OHLC data)

**File:** `src/dashboard/src/components/charts/CandlestickChart.tsx`

**Implementation:**

- Use Lightweight Charts (TradingView) for candlesticks
- Mock OHLC data for development
- Support multiple timeframes
- Type: `CandleData[]` from `types/market.ts`

**Design System:**

- Chart: Monochrome candles with orange accent for volume
- Numbers: Monospace font for prices

**Mock support:**

- Generate OHLC data from tick data
- Simulate price movements

### 11.8 CodeEditor

**Status:** N/A (Client-side)

**File:** `src/dashboard/src/components/advanced/CodeEditor.tsx`

**Implementation:**

- Embedded code editing
- Use Monaco Editor or CodeMirror
- Syntax highlighting
- Type: Editor props

**Design System:**

- Editor: Terminal theme (monochrome with orange accent)
- Font: Monospace
- Density: `comfortable`

### 11.9 NotebookViewer

**Status:** N/A (Client-side)

**File:** `src/dashboard/src/components/advanced/NotebookViewer.tsx`

**Implementation:**

- Jupyter notebook display
- Render markdown, code, outputs
- Use react-notebook or similar
- Type: Notebook props

**Design System:**

- Terminal theme for code cells
- Monospace font for code
- Orange accent for execution buttons

### 11.10 FileUploader

**Status:** N/A (Client-side)

**File:** `src/dashboard/src/components/forms/FileUploader.tsx`

**Implementation:**

- File upload component
- Drag and drop support
- Progress indicator
- Type: Upload props

**Design System:**

- Density: `comfortable`
- Orange accent for upload button
- Use `ProgressBar` for upload progress

### 11.11 ImageUploader

**Status:** N/A (Client-side)

**File:** `src/dashboard/src/components/forms/ImageUploader.tsx`

**Implementation:**

- Image upload with preview
- Crop/resize functionality
- Type: Image upload props

**Design System:**

- Density: `comfortable`
- Orange accent for upload button
- Preview: Monochrome border

### 11.12 DataExport

**Status:** ✅ API Available (some endpoints)

**File:** `src/dashboard/src/components/advanced/DataExport.tsx`

**Implementation:**

- Use `GET /api/performance/portfolio/export`
- Use `GET /api/performance/models/{id}/export`
- Export data functionality
- CSV/PDF export
- Type: Export props

**Design System:**

- Density: `dense`
- Orange accent for export button

### 11.13 Tooltip

**File:** `src/dashboard/src/components/feedback/Tooltip.tsx`

**Implementation:**

- Hover tooltip component
- Use shadcn/ui Tooltip
- Customize with design system colors
- Type: Tooltip props

**Design System:**

- Background: `mono-300` with orange accent border
- Text: Monochrome

### 11.14 Popover

**File:** `src/dashboard/src/components/feedback/Popover.tsx`

**Implementation:**

- Popover component
- Use shadcn/ui Popover
- Customize with design system colors
- Type: Popover props

**Design System:**

- Background: `mono-300` with orange accent border

### 11.15 ContextMenu

**File:** `src/dashboard/src/components/feedback/ContextMenu.tsx`

**Implementation:**

- Right-click menu component
- Use shadcn/ui ContextMenu
- Customize with design system colors
- Type: Context menu props

**Design System:**

- Background: `mono-300`
- Orange accent for hover state

### 11.16 FormField

**File:** `src/dashboard/src/components/forms/FormField.tsx`

**Implementation:**

- Form field wrapper with validation
- Error message display
- Label and helper text
- Type: Form field props

**Design System:**

- Density: `comfortable`
- Error: Use semantic destructive color
- Focus: Orange ring

### 11.17 NumberInput

**File:** `src/dashboard/src/components/forms/NumberInput.tsx`

**Implementation:**

- Numeric input with controls
- Increment/decrement buttons
- Min/max validation
- Type: Number input props

**Design System:**

- Numbers: Monospace font
- Orange accent for increment/decrement buttons
- Focus: Orange ring

### 11.18 Textarea

**File:** `src/dashboard/src/components/forms/Textarea.tsx`

**Implementation:**

- Multi-line text input
- Use shadcn/ui Textarea
- Auto-resize option
- Type: Textarea props

**Design System:**

- Density: `comfortable`
- Focus: Orange ring

### 11.19 Checkbox

**File:** `src/dashboard/src/components/forms/Checkbox.tsx`

**Implementation:**

- Checkbox input
- Use shadcn/ui Checkbox
- Customize with design system colors
- Type: Checkbox props

**Design System:**

- Orange accent for checked state
- Focus: Orange ring

### 11.20 RadioGroup

**File:** `src/dashboard/src/components/forms/RadioGroup.tsx`

**Implementation:**

- Radio button group
- Use shadcn/ui RadioGroup
- Customize with design system colors
- Type: Radio group props

**Design System:**

- Orange accent for selected state
- Focus: Orange ring

### 11.21 TimePicker

**File:** `src/dashboard/src/components/forms/TimePicker.tsx`

**Implementation:**

- Time selection component
- Use date-fns for time formatting
- Type: Time picker props

**Design System:**

- Density: `comfortable`
- Numbers: Monospace font for time display
- Focus: Orange ring

---

## Phase 12: P3 Components (Weeks 19-20)

### 12.1 CustomDashboardBuilder

**Status:** N/A (Client-side)

**File:** `src/dashboard/src/components/advanced/CustomDashboardBuilder.tsx`

**Implementation:**

- Drag-and-drop dashboard builder
- Widget library
- Layout customization
- Save/load layouts
- Type: Dashboard builder props

**Design System:**

- Density: `comfortable` (builder interface)
- Orange accent for selected widgets
- Use `DenseCard` for widget containers

### 12.2 LayoutCustomizer

**Status:** N/A (Client-side)

**File:** `src/dashboard/src/components/advanced/LayoutCustomizer.tsx`

**Implementation:**

- User layout preferences
- Save layout configurations
- Type: Layout config props

**Design System:**

- Density: `comfortable`
- Orange accent for save button

### 12.3 ThemeCustomizer

**Status:** N/A (Client-side)

**File:** `src/dashboard/src/components/advanced/ThemeCustomizer.tsx`

**Implementation:**

- Advanced theme options
- Custom color schemes (within design system constraints)
- Type: Theme config props

**Design System:**

- Maintain terminal/print aesthetic
- Allow density customization
- Orange accent must remain primary

### 12.4 CollaborationFeatures (Future)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/advanced/CollaborationFeatures.tsx`

**Implementation:**

- Comments on experiments/models
- Sharing functionality
- Team collaboration
- Type: Collaboration props

**Design System:**

- Density: `dense`
- Orange accent for action buttons

**Note:** Requires backend API development

### 12.5 AdvancedAnalytics (Future)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/advanced/AdvancedAnalytics.tsx`

**Implementation:**

- Advanced analytics dashboard
- Custom queries
- Statistical analysis
- Type: Analytics props

**Design System:**

- Density: `dense`
- Charts: Follow chart design system

**Note:** Requires backend API development

### 12.6 3DVisualizations (Future)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/charts/3DVisualizations.tsx`

**Implementation:**

- 3D plots for parameter spaces
- Use Three.js or Plotly.js 3D
- Type: 3D visualization props

**Design System:**

- Monochrome base with orange accent for highlights
- No halftone textures

**Note:** Low priority, future enhancement

### 12.7 GeospatialMaps (Future)

**Status:** ❌ Missing API

**File:** `src/dashboard/src/components/charts/GeospatialMaps.tsx`

**Implementation:**

- Geospatial data visualization
- Map integration
- Type: Geospatial props

**Design System:**

- Monochrome map style
- Orange accent for markers

**Note:** Low priority, future enhancement

---

## Implementation Guidelines

### Component Structure

```typescript
// Example component structure following design system
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common'
import { cn } from '@/utils/cn'

interface ComponentProps {
  density?: 'comfortable' | 'dense' | 'ultra-dense'
  className?: string
  // Component-specific props
}

export function Component({ 
  density = 'dense',
  className,
  ...props 
}: ComponentProps) {
  // 1. Data fetching (React Query)
  // 2. WebSocket subscriptions (if needed)
  // 3. State management
  // 4. Render with design system components
  
  return (
    <DenseCard density={density} className={className}>
      <DenseCardHeader title="Component Title" />
      <DenseCardContent>
        {/* Use font-mono-data for numbers */}
        <span className="font-mono-data">123.45</span>
        {/* Use text-technical for labels */}
        <span className="text-technical">LABEL</span>
      </DenseCardContent>
    </DenseCard>
  )
}
```

### Design System Styling Checklist

For each component, ensure:

- [ ] Uses CSS variables or Tailwind tokens (no hard-coded colors)
- [ ] Supports density variants (`comfortable`, `dense`, `ultra-dense`)
- [ ] Uses `font-mono-data` for all numeric values
- [ ] Uses `text-technical` for technical labels
- [ ] Orange accent (`orange-400`) only for focus, active states, primary actions
- [ ] Semantic colors for status (success, warning, error, info)
- [ ] Visible focus rings (orange) on all interactive elements
- [ ] Respects `prefers-reduced-motion` for animations
- [ ] Works in both dark and light themes
- [ ] No halftone textures in tables, charts, or dense text areas

### Type Safety

- All components use shared types from `types/` directory
- Mock services return same types as real API
- Use TypeScript strict mode
- No `any` types

### Mock Data Generation

- Use realistic data patterns (not just random)
- Maintain data relationships (e.g., positions match trades)
- Support all filter/query parameters
- Simulate real-time updates with appropriate intervals

### Testing Strategy

- Components work with both real API and mocks
- Test with mocks for development
- Integration tests with real API
- Type checking ensures API/mock compatibility

### Environment Configuration

```typescript
// .env.local
VITE_USE_MOCK_API=true  # Enable mocks
VITE_API_BASE_URL=http://localhost:8000  # Real API URL
```

---

## File Structure Summary

### New Directories

```
src/dashboard/src/
├── components/
│   ├── trading/          # 15+ components
│   ├── ml/              # 20+ components
│   ├── charts/          # 8+ chart components
│   ├── forms/           # 10+ form components
│   └── feedback/        # 5+ feedback components
├── services/
│   ├── api-mock.ts      # Mock API client
│   ├── api-factory.ts   # API factory
│   └── websocket-mock.ts # Mock WebSocket
└── types/
    ├── market.ts        # Market data types
    ├── orders.ts        # Order types
    ├── charts.ts        # Chart types
    ├── training.ts      # Training types
    └── resources.ts     # Resource types
```

### Estimated Files

- **Types:** ~8 new type files, ~15 extended
- **Services:** 3 new service files
- **Components:** ~85 new component files
  - Trading: ~20 components
  - ML: ~30 components
  - Charts: ~12 components
  - Forms: ~12 components
  - Feedback: ~7 components
  - Advanced: ~4 components
- **Total:** ~95-100 new files

---

## Success Criteria

1. ✅ All P0 components implemented and functional
2. ✅ All P1 components implemented and functional
3. ✅ P2 components implemented (as needed)
4. ✅ P3 components planned for future
5. ✅ Type safety: zero `any` types, all components typed
6. ✅ Mock/real API switching works seamlessly
7. ✅ Components follow design system (density, theme, typography, colors)
8. ✅ All components documented with usage examples
9. ✅ Components work with existing pages
10. ✅ No breaking changes to existing code
11. ✅ Design system compliance verified (colors, typography, density, animations)
12. ✅ Accessibility: keyboard navigation, focus states, screen readers
13. ✅ Performance: optimized renders, lazy loading, virtualization where needed

---

## Implementation Timeline Summary

### Phase 1: Foundation (Week 1)

- Type definitions
- Mock service infrastructure
- API client extensions

### Phase 2-5: P0 Components (Weeks 2-7)

- Trading components (6 components)
- ML components (6 components)
- Chart components (5 components)
- Missing API components (3 components)

### Phase 6-10: P1 Components (Weeks 8-15)

- Remaining trading components (10 components)
- Remaining ML components (15 components)
- Form components (11 components)
- Feedback components (7 components)

### Phase 11: P2 Components (Weeks 16-18)

- Advanced trading features (3 components)
- Advanced ML visualizations (3 components)
- Advanced form components (6 components)
- Advanced feedback components (3 components)
- Advanced utilities (3 components)

### Phase 12: P3 Components (Weeks 19-20)

- Future enhancements (7 components)
- Collaboration features
- Advanced analytics
- 3D visualizations
- Geospatial maps

**Total Timeline:** 20 weeks for complete implementation

## Next Steps After Plan Approval

1. Create type definitions (Phase 1.1)
2. Set up mock service infrastructure (Phase 1.2)
3. Begin P0 component implementation (Phase 2)
4. Iterate: build → test → document → integrate
5. Follow design system guidelines for each component
6. Test in both dark and light themes
7. Verify accessibility and performance