import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { Layout } from '@/components/Layout/Layout'
import { WebSocketProvider } from '@/contexts/WebSocketContext'
import { UIContextProvider } from '@/contexts/UIContext'

// Pages
import Dashboard from '@/pages/Dashboard'
import ExperimentBuilder from '@/pages/ExperimentBuilder'
import HyperparameterSearch from '@/pages/HyperparameterSearch'
import TrainingMonitor from '@/pages/TrainingMonitor'
import FeatureCatalog from '@/pages/FeatureCatalog'
import ModelRegistry from '@/pages/ModelRegistry'
import LiveTrading from '@/pages/LiveTrading'
import MT5Accounts from '@/pages/MT5Accounts'
import PortfolioPerformance from '@/pages/PortfolioPerformance'
import ModelPerformance from '@/pages/ModelPerformance'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000,
    },
  },
})

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <UIContextProvider>
          <WebSocketProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/" element={<Layout />}>
                  <Route index element={<Dashboard />} />
                  <Route path="dashboard" element={<Dashboard />} />
                  <Route path="experiments" element={<ExperimentBuilder />} />
                  <Route path="hyperparameters" element={<HyperparameterSearch />} />
                  <Route path="training" element={<TrainingMonitor />} />
                  <Route path="features" element={<FeatureCatalog />} />
                  <Route path="models" element={<ModelRegistry />} />
                  <Route path="trading" element={<LiveTrading />} />
                  <Route path="accounts" element={<MT5Accounts />} />
                  <Route path="performance" element={<PortfolioPerformance />} />
                  <Route path="performance/:modelId" element={<ModelPerformance />} />
                </Route>
              </Routes>
            </BrowserRouter>
            <Toaster position="top-right" />
          </WebSocketProvider>
        </UIContextProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App
