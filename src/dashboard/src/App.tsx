import { lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { Toaster } from 'react-hot-toast'
import { ClerkProvider } from '@clerk/clerk-react'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import { Layout } from '@/components/Layout/Layout'
import { WebSocketProvider } from '@/contexts/WebSocketContext'
import { UIContextProvider } from '@/contexts/UIContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { clerkConfig } from '@/config/clerk'
import { clerkAppearance } from '@/config/clerkAppearance'
import { useClerkApi } from '@/hooks/useClerkApi'

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
const Unauthorized = lazy(() => import('@/pages/Unauthorized'))
const SignInPage = lazy(() => import('@/pages/SignInPage'))
const SignUpPage = lazy(() => import('@/pages/SignUpPage'))

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

function AppContent() {
  // Initialize API client with Clerk token getter
  useClerkApi()

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <UIContextProvider>
          <WebSocketProvider>
            <BrowserRouter>
              <Routes>
                  {/* Authentication pages */}
                  <Route path="/sign-in/*" element={<SignInPage />} />
                  <Route path="/sign-up/*" element={<SignUpPage />} />
                  <Route path="/unauthorized" element={<Unauthorized />} />
                  
                  {/* Protected routes */}
                <Route path="/" element={<Layout />}>
                  <Route index element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                  <Route path="dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                  <Route path="experiments" element={<ProtectedRoute><ExperimentBuilder /></ProtectedRoute>} />
                  <Route path="hyperparameters" element={<ProtectedRoute><HyperparameterSearch /></ProtectedRoute>} />
                  <Route path="training" element={<ProtectedRoute><TrainingMonitor /></ProtectedRoute>} />
                  <Route path="features" element={<ProtectedRoute><FeatureCatalog /></ProtectedRoute>} />
                  <Route path="models" element={<ProtectedRoute><ModelRegistry /></ProtectedRoute>} />
                  <Route path="trading" element={<ProtectedRoute><LiveTrading /></ProtectedRoute>} />
                  <Route path="accounts" element={<ProtectedRoute><MT5Accounts /></ProtectedRoute>} />
                  <Route path="performance" element={<ProtectedRoute><PortfolioPerformance /></ProtectedRoute>} />
                  <Route path="performance/:modelId" element={<ProtectedRoute><ModelPerformance /></ProtectedRoute>} />
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

function App() {
  if (!clerkConfig.publishableKey) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-2">Configuration Error</h1>
          <p className="text-muted-foreground">Clerk publishable key is not configured</p>
        </div>
      </div>
    )
  }

  return (
    <ClerkProvider 
      publishableKey={clerkConfig.publishableKey}
      appearance={clerkAppearance}
    >
      <AppContent />
    </ClerkProvider>
  )
}

export default App
