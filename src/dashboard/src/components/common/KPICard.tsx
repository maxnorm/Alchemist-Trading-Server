import { ReactNode } from 'react'
import { cn } from '@/utils/cn'
import { TrendingUp, TrendingDown } from 'lucide-react'

export type KPIDensity = 'comfortable' | 'dense' | 'ultra-dense'
export type KPIStatus = 'positive' | 'negative' | 'neutral' | 'warning'

export interface KPICardProps {
  label: string
  value: string | number
  delta?: {
    value: string | number
    status?: KPIStatus
  }
  icon?: ReactNode
  sparkline?: ReactNode
  density?: KPIDensity
  status?: KPIStatus
  className?: string
  loading?: boolean
}

const densityClasses: Record<KPIDensity, string> = {
  comfortable: 'p-6',
  dense: 'p-4',
  'ultra-dense': 'p-3',
}

const statusColors: Record<KPIStatus, string> = {
  positive: 'text-success',
  negative: 'text-destructive',
  neutral: 'text-foreground',
  warning: 'text-warning',
}

/**
 * KPICard - Dense, data-focused metric display
 * Supports density variants, deltas, sparklines, and status indicators
 */
export function KPICard({
  label,
  value,
  delta,
  icon,
  sparkline,
  density = 'dense',
  status = 'neutral',
  className,
  loading = false,
}: KPICardProps) {
  if (loading) {
    return (
      <div
        className={cn(
          'rounded-sm border border-border bg-card',
          densityClasses[density],
          className
        )}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="h-3 w-24 bg-mono-300 animate-pulse rounded" />
          <div className="h-4 w-4 bg-mono-300 animate-pulse rounded" />
        </div>
        <div className="h-7 w-32 bg-mono-300 animate-pulse rounded mb-1" />
        <div className="h-3 w-20 bg-mono-300 animate-pulse rounded" />
      </div>
    )
  }

  const deltaStatus = delta?.status || status

  return (
    <div
      className={cn(
        'rounded-sm border border-border bg-card transition-colors',
        'hover:border-orange-400/50',
        densityClasses[density],
        className
      )}
    >
      {/* Header: Label + Icon */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          {label}
        </span>
        {icon && (
          <div className="text-muted-foreground flex-shrink-0">
            {icon}
          </div>
        )}
      </div>

      {/* Value */}
      <div className={cn('text-2xl font-bold font-mono-data', statusColors[status])}>
        {value}
      </div>

      {/* Delta or Sparkline */}
      {delta && (
        <div className={cn('flex items-center gap-1 mt-1 text-sm', statusColors[deltaStatus])}>
          {deltaStatus === 'positive' && <TrendingUp className="h-3 w-3" />}
          {deltaStatus === 'negative' && <TrendingDown className="h-3 w-3" />}
          <span className="font-medium">{delta.value}</span>
        </div>
      )}

      {sparkline && (
        <div className="mt-2 h-8 w-full">
          {sparkline}
        </div>
      )}
    </div>
  )
}
