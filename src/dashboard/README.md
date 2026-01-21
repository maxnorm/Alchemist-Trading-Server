# The Alchemist Dashboard

React dashboard for The Alchemist AI Forex Experimentation Platform.

## Development

### Prerequisites

- **Node.js 20.19+ or 22.12+** (required for Vite 7)
  - Check your version: `node --version`
  - Upgrade if needed: [Download Node.js](https://nodejs.org/) or use [nvm](https://github.com/nvm-sh/nvm) (Windows: [nvm-windows](https://github.com/coreybutler/nvm-windows))
- npm 10+ or yarn
- Backend services running via Docker Compose (see main project README)

### Setup

1. Install dependencies:
```bash
npm install
```

2. Create `.env.local` file for local development:
```bash
# Point to gateway (recommended - consistent with production routing)
VITE_API_URL=http://localhost/api
VITE_WS_URL=ws://localhost/ws

# Alternative: Point directly to API (bypasses gateway)
# VITE_API_URL=http://localhost:8000
# VITE_WS_URL=ws://localhost:8000/ws

# Clerk authentication (get from your Clerk dashboard)
# VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
```

**Note:** The dashboard is now run locally via `npm run dev` and connects to backend services running in Docker Compose. The gateway serves only backend services (API + Server).

3. Start backend services (from project root):
```bash
docker compose up -d gateway api server postgres redis mlflow
```

4. Start development server:
```bash
npm run dev
```

The dashboard will be available at `http://localhost:3000` and will connect to the backend via the gateway at `http://localhost/api`.

## Building for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## Docker (Legacy)

**Note:** Dashboard is no longer deployed via Docker Compose. It runs locally for development.

For production deployment, the dashboard can be built and deployed separately:

```bash
npm run build
# Deploy dist/ directory to your hosting service (Vercel, Netlify, S3, etc.)
```

## Features

- **Experiment Builder**: Create and configure trading experiments
- **Hyperparameter Search**: Configure and monitor Optuna optimization
- **Training Monitor**: Real-time training metrics
- **Feature Catalog**: Browse available features
- **Model Registry**: Manage model lifecycle
- **Live Trading**: Monitor and control live trading
- **MT5 Accounts**: Manage account connections and assignments
- **Performance**: View portfolio and model performance metrics

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **shadcn/ui** - UI components
- **Zustand** - State management (legacy, being migrated to Context)
- **TanStack Query** - Server state
- **React Router** - Routing
- **Axios** - HTTP client
- **Lightweight Charts** - Trading charts
- **Recharts** - Metrics charts
- **Vitest** - Testing framework

## Architecture

The dashboard follows a feature-based architecture with clear separation of concerns:

```
src/
├── features/              # Feature-based organization
│   ├── experiments/      # Experiment management
│   │   ├── hooks/        # useExperimentForm, useExperiments
│   │   └── components/   # Presentational components
│   ├── models/           # Model lifecycle management
│   ├── trading/          # Trading operations
│   ├── performance/     # Performance metrics
│   ├── features/         # Feature catalog
│   └── optuna/           # Hyperparameter optimization
├── hooks/                 # Shared reusable hooks
│   ├── usePagination.ts
│   ├── usePeriodFilter.ts
│   ├── useDebounce.ts
│   └── useModalController.ts
├── contexts/             # React Context providers
│   ├── WebSocketContext.tsx
│   └── UIContext.tsx
├── services/             # API clients and services
│   ├── api.ts
│   ├── websocket.ts
│   └── 2fa.ts
├── stores/               # Zustand stores (legacy, being migrated)
├── components/           # Shared presentational components
└── pages/                # Page components (orchestrate hooks + components)
```

### Key Principles

1. **Custom Hooks**: Reusable stateful logic extracted into hooks (e.g., `useExperimentForm`, `usePerformanceMetrics`)
2. **Context Providers**: Shared state managed via React Context (WebSocket, UI theme)
3. **Presentational Components**: UI components are mostly presentational (props in, JSX out)
4. **Feature Organization**: Domain logic organized by feature for better maintainability
5. **Separation of Concerns**: Business logic in hooks, UI in components, coordination via context

### Testing

Run tests with:
```bash
npm test              # Run tests
npm run test:ui       # Run tests with UI
npm run test:coverage # Run tests with coverage
```

Test files are co-located with their source files in `__tests__` directories.
