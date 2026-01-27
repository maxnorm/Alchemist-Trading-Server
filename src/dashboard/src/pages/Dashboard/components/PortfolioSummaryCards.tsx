import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCurrency, formatPercent } from '@/utils/formatters'
import { TrendingUp, TrendingDown, Activity } from 'lucide-react'
import type { PortfolioMetrics } from '@/types/performance'

interface PortfolioSummaryCardsProps {
  metrics: PortfolioMetrics | undefined
  isLoading?: boolean
}

export function PortfolioSummaryCards({ metrics, isLoading }: PortfolioSummaryCardsProps) {
  if (isLoading && !metrics) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <div className="h-4 w-24 bg-muted animate-pulse rounded" />
              <div className="h-4 w-4 bg-muted animate-pulse rounded" />
            </CardHeader>
            <CardContent>
              <div className="h-8 w-32 bg-muted animate-pulse rounded mb-2" />
              <div className="h-4 w-40 bg-muted animate-pulse rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (!metrics) return null

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
          {metrics.total_pnl >= 0 ? (
            <TrendingUp className="h-4 w-4 text-green-600" />
          ) : (
            <TrendingDown className="h-4 w-4 text-red-600" />
          )}
        </CardHeader>
        <CardContent>
          <div
            className={`text-2xl font-bold ${
              metrics.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'
            }`}
          >
            {formatCurrency(metrics.total_pnl)}
          </div>
          {metrics.total_pnl_pct !== undefined && (
            <p className="text-xs text-muted-foreground mt-1">
              {formatPercent(metrics.total_pnl_pct)}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Sharpe Ratio</CardTitle>
          <Activity className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {metrics.sharpe_ratio?.toFixed(2) || 'N/A'}
          </div>
          <p className="text-xs text-muted-foreground mt-1">Risk-adjusted return</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Win Rate</CardTitle>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {formatPercent(metrics.win_rate != null ? metrics.win_rate * 100 : null)}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {metrics.winning_trades} / {metrics.total_trades} trades
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Max Drawdown</CardTitle>
          <TrendingDown className="h-4 w-4 text-red-600" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-red-600">
            {metrics.max_drawdown_pct !== undefined
              ? formatPercent(metrics.max_drawdown_pct)
              : metrics.max_drawdown
              ? formatCurrency(metrics.max_drawdown)
              : 'N/A'}
          </div>
          <p className="text-xs text-muted-foreground mt-1">Worst peak-to-trough</p>
        </CardContent>
      </Card>
    </div>
  )
}
