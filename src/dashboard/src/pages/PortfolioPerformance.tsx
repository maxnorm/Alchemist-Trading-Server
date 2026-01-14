import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EquityCurveChart } from '@/components/charts/EquityCurveChart'
import { formatCurrency, formatPercent } from '@/utils/formatters'
import { usePeriodFilter } from '@/hooks/usePeriodFilter'
import { usePerformanceMetrics } from '@/features/performance/hooks/usePerformanceMetrics'
import { useEquityCurve } from '@/features/performance/hooks/useEquityCurve'
import { usePerformanceBreakdown } from '@/features/performance/hooks/usePerformanceBreakdown'
import type { PortfolioMetrics, PerformanceBreakdown } from '@/types/performance'

export default function PortfolioPerformance() {
  const { period, setPeriod, periods } = usePeriodFilter('all_time')
  const { metrics, isLoading } = usePerformanceMetrics(period)
  const { equityCurve } = useEquityCurve()
  const { breakdown } = usePerformanceBreakdown(period === 'all_time' ? 'day' : period)

  const { data: allocation } = useQuery({
    queryKey: ['portfolio-allocation'],
    queryFn: () => api.getAllocation(),
  })

  const { data: modelPerformance } = useQuery({
    queryKey: ['model-performance-list'],
    queryFn: () => api.listModelPerformance(),
  })

  if (isLoading && !metrics) {
    return <LoadingSpinner />
  }

  const displayMetrics = metrics as PortfolioMetrics | undefined

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Portfolio Performance</h1>
        <p className="text-muted-foreground">Overall performance across all models</p>
      </div>

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
