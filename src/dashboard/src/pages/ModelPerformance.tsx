import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EquityCurveChart } from '@/components/charts/EquityCurveChart'
import { formatCurrency, formatPercent, formatDuration } from '@/utils/formatters'
import { usePeriodFilter } from '@/hooks/usePeriodFilter'
import { usePerformanceMetrics } from '@/features/performance/hooks/usePerformanceMetrics'
import { useEquityCurve } from '@/features/performance/hooks/useEquityCurve'
import { PageHeader } from '@/components/common/PageHeader'
import { HealthDot } from '@/components/common/StatusBadge'
import { RefreshCw, Download, ArrowLeft } from 'lucide-react'
import toast from 'react-hot-toast'
import type { Trade } from '@/types/performance'

export default function ModelPerformance() {
  const { modelId } = useParams<{ modelId: string }>()
  const { period, setPeriod, periods } = usePeriodFilter('all_time')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const modelIdNum = modelId ? Number(modelId) : undefined
  const { metrics, isLoading } = usePerformanceMetrics(period, modelIdNum)
  const { equityCurve } = useEquityCurve(modelIdNum)

  const { data: statistics } = useQuery({
    queryKey: ['model-statistics', modelId, period],
    queryFn: () => api.getModelStatistics(Number(modelId!), period),
    enabled: !!modelId,
  })

  const { data: tradesData } = useQuery({
    queryKey: ['model-trades', modelId, page],
    queryFn: () => api.getModelTrades(Number(modelId!), pageSize, (page - 1) * pageSize),
    enabled: !!modelId,
  })

  const { data: comparison } = useQuery({
    queryKey: ['model-comparison', modelId],
    queryFn: () => api.getModelComparison(Number(modelId!)),
    enabled: !!modelId,
  })

  const queryClient = useQueryClient()

  if (!modelId) {
    return <div>No model ID provided</div>
  }

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['performance', modelId] })
    queryClient.invalidateQueries({ queryKey: ['model-statistics', modelId] })
    queryClient.invalidateQueries({ queryKey: ['model-trades', modelId] })
    queryClient.invalidateQueries({ queryKey: ['model-comparison', modelId] })
    toast.success('Model performance data refreshed')
  }

  const handleExport = () => {
    if (!metrics) {
      toast.error('No performance data to export')
      return
    }

    const data = {
      model_id: modelId,
      period,
      metrics: {
        total_pnl: metrics.total_pnl,
        total_pnl_pct: metrics.total_pnl_pct,
        sharpe_ratio: metrics.sharpe_ratio,
        max_drawdown: metrics.max_drawdown,
        win_rate: metrics.win_rate,
        total_trades: metrics.total_trades,
      },
      statistics,
      exported_at: new Date().toISOString(),
    }

    const json = JSON.stringify(data, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `model-${modelId}-performance-${period}-${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('Model performance data exported')
  }

  if (isLoading && !metrics) {
    return <LoadingSpinner />
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Model ${modelId} Performance`}
        description={`Detailed performance metrics and analytics for model ${modelId} (${period.replace('_', ' ')})`}
        breadcrumbs={[
          { label: 'Portfolio Performance', href: '/performance' },
          { label: `Model ${modelId}` },
        ]}
        actions={
          <div className="flex items-center gap-3">
            <Link
              to="/performance"
              className="inline-flex items-center justify-center gap-2 h-9 px-3 rounded-sm text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 disabled:pointer-events-none disabled:opacity-50 border border-border bg-transparent hover:bg-mono-300 hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Link>
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
              disabled={!metrics}
              className="gap-2"
            >
              <Download className="h-4 w-4" />
              Export
            </Button>
            <HealthDot 
              status={metrics && metrics.total_pnl >= 0 ? 'ok' : metrics ? 'warn' : 'error'} 
              label={metrics ? formatCurrency(metrics.total_pnl) : 'No data'}
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

      {/* Performance Summary */}
      {metrics && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Total P&L</CardTitle>
            </CardHeader>
            <CardContent>
              <p className={`text-2xl font-bold ${metrics.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(metrics.total_pnl)}
              </p>
              {metrics.total_pnl_pct !== undefined && (
                <p className="text-sm text-muted-foreground">
                  {formatPercent(metrics.total_pnl_pct)}
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
                {metrics.sharpe_ratio?.toFixed(2) || 'N/A'}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Max Drawdown</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-red-600">
                {metrics.max_drawdown
                  ? formatCurrency(metrics.max_drawdown)
                  : 'N/A'}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Win Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{formatPercent(metrics.win_rate)}</p>
              <p className="text-sm text-muted-foreground">
                {metrics.total_trades} total trades
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Risk Metrics */}
      {statistics && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Risk Metrics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between">
                <span>Sortino Ratio:</span>
                <span className="font-medium">{statistics.sortino_ratio != null ? statistics.sortino_ratio.toFixed(2) : 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span>Recovery Factor:</span>
                <span className="font-medium">{statistics.recovery_factor != null ? statistics.recovery_factor.toFixed(2) : 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span>Longest Win Streak:</span>
                <span className="font-medium">{statistics.longest_win_streak ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span>Longest Loss Streak:</span>
                <span className="font-medium text-red-600">{statistics.longest_loss_streak ?? 0}</span>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Trade Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between">
                <span>Average Win:</span>
                <span className="font-medium text-green-600">
                  {statistics.average_win != null ? formatCurrency(statistics.average_win) : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Average Loss:</span>
                <span className="font-medium text-red-600">
                  {statistics.average_loss != null ? formatCurrency(statistics.average_loss) : 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Profit Factor:</span>
                <span className="font-medium">{statistics.profit_factor != null ? statistics.profit_factor.toFixed(2) : 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span>Expectancy:</span>
                <span className="font-medium">
                  {statistics.expectancy != null ? formatCurrency(statistics.expectancy) : 'N/A'}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Timing Analysis */}
      {statistics && (
        <Card>
          <CardHeader>
            <CardTitle>Timing Analysis</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Avg Duration</p>
                <p className="text-lg font-medium">
                  {statistics.avg_duration_seconds != null
                    ? formatDuration(statistics.avg_duration_seconds)
                    : 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Shortest</p>
                <p className="text-lg font-medium">
                  {statistics.min_duration_seconds != null
                    ? formatDuration(statistics.min_duration_seconds)
                    : 'N/A'}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Longest</p>
                <p className="text-lg font-medium">
                  {statistics.max_duration_seconds != null
                    ? formatDuration(statistics.max_duration_seconds)
                    : 'N/A'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Equity Curve Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Model Equity Curve</CardTitle>
          <CardDescription>Model equity over time with drawdown overlay</CardDescription>
        </CardHeader>
        <CardContent>
          {equityCurve && equityCurve.length > 0 ? (
            <EquityCurveChart data={equityCurve} showDrawdown={true} />
          ) : (
            <p className="text-muted-foreground">No equity curve data available</p>
          )}
        </CardContent>
      </Card>

      {/* Recent Trades */}
      {tradesData && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Trades</CardTitle>
            <CardDescription>Trade history with pagination</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Time</th>
                    <th className="text-left p-2">Symbol</th>
                    <th className="text-left p-2">Action</th>
                    <th className="text-right p-2">Entry</th>
                    <th className="text-right p-2">Exit</th>
                    <th className="text-right p-2">Volume</th>
                    <th className="text-right p-2">P&L</th>
                    <th className="text-right p-2">Duration</th>
                    <th className="text-left p-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {tradesData.trades.map((trade: Trade) => (
                    <tr key={trade.id} className="border-b">
                      <td className="p-2">
                        {new Date(trade.entry_time).toLocaleString()}
                      </td>
                      <td className="p-2">{trade.symbol}</td>
                      <td className="p-2">{trade.order_type}</td>
                      <td className="text-right p-2">{trade.entry_price?.toFixed(5)}</td>
                      <td className="text-right p-2">{trade.exit_price?.toFixed(5) || '-'}</td>
                      <td className="text-right p-2">{trade.volume}</td>
                      <td className={`text-right p-2 font-medium ${
                        trade.pnl && trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {trade.pnl ? formatCurrency(trade.pnl) : '-'}
                      </td>
                      <td className="text-right p-2">
                        {trade.exit_time && trade.entry_time
                          ? formatDuration(
                              (new Date(trade.exit_time).getTime() - new Date(trade.entry_time).getTime()) / 1000
                            )
                          : '-'}
                      </td>
                      <td className="p-2">
                        <span className={`px-2 py-1 rounded text-xs ${
                          trade.status === 'OPEN' ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'
                        }`}>
                          {trade.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {tradesData.total > pageSize && (
              <div className="flex justify-between items-center mt-4">
                <p className="text-sm text-muted-foreground">
                  Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, tradesData.total)} of {tradesData.total} trades
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1 border rounded disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    disabled={page * pageSize >= tradesData.total}
                    className="px-3 py-1 border rounded disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Paper vs Live Comparison */}
      {comparison && (
        <Card>
          <CardHeader>
            <CardTitle>Paper vs Live Comparison</CardTitle>
            <CardDescription>Compare paper trading performance with live trading</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Metric</th>
                    <th className="text-right p-2">Paper (Demo)</th>
                    <th className="text-right p-2">Live Account</th>
                    <th className="text-right p-2">Difference</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b">
                    <td className="p-2">Sharpe Ratio</td>
                    <td className="text-right p-2">{comparison.paper?.sharpe_ratio != null ? comparison.paper.sharpe_ratio.toFixed(2) : 'N/A'}</td>
                    <td className="text-right p-2">{comparison.live?.sharpe_ratio != null ? comparison.live.sharpe_ratio.toFixed(2) : 'N/A'}</td>
                    <td className="text-right p-2">
                      {comparison.difference?.sharpe_ratio != null
                        ? `${comparison.difference.sharpe_ratio >= 0 ? '+' : ''}${comparison.difference.sharpe_ratio.toFixed(2)}`
                        : 'N/A'}
                    </td>
                  </tr>
                  <tr className="border-b">
                    <td className="p-2">Win Rate</td>
                    <td className="text-right p-2">{comparison.paper?.win_rate != null ? formatPercent(comparison.paper.win_rate) : 'N/A'}</td>
                    <td className="text-right p-2">{comparison.live?.win_rate != null ? formatPercent(comparison.live.win_rate) : 'N/A'}</td>
                    <td className="text-right p-2">
                      {comparison.difference?.win_rate != null
                        ? `${comparison.difference.win_rate >= 0 ? '+' : ''}${formatPercent(comparison.difference.win_rate)}`
                        : 'N/A'}
                    </td>
                  </tr>
                  <tr className="border-b">
                    <td className="p-2">Profit Factor</td>
                    <td className="text-right p-2">{comparison.paper?.profit_factor != null ? comparison.paper.profit_factor.toFixed(2) : 'N/A'}</td>
                    <td className="text-right p-2">{comparison.live?.profit_factor != null ? comparison.live.profit_factor.toFixed(2) : 'N/A'}</td>
                    <td className="text-right p-2">
                      {comparison.difference?.profit_factor != null
                        ? `${comparison.difference.profit_factor >= 0 ? '+' : ''}${comparison.difference.profit_factor.toFixed(2)}`
                        : 'N/A'}
                    </td>
                  </tr>
                  <tr>
                    <td className="p-2">Avg Trade</td>
                    <td className="text-right p-2">
                      {comparison.paper?.avg_trade != null ? formatCurrency(comparison.paper.avg_trade) : 'N/A'}
                    </td>
                    <td className="text-right p-2">
                      {comparison.live?.avg_trade != null ? formatCurrency(comparison.live.avg_trade) : 'N/A'}
                    </td>
                    <td className="text-right p-2">
                      {comparison.difference?.avg_trade != null
                        ? `${comparison.difference.avg_trade >= 0 ? '+' : ''}${formatCurrency(comparison.difference.avg_trade)}`
                        : 'N/A'}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
