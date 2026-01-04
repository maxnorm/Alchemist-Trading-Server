import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCurrency, formatPercent } from '@/utils/formatters'
import { ArrowRight } from 'lucide-react'
import type { Position } from '@/types/trading'

interface ActivePositionsProps {
  positions: Position[]
}

export function ActivePositions({ positions }: ActivePositionsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Active Positions</CardTitle>
        <CardDescription>
          {positions.length} open position{positions.length !== 1 ? 's' : ''}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {positions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No open positions</p>
        ) : (
          <div className="space-y-2">
            {positions.slice(0, 5).map((position) => (
              <div
                key={position.id}
                className="flex items-center justify-between rounded-md border p-3 text-sm"
              >
                <div>
                  <div className="font-medium">{position.symbol}</div>
                  <div className="text-xs text-muted-foreground">
                    {position.order_type} {position.volume} @ {position.entry_price.toFixed(5)}
                  </div>
                </div>
                <div className="text-right">
                  <div
                    className={`font-medium ${
                      position.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}
                  >
                    {formatCurrency(position.unrealized_pnl)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {formatPercent(position.unrealized_pnl_pct)}
                  </div>
                </div>
              </div>
            ))}
            {positions.length > 5 && (
              <Link
                to="/trading"
                className="flex items-center gap-2 text-sm text-primary hover:underline mt-2"
              >
                View all {positions.length} positions
                <ArrowRight className="h-4 w-4" />
              </Link>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
