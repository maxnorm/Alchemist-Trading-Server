import { ReactNode } from 'react'
import { cn } from '@/utils/cn'

export interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

/**
 * EmptyState - Displayed when no data is available
 * Uses subtle halftone texture background
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center',
        'py-12 px-6 text-center',
        'halftone-texture-subtle rounded-sm border border-border',
        className
      )}
    >
      {icon && (
        <div className="mb-4 text-muted-foreground">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-semibold text-foreground mb-2">
        {title}
      </h3>
      {description && (
        <p className="text-sm text-muted-foreground max-w-md mb-4">
          {description}
        </p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export interface ErrorStateProps {
  title?: string
  message: string
  action?: ReactNode
  className?: string
}

/**
 * ErrorState - Displayed when an error occurs
 */
export function ErrorState({
  title = 'Error',
  message,
  action,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center',
        'py-12 px-6 text-center',
        'rounded-sm border border-destructive/20 bg-destructive/5',
        className
      )}
    >
      <div className="mb-4 text-destructive">
        <svg
          className="h-12 w-12"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">
        {title}
      </h3>
      <p className="text-sm text-muted-foreground max-w-md mb-4">
        {message}
      </p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export interface LoadingStateProps {
  message?: string
  className?: string
}

/**
 * LoadingState - Displayed while data is loading
 */
export function LoadingState({
  message = 'Loading...',
  className,
}: LoadingStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center',
        'py-12 px-6 text-center',
        className
      )}
    >
      <div className="mb-4">
        <div className="h-8 w-8 border-2 border-orange-400 border-t-transparent rounded-full animate-spin" />
      </div>
      <p className="text-sm text-muted-foreground">
        {message}
      </p>
    </div>
  )
}
