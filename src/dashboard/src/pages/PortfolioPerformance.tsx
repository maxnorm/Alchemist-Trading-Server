import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EquityCurveChart } from '@/components/charts/EquityCurveChart'
import { formatCurrency, formatPercent } from '@/utils/formatters'
import { usePeriodFilter } from '@/hooks/usePeriodFilter'
import { usePerformanceMetrics } from '@/features/performance/hooks/usePerformanceMetrics'
import { useEquityCurve } from '@/features/performance/hooks/useEquityCurve'
import { usePerformanceBreakdown } from '@/features/performance/hooks/usePerformanceBreakdown'
import { PageHeader } from '@/components/common/PageHeader'
import { HealthDot } from '@/components/common/StatusBadge'
import { RefreshCw, Download } from 'lucide-react'
import toast from 'react-hot-toast'
import type { PortfolioMetrics, PerformanceBreakdown } from '@/types/performance'

export default function PortfolioPerformance() {
  const { period, setPeriod, periods } = usePeriodFilter('all_time')
  const { metrics, isLoading } = usePerformanceMetrics(period)
  const { equityCurve } = useEquityCurve()
  const { breakdown } = usePerformanceBreakdown(period === 'all_time' ? 'day' : period)
  const queryClient = useQueryClient()

  const { data: allocation } = useQuery({
    queryKey: ['portfolio-allocation'],
    queryFn: () => api.getAllocation(),
  })

  const { data: modelPerformance } = useQuery({
    queryKey: ['model-performance-list'],
    queryFn: () => api.listModelPerformance(),
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['performance'] })
    queryClient.invalidateQueries({ queryKey: ['portfolio-allocation'] })
    queryClient.invalidateQueries({ queryKey: ['model-performance-list'] })
    toast.success('Performance data refreshed')
  }

  const handleExport = () => {
    if (!displayMetrics) {
      toast.error('No performance data to export')
      return
    }

    const data = {
      period,
      total_pnl: displayMetrics.total_pnl,
      total_pnl_pct: displayMetrics.total_pnl_pct,
      sharpe_ratio: displayMetrics.sharpe_ratio,
      max_drawdown: displayMetrics.max_drawdown,
      max_drawdown_pct: displayMetrics.max_drawdown_pct,
      win_rate: displayMetrics.win_rate,
      total_trades: displayMetrics.total_trades,
      winning_trades: displayMetrics.winning_trades,
      losing_trades: displayMetrics.losing_trades,
      profit_factor: displayMetrics.profit_factor,
      expectancy: displayMetrics.expectancy,
      exported_at: new Date().toISOString(),
    }

    const json = JSON.stringify(data, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `portfolio-performance-${period}-${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('Performance data exported')
  }

  if (isLoading && !metrics) {
    return <LoadingSpinner />
  }

  const displayMetrics = metrics as PortfolioMetrics | undefined

  return (
    <div className="space-y-6">
      <PageHeader
        title="Portfolio Performance"
        description={`Overall performance metrics across all models (${period.replace('_', ' ')})`}
        actions={
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isLoading}
              className="gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              disabled={!displayMetrics}
              className="gap-2"
            >
              <Download className="h-4 w-4" />
              Export
            </Button>
            <HealthDot 
              status={displayMetrics && displayMetrics.total_pnl >= 0 ? 'ok' : displayMetrics ? 'warn' : 'error'} 
              label={displayMetrics ? formatCurrency(displayMetrics.total_pnl) : 'No data'}
            />
          </div>
        }
      />

      {/* Time Range Filter */}
      <div className="flex gap-2">
        {periods.map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
              period === p
                ? 'bg-primary text-primary-foreground'
                : 'hover:bg-accent'
            }`}
          >
            {p.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
          </button>
        ))}
      </div>

      {/* Key Metrics Cards */}
      {displayMetrics && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Total P&L</CardTitle>
            </CardHeader>
            <CardContent>
              <p className={`text-2xl font-bold ${displayMetrics.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(displayMetrics.total_pnl)}
              </p>
              {displayMetrics.total_pnl_pct !== undefined && (
                <p className="text-sm text-muted-foreground">
                  {formatPercent(displayMetrics.total_pnl_pct)}
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Sharpe Ratio</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {displayMetrics.sharpe_ratio?.toFixed(2) || 'N/A'}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Max Drawdown</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-red-600">
                {displayMetrics.max_drawdown_pct !== undefined
                  ? formatPercent(displayMetrics.max_drawdown_pct)
                  : displayMetrics.max_drawdown
                  ? formatCurrency(displayMetrics.max_drawdown)
                  : 'N/A'}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Win Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{formatPercent(displayMetrics.win_rate != null ? displayMetrics.win_rate * 100 : null)}</p>
              <p className="text-sm text-muted-foreground">
                {displayMetrics.winning_trades} / {displayMetrics.total_trades} trades
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Additional Metrics */}
      {displayMetrics && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Profit Factor</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {displayMetrics.profit_factor?.toFixed(2) || 'N/A'}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Expectancy</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {displayMetrics.expectancy ? formatCurrency(displayMetrics.expectancy) : 'N/A'}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Total Trades</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{displayMetrics.total_trades}</p>
              <p className="text-sm text-muted-foreground">
                {displayMetrics.winning_trades} wins, {displayMetrics.losing_trades} losses
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Equity Curve Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Portfolio Equity Curve</CardTitle>
          <CardDescription>Portfolio value over time with drawdown overlay</CardDescription>
        </CardHeader>
        <CardContent>
          {equityCurve && equityCurve.length > 0 ? (
            <EquityCurveChart data={equityCurve} showDrawdown={true} />
          ) : (
            <p className="text-muted-foreground">No equity curve data available</p>
          )}
        </CardContent>
      </Card>

      {/* Model Contributions */}
      {modelPerformance && modelPerformance.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Model Contributions</CardTitle>
            <CardDescription>Performance breakdown by model</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Model</th>
                    <th className="text-right p-2">P&L</th>
                    <th className="text-right p-2">Win Rate</th>
                    <th className="text-right p-2">Sharpe</th>
                    <th className="text-right p-2">Trades</th>
                    <th className="text-right p-2">Contribution</th>
                  </tr>
                </thead>
                <tbody>
                  {modelPerformance.map((model) => {
                    const contribution = displayMetrics?.total_pnl && model.total_pnl != null
                      ? (model.total_pnl / displayMetrics.total_pnl) * 100
                      : 0
                    const contributionValue = contribution != null && !isNaN(contribution) ? contribution : 0
                    return (
                      <tr key={model.model_id} className="border-b">
                        <td className="p-2">Model {model.model_id}</td>
                        <td className={`text-right p-2 ${model.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {formatCurrency(model.total_pnl)}
                        </td>
                        <td className="text-right p-2">{formatPercent(model.win_rate != null ? model.win_rate * 100 : null)}</td>
                        <td className="text-right p-2">{model.sharpe_ratio?.toFixed(2) || 'N/A'}</td>
                        <td className="text-right p-2">{model.total_trades}</td>
                        <td className="text-right p-2">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-24 bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-blue-600 h-2 rounded-full"
                                style={{ width: `${Math.abs(contributionValue)}%` }}
                              />
                            </div>
                            <span>{contributionValue.toFixed(1)}%</span>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* P&L Breakdown */}
      {breakdown && breakdown.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>P&L Breakdown</CardTitle>
            <CardDescription>Performance by time period</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Period</th>
                    <th className="text-right p-2">P&L</th>
                    <th className="text-right p-2">Trades</th>
                    <th className="text-right p-2">Win Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {breakdown.map((item: PerformanceBreakdown, idx: number) => (
                    <tr key={idx} className="border-b">
                      <td className="p-2">{item.period}</td>
                      <td className={`text-right p-2 ${item.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {formatCurrency(item.pnl)}
                      </td>
                      <td className="text-right p-2">{item.trades}</td>
                      <td className="text-right p-2">{formatPercent(item.win_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Allocation */}
      {allocation && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Currency Pair Allocation</CardTitle>
            </CardHeader>
            <CardContent>
              {allocation.by_pair && typeof allocation.by_pair === 'object' && Object.keys(allocation.by_pair).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(allocation.by_pair).map(([pair, value]) => (
                    <div key={pair} className="flex items-center justify-between">
                      <span>{pair}</span>
                      <span className="font-medium">{formatCurrency(value as number)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground">No open positions</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Model Allocation</CardTitle>
            </CardHeader>
            <CardContent>
              {allocation.by_model && typeof allocation.by_model === 'object' && Object.keys(allocation.by_model).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(allocation.by_model).map(([model, value]) => (
                    <div key={model} className="flex items-center justify-between">
                      <span>{model}</span>
                      <span className="font-medium">{formatCurrency(value as number)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground">No active models</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
