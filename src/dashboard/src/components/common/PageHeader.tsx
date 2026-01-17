import { ReactNode } from 'react'
import { cn } from '@/utils/cn'

export interface PageHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
  breadcrumbs?: { label: string; href?: string }[]
  className?: string
}

/**
 * PageHeader - Consistent page header with title, description, breadcrumbs, and actions
 * Uses halftone texture background for terminal aesthetic
 */
export function PageHeader({
  title,
  description,
  actions,
  breadcrumbs,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        'relative bg-card halftone-texture-subtle border border-orange-400/15',
        'px-6 py-4',
        className
      )}
    >
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="mb-2 flex items-center gap-2 text-xs text-mono-600 dark:text-mono-600">
          {breadcrumbs.map((crumb, idx) => (
            <span key={idx} className="flex items-center gap-2">
              {crumb.href ? (
                <a
                  href={crumb.href}
                  className="hover:text-foreground transition-colors"
                >
                  {crumb.label}
                </a>
              ) : (
                <span className="text-foreground">{crumb.label}</span>
              )}
              {idx < breadcrumbs.length - 1 && (
                <span className="text-mono-500">/</span>
              )}
            </span>
          ))}
        </nav>
      )}

      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            {title}
          </h1>
          {description && (
            <p className="mt-1 text-sm text-mono-600 dark:text-mono-600">{description}</p>
          )}
        </div>

        {actions && (
          <div className="flex items-center gap-2 flex-shrink-0">
            {actions}
          </div>
        )}
      </div>
    </div>
  )
}
