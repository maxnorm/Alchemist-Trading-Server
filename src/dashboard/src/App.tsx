import { lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { Toaster } from 'react-hot-toast'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { Layout } from '@/components/Layout/Layout'
import { WebSocketProvider } from '@/contexts/WebSocketContext'
import { UIContextProvider } from '@/contexts/UIContext'

// Lazy load pages for code splitting
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const ExperimentBuilder = lazy(() => import('@/pages/ExperimentBuilder'))
const HyperparameterSearch = lazy(() => import('@/pages/HyperparameterSearch'))
const TrainingMonitor = lazy(() => import('@/pages/TrainingMonitor'))
const FeatureCatalog = lazy(() => import('@/pages/FeatureCatalog'))
const ModelRegistry = lazy(() => import('@/pages/ModelRegistry'))
const LiveTrading = lazy(() => import('@/pages/LiveTrading'))
const MT5Accounts = lazy(() => import('@/pages/MT5Accounts'))
const PortfolioPerformance = lazy(() => import('@/pages/PortfolioPerformance'))
const ModelPerformance = lazy(() => import('@/pages/ModelPerformance'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000, // 30 seconds - data is considered fresh
      gcTime: 5 * 60 * 1000, // 5 minutes - cache time (formerly cacheTime)
      // Enable request deduplication for parallel queries
      refetchOnMount: false, // Don't refetch if data is fresh
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
                  {/* Suspense moved to Layout - pages render directly */}
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
            {/* React Query DevTools - only in development */}
            {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
          </WebSocketProvider>
        </UIContextProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

export default App
