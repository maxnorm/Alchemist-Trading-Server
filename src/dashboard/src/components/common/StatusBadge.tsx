import { ReactNode } from 'react'
import { cn } from '@/utils/cn'

export type StatusSeverity = 'success' | 'warning' | 'error' | 'info' | 'neutral'

export interface StatusBadgeProps {
  severity: StatusSeverity
  children: ReactNode
  className?: string
  dot?: boolean
}

const severityStyles: Record<StatusSeverity, string> = {
  success: 'bg-success/10 text-success border-success/20',
  warning: 'bg-warning/10 text-warning border-warning/20',
  error: 'bg-destructive/10 text-destructive border-destructive/20',
  info: 'bg-orange-400/10 text-orange-400 border-orange-400/20',
  neutral: 'bg-mono-300 text-mono-600 border-mono-400',
}

const dotStyles: Record<StatusSeverity, string> = {
  success: 'bg-success',
  warning: 'bg-warning',
  error: 'bg-destructive',
  info: 'bg-orange-400',
  neutral: 'bg-mono-500',
}

/**
 * StatusBadge - Compact status indicator with optional dot
 */
export function StatusBadge({ severity, children, className, dot = false }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm',
        'text-xs font-medium border',
        severityStyles[severity],
        className
      )}
    >
      {dot && (
        <span className={cn('h-1.5 w-1.5 rounded-full', dotStyles[severity])} />
      )}
      {children}
    </span>
  )
}

export interface HealthDotProps {
  status: 'ok' | 'warn' | 'error' | 'unknown'
  label?: string
  className?: string
}

const healthDotStyles = {
  ok: 'bg-success',
  warn: 'bg-warning',
  error: 'bg-destructive',
  unknown: 'bg-mono-500',
}

/**
 * HealthDot - Minimal status indicator (just a colored dot + optional label)
 */
export function HealthDot({ status, label, className }: HealthDotProps) {
  return (
    <div className={cn('inline-flex items-center gap-2', className)}>
      <span className={cn('h-2 w-2 rounded-full', healthDotStyles[status])} />
      {label && <span className="text-xs text-muted-foreground">{label}</span>}
    </div>
  )
}
