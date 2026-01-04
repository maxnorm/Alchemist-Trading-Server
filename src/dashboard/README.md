# The Alchemist Dashboard

React dashboard for The Alchemist AI Forex Experimentation Platform.

## Development

### Prerequisites

- Node.js 20+
- npm or yarn

### Setup

1. Install dependencies:
```bash
npm install
```

2. Create `.env` file (copy from `.env.example`):
```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

3. Start development server:
```bash
npm run dev
```

The dashboard will be available at `http://localhost:3000`

## Building for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## Docker

Build and run with Docker Compose (from project root):

```bash
docker compose up dashboard
```

The dashboard will be available at `http://localhost:3000`

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
