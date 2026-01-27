/**
 * Common Component Library - Terminal/Print Theme
 * Reusable components with density variants and GSAP animations
 */

// Layout & Structure
export { PageHeader } from './PageHeader'
export type { PageHeaderProps } from './PageHeader'

// Cards
export { 
  DenseCard, 
  DenseCardHeader, 
  DenseCardContent, 
  DenseCardFooter 
} from './DenseCard'
export type { 
  DenseCardProps, 
  DenseCardHeaderProps, 
  DenseCardContentProps, 
  DenseCardFooterProps,
  CardDensity 
} from './DenseCard'

// KPI & Metrics
export { KPICard } from './KPICard'
export type { KPICardProps, KPIDensity, KPIStatus } from './KPICard'

// Status & Indicators
export { StatusBadge, HealthDot } from './StatusBadge'
export type { StatusBadgeProps, HealthDotProps, StatusSeverity } from './StatusBadge'

// Data Display
export { 
  DataTable, 
  DataTableHeader, 
  DataTableBody, 
  DataTableRow, 
  DataTableCell 
} from './DataTable'
export type { 
  DataTableProps, 
  DataTableHeaderProps, 
  DataTableBodyProps, 
  DataTableRowProps, 
  DataTableCellProps,
  TableDensity 
} from './DataTable'

// Filters & Search
export { FilterBar, FilterChips, SearchInput } from './FilterBar'
export type { 
  FilterBarProps, 
  FilterChipsProps, 
  SearchInputProps, 
  FilterChip 
} from './FilterBar'

// States
export { EmptyState, ErrorState, LoadingState } from './EmptyState'
export type { EmptyStateProps, ErrorStateProps, LoadingStateProps } from './EmptyState'

// Animation
export { AnimatedPanel, AnimatedList } from './AnimatedPanel'
export type { AnimatedPanelProps, AnimatedListProps } from './AnimatedPanel'

// Legacy components (kept for compatibility)
export { ErrorBoundary } from './ErrorBoundary'
export { LoadingSpinner } from './LoadingSpinner'
