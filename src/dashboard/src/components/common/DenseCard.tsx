import { ReactNode } from 'react'
import { cn } from '@/utils/cn'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'

export type CardDensity = 'comfortable' | 'dense' | 'ultra-dense'

export interface DenseCardProps {
  children: ReactNode
  density?: CardDensity
  className?: string
  hover?: boolean
}

const densityClasses: Record<CardDensity, string> = {
  comfortable: '[&_.card-header]:p-6 [&_.card-content]:p-6 [&_.card-footer]:p-6',
  dense: '[&_.card-header]:p-4 [&_.card-content]:p-4 [&_.card-footer]:p-4',
  'ultra-dense': '[&_.card-header]:p-3 [&_.card-content]:p-3 [&_.card-footer]:p-3',
}

/**
 * DenseCard - Wrapper around shadcn Card with density variants
 * Maintains ZEEX-like compact layouts
 */
export function DenseCard({
  children,
  density = 'dense',
  className,
  hover = false,
}: DenseCardProps) {
  return (
    <Card
      className={cn(
        'rounded-sm border-border',
        densityClasses[density],
        hover && 'transition-colors hover:border-orange-400/50',
        className
      )}
    >
      {children}
    </Card>
  )
}

export interface DenseCardHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
  className?: string
}

/**
 * DenseCardHeader - Card header with title, description, and actions
 */
export function DenseCardHeader({
  title,
  description,
  actions,
  className,
}: DenseCardHeaderProps) {
  return (
    <CardHeader className={cn('card-header flex flex-row items-start justify-between space-y-0', className)}>
      <div className="flex-1 min-w-0">
        <CardTitle className="text-base font-semibold">{title}</CardTitle>
        {description && (
          <CardDescription className="text-xs mt-1">{description}</CardDescription>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 flex-shrink-0 ml-4">
          {actions}
        </div>
      )}
    </CardHeader>
  )
}

export interface DenseCardContentProps {
  children: ReactNode
  className?: string
}

/**
 * DenseCardContent - Card content area
 */
export function DenseCardContent({ children, className }: DenseCardContentProps) {
  return (
    <CardContent className={cn('card-content pt-0', className)}>
      {children}
    </CardContent>
  )
}

export interface DenseCardFooterProps {
  children: ReactNode
  className?: string
}

/**
 * DenseCardFooter - Card footer area
 */
export function DenseCardFooter({ children, className }: DenseCardFooterProps) {
  return (
    <CardFooter className={cn('card-footer pt-0', className)}>
      {children}
    </CardFooter>
  )
}
