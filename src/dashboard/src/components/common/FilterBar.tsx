import { ReactNode } from 'react'
import { cn } from '@/utils/cn'
import { X } from 'lucide-react'

export interface FilterChip {
  id: string
  label: string
  value: string
}

export interface FilterChipsProps {
  filters: FilterChip[]
  onRemove: (id: string) => void
  onClear?: () => void
  className?: string
}

/**
 * FilterChips - Display active filters as removable chips
 */
export function FilterChips({ filters, onRemove, onClear, className }: FilterChipsProps) {
  if (filters.length === 0) return null

  return (
    <div className={cn('flex items-center gap-2 flex-wrap', className)}>
      <span className="text-xs text-muted-foreground">Filters:</span>
      {filters.map((filter) => (
        <button
          key={filter.id}
          onClick={() => onRemove(filter.id)}
          className={cn(
            'inline-flex items-center gap-1.5 px-2 py-1 rounded-sm',
            'text-xs font-medium',
            'bg-orange-400/10 text-orange-400 border border-orange-400/20',
            'hover:bg-orange-400/20 transition-colors'
          )}
        >
          <span>{filter.label}: {filter.value}</span>
          <X className="h-3 w-3" />
        </button>
      ))}
      {onClear && filters.length > 1 && (
        <button
          onClick={onClear}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Clear all
        </button>
      )}
    </div>
  )
}

export interface SearchInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}

/**
 * SearchInput - Styled search input for filtering
 */
export function SearchInput({ value, onChange, placeholder = 'Search...', className }: SearchInputProps) {
  return (
    <div className={cn('relative', className)}>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          'w-full px-3 py-2 pl-9 rounded-sm',
          'bg-mono-300 border border-border',
          'text-sm text-foreground placeholder:text-muted-foreground',
          'focus:outline-none focus:ring-2 focus:ring-orange-400 focus:border-orange-400',
          'transition-colors'
        )}
      />
      <svg
        className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
    </div>
  )
}

export interface FilterBarProps {
  search?: {
    value: string
    onChange: (value: string) => void
    placeholder?: string
  }
  filters?: FilterChip[]
  onRemoveFilter?: (id: string) => void
  onClearFilters?: () => void
  actions?: ReactNode
  className?: string
}

/**
 * FilterBar - Combined search, filter chips, and actions
 */
export function FilterBar({
  search,
  filters,
  onRemoveFilter,
  onClearFilters,
  actions,
  className,
}: FilterBarProps) {
  return (
    <div className={cn('flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between', className)}>
      <div className="flex-1 flex flex-col gap-3 sm:flex-row sm:items-center">
        {search && (
          <SearchInput
            value={search.value}
            onChange={search.onChange}
            placeholder={search.placeholder}
            className="sm:w-64"
          />
        )}
        {filters && onRemoveFilter && (
          <FilterChips
            filters={filters}
            onRemove={onRemoveFilter}
            onClear={onClearFilters}
          />
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-2 flex-shrink-0">
          {actions}
        </div>
      )}
    </div>
  )
}
