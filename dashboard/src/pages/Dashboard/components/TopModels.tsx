import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCurrency } from '@/utils/formatters'
import { ArrowRight } from 'lucide-react'
import type { ModelMetrics } from '@/types/performance'
import type { Model } from '@/types/model'

interface TopModel extends ModelMetrics {
  model_id: number
  model?: Model
}

interface TopModelsProps {
  topModels: TopModel[]
}

export function TopModels({ topModels }: TopModelsProps) {
  if (topModels.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Top Performing Models</CardTitle>
          <CardDescription>Best performers by total P&L</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No model performance data available</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Top Performing Models</CardTitle>
        <CardDescription>Best performers by total P&L</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {topModels.map((item) => (
            <Link
              key={item.model_id}
              to={`/performance/${item.model_id}`}
              className="flex items-center justify-between rounded-md border p-3 text-sm hover:bg-accent transition-colors"
            >
              <div>
                <div className="font-medium">
                  Model v{item.model?.version || item.model_id}
                </div>
                <div className="text-xs text-muted-foreground">
                  {item.model?.stage || 'Unknown'} • Sharpe: {item.sharpe_ratio?.toFixed(2) || 'N/A'}
                </div>
              </div>
              <div className="text-right">
                <div
                  className={`font-medium ${
                    item.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {formatCurrency(item.total_pnl || 0)}
                </div>
                <div className="text-xs text-muted-foreground">{item.total_trades || 0} trades</div>
              </div>
            </Link>
          ))}
          <Link
            to="/models"
            className="flex items-center gap-2 text-sm text-primary hover:underline mt-2"
          >
            View all models
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
