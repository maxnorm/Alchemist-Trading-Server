import { useMemo } from 'react'
import { EquityCurveChart } from '@/components/charts/EquityCurveChart'
import { Link } from 'react-router-dom'
import { ArrowRight, TrendingUp, Activity, AlertTriangle } from 'lucide-react'
import { useTradingStore } from '@/stores/tradingStore'
import { useTradingPositions } from '@/hooks/useTradingPositions'
import { usePerformanceMetrics } from '@/features/performance/hooks/usePerformanceMetrics'
import { useEquityCurve } from '@/features/performance/hooks/useEquityCurve'
import { useDashboardStats } from '@/hooks/useDashboardStats'
import { formatCurrency, formatPercent } from '@/utils/formatters'
import type { PortfolioMetrics } from '@/types/performance'

// New components
import { PageHeader } from '@/components/common/PageHeader'
import { KPICard } from '@/components/common/KPICard'
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard'
import { AnimatedPanel, AnimatedList } from '@/components/common/AnimatedPanel'
import { HealthDot } from '@/components/common/StatusBadge'

// Keep existing specialized components
import { SystemStatus } from './Dashboard/components/SystemStatus'
import { ActivePositions } from './Dashboard/components/ActivePositions'
import { TopModels } from './Dashboard/components/TopModels'
import { RecentActivity } from './Dashboard/components/RecentActivity'
import { QuickStats } from './Dashboard/components/QuickStats'

export default function Dashboard() {
  const { status } = useTradingStore()
  const { positions } = useTradingPositions()
  const { metrics: portfolioMetrics, isLoading: metricsLoading } = usePerformanceMetrics('all_time')
  const { equityCurve } = useEquityCurve()
  const { topModels, recentActivity, quickStats, circuitBreaker } = useDashboardStats()

  // Filter equity curve to last 30 days for mini chart
  const recentEquityCurve = useMemo(() => {
    if (!equityCurve) return []
    const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000
    return equityCurve.filter((point) => new Date(point.timestamp).getTime() > thirtyDaysAgo)
  }, [equityCurve])

  const metrics = portfolioMetrics as PortfolioMetrics | undefined

  return (
    <div className="space-y-4">
      {/* Page Header with halftone texture */}
      <PageHeader
        title="Command Center"
        description="Real-time portfolio monitoring and system status"
        actions={
          <div className="flex items-center gap-3">
            <HealthDot 
              status={status?.is_active ? 'ok' : 'error'} 
              label="Trading System" 
            />
            <span className="text-xs text-mono-600 dark:text-mono-600 font-medium">
              Updated {new Date().toLocaleTimeString()}
            </span>
          </div>
        }
      />

      {/* KPI Grid - Dense, ZEEX-style */}
      <AnimatedList className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {[
          <KPICard
            key="pnl"
            label="Total P&L"
            value={metrics ? formatCurrency(metrics.total_pnl) : '—'}
            delta={
              metrics?.total_pnl_pct !== undefined
                ? {
                    value: formatPercent(metrics.total_pnl_pct),
                    status: metrics.total_pnl >= 0 ? 'positive' : 'negative',
                  }
                : undefined
            }
            icon={<TrendingUp className="h-4 w-4" />}
            status={metrics?.total_pnl ? (metrics.total_pnl >= 0 ? 'positive' : 'negative') : 'neutral'}
            loading={metricsLoading}
            density="dense"
          />,
          <KPICard
            key="sharpe"
            label="Sharpe Ratio"
            value={metrics?.sharpe_ratio?.toFixed(2) || '—'}
            icon={<Activity className="h-4 w-4" />}
            loading={metricsLoading}
            density="dense"
          />,
          <KPICard
            key="winrate"
            label="Win Rate"
            value={
              metrics?.win_rate != null
                ? formatPercent(metrics.win_rate * 100)
                : '—'
            }
            delta={
              metrics
                ? {
                    value: `${metrics.winning_trades}/${metrics.total_trades}`,
                    status: 'neutral',
                  }
                : undefined
            }
            loading={metricsLoading}
            density="dense"
          />,
          <KPICard
            key="drawdown"
            label="Max Drawdown"
            value={
              metrics?.max_drawdown_pct !== undefined
                ? formatPercent(metrics.max_drawdown_pct)
                : metrics?.max_drawdown
                ? formatCurrency(metrics.max_drawdown)
                : '—'
            }
            icon={<AlertTriangle className="h-4 w-4" />}
            status="negative"
            loading={metricsLoading}
            density="dense"
          />,
        ]}
      </AnimatedList>

      {/* System Status + Active Positions */}
      <AnimatedPanel delay={0.1}>
        <div className="grid gap-3 md:grid-cols-2">
          <SystemStatus status={status} circuitBreaker={circuitBreaker ?? null} />
          <ActivePositions positions={positions} />
        </div>
      </AnimatedPanel>

      {/* Top Models + Recent Activity */}
      <AnimatedPanel delay={0.15}>
        <div className="grid gap-3 md:grid-cols-2">
          <TopModels topModels={topModels} />
          <RecentActivity activities={recentActivity} />
        </div>
      </AnimatedPanel>

      {/* Quick Stats + Equity Chart */}
      <AnimatedPanel delay={0.2}>
        <div className="grid gap-3 md:grid-cols-2">
          <QuickStats stats={quickStats} />
          <DenseCard density="dense" hover>
            <DenseCardHeader
              title="Portfolio Equity (30 Days)"
              description="Recent performance trend"
            />
            <DenseCardContent>
              {recentEquityCurve.length > 0 ? (
                <>
                  <EquityCurveChart data={recentEquityCurve} height={200} showDrawdown={false} />
                  <Link
                    to="/performance"
                    className="flex items-center gap-2 text-sm text-orange-400 hover:text-orange-300 transition-colors mt-4"
                  >
                    View full performance
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No equity curve data available</p>
              )}
            </DenseCardContent>
          </DenseCard>
        </div>
      </AnimatedPanel>
    </div>
  )
}
