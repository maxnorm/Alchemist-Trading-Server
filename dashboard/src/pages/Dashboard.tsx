import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EquityCurveChart } from '@/components/charts/EquityCurveChart'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { useTradingStore } from '@/stores/tradingStore'
import { useTradingPositions } from '@/hooks/useTradingPositions'
import { usePerformanceMetrics } from '@/features/performance/hooks/usePerformanceMetrics'
import { useEquityCurve } from '@/features/performance/hooks/useEquityCurve'
import { useDashboardStats } from '@/hooks/useDashboardStats'
import { DashboardHeader } from './Dashboard/components/DashboardHeader'
import { PortfolioSummaryCards } from './Dashboard/components/PortfolioSummaryCards'
import { SystemStatus } from './Dashboard/components/SystemStatus'
import { ActivePositions } from './Dashboard/components/ActivePositions'
import { TopModels } from './Dashboard/components/TopModels'
import { RecentActivity } from './Dashboard/components/RecentActivity'
import { QuickStats } from './Dashboard/components/QuickStats'
import type { PortfolioMetrics } from '@/types/performance'

export default function Dashboard() {
  const { status } = useTradingStore()
  const { positions } = useTradingPositions()
  const { metrics: portfolioMetrics, isLoading: metricsLoading } = usePerformanceMetrics('all_time')
  const { equityCurve } = useEquityCurve()
  const { topModels, recentActivity, quickStats } = useDashboardStats()

  const { data: circuitBreaker } = useQuery({
    queryKey: ['circuit-breaker'],
    queryFn: () => api.getCircuitBreakerStatus(),
  })

  // Filter equity curve to last 30 days for mini chart
  const recentEquityCurve = useMemo(() => {
    if (!equityCurve) return []
    const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000
    return equityCurve.filter((point) => new Date(point.timestamp).getTime() > thirtyDaysAgo)
  }, [equityCurve])

  if (metricsLoading && !portfolioMetrics) {
    return <LoadingSpinner />
  }

  return (
    <div className="space-y-6">
      <DashboardHeader lastUpdated={new Date().toLocaleTimeString()} />

      <PortfolioSummaryCards metrics={portfolioMetrics as PortfolioMetrics | undefined} />

      <div className="grid gap-4 md:grid-cols-2">
        <SystemStatus status={status} circuitBreaker={circuitBreaker || null} />
        <ActivePositions positions={positions} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <TopModels topModels={topModels} />
        <RecentActivity activities={recentActivity} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <QuickStats stats={quickStats} />
        <Card>
          <CardHeader>
            <CardTitle>Portfolio Equity (30 Days)</CardTitle>
            <CardDescription>Recent performance trend</CardDescription>
          </CardHeader>
          <CardContent>
            {recentEquityCurve.length > 0 ? (
              <>
                <EquityCurveChart data={recentEquityCurve} height={200} showDrawdown={false} />
                <Link
                  to="/performance"
                  className="flex items-center gap-2 text-sm text-primary hover:underline mt-4"
                >
                  View full performance
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No equity curve data available</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
