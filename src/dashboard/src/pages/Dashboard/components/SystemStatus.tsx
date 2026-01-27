import { Link } from 'react-router-dom'
import { formatCurrency } from '@/utils/formatters'
import { CheckCircle2, XCircle, AlertTriangle, ArrowRight } from 'lucide-react'
import type { TradingStatus } from '@/types/trading'
import type { CircuitBreakerStatus } from '@/types/trading'
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard'

interface SystemStatusProps {
  status: TradingStatus | null
  circuitBreaker: CircuitBreakerStatus | null
}

export function SystemStatus({ status, circuitBreaker }: SystemStatusProps) {
  return (
    <DenseCard density="dense" hover>
      <DenseCardHeader
        title="System Status"
        description="Current system health and trading status"
      />
      <DenseCardContent className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Trading Status</span>
          <div className="flex items-center gap-2">
            {status?.is_active ? (
              <>
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <span className="text-sm font-medium text-green-600">Active</span>
              </>
            ) : (
              <>
                <XCircle className="h-4 w-4 text-red-600" />
                <span className="text-sm font-medium text-red-600">Inactive</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Kill Switch</span>
          <div className="flex items-center gap-2">
            {status?.kill_switch_active ? (
              <>
                <AlertTriangle className="h-4 w-4 text-red-600" />
                <span className="text-sm font-medium text-red-600">Active</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <span className="text-sm font-medium text-green-600">Inactive</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Circuit Breaker</span>
          <div className="flex items-center gap-2">
            {circuitBreaker?.is_active ? (
              <>
                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                <span className="text-sm font-medium text-yellow-600">Triggered</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <span className="text-sm font-medium text-green-600">Normal</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Active Positions</span>
          <span className="text-sm font-medium">{status?.active_positions || 0}</span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Total Equity</span>
          <span className="text-sm font-medium">
            {formatCurrency(status?.total_equity || 0)}
          </span>
        </div>

        <Link
          to="/trading"
          className="flex items-center gap-2 text-sm text-orange-400 hover:text-orange-300 transition-colors mt-3"
        >
          View Trading Controls
          <ArrowRight className="h-4 w-4" />
        </Link>
      </DenseCardContent>
    </DenseCard>
  )
}
