import { ReactNode } from 'react'
import { cn } from '@/utils/cn'

export type TableDensity = 'comfortable' | 'dense' | 'ultra-dense'

export interface DataTableProps {
  children: ReactNode
  density?: TableDensity
  stickyHeader?: boolean
  className?: string
}

const densityClasses: Record<TableDensity, string> = {
  comfortable: '[&_th]:py-3 [&_td]:py-3',
  dense: '[&_th]:py-2 [&_td]:py-2',
  'ultra-dense': '[&_th]:py-1 [&_td]:py-1',
}

/**
 * DataTable - Dense table wrapper with sticky headers and density variants
 * Wraps native table elements with consistent styling
 */
export function DataTable({
  children,
  density = 'dense',
  stickyHeader = true,
  className,
}: DataTableProps) {
  return (
    <div className={cn('relative overflow-auto border border-border rounded-sm', className)}>
      <table
        className={cn(
          'w-full text-sm',
          densityClasses[density],
          stickyHeader && '[&_thead]:sticky [&_thead]:top-0 [&_thead]:z-10 [&_thead]:bg-mono-300'
        )}
      >
        {children}
      </table>
    </div>
  )
}

export interface DataTableHeaderProps {
  children: ReactNode
  className?: string
}

export function DataTableHeader({ children, className }: DataTableHeaderProps) {
  return (
    <thead className={cn('border-b border-border bg-mono-300', className)}>
      {children}
    </thead>
  )
}

export interface DataTableBodyProps {
  children: ReactNode
  className?: string
}

export function DataTableBody({ children, className }: DataTableBodyProps) {
  return (
    <tbody className={cn('[&_tr]:border-b [&_tr]:border-border last:[&_tr]:border-0', className)}>
      {children}
    </tbody>
  )
}

export interface DataTableRowProps {
  children: ReactNode
  onClick?: () => void
  className?: string
}

export function DataTableRow({ children, onClick, className }: DataTableRowProps) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        'transition-colors hover:bg-mono-300/50',
        onClick && 'cursor-pointer',
        className
      )}
    >
      {children}
    </tr>
  )
}

export interface DataTableCellProps {
  children: ReactNode
  header?: boolean
  align?: 'left' | 'center' | 'right'
  mono?: boolean
  className?: string
}

export function DataTableCell({
  children,
  header = false,
  align = 'left',
  mono = false,
  className,
}: DataTableCellProps) {
  const Tag = header ? 'th' : 'td'
  
  return (
    <Tag
      className={cn(
        'px-4 text-left',
        header && 'text-xs font-medium text-muted-foreground uppercase tracking-wider',
        !header && 'text-foreground',
        align === 'center' && 'text-center',
        align === 'right' && 'text-right',
        mono && 'font-mono-data',
        className
      )}
    >
      {children}
    </Tag>
  )
}
