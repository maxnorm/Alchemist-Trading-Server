import { format, formatDistance } from 'date-fns'

export function formatCurrency(value: number | null | undefined, currency: string = 'USD'): string {
  if (value == null || isNaN(value)) {
    return 'N/A'
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(value)
}

export function formatPercent(value: number | null | undefined, decimals: number = 2): string {
  if (value == null || isNaN(value)) {
    return 'N/A'
  }
  return `${value.toFixed(decimals)}%`
}

export function formatNumber(value: number | null | undefined, decimals: number = 2): string {
  if (value == null || isNaN(value)) {
    return 'N/A'
  }
  return value.toFixed(decimals)
}

export function formatDate(date: string | Date, formatStr: string = 'PPp'): string {
  return format(new Date(date), formatStr)
}

export function formatRelativeTime(date: string | Date): string {
  return formatDistance(new Date(date), new Date(), { addSuffix: true })
}

export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`
  } else {
    return `${secs}s`
  }
}
