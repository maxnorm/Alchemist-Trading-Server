import * as React from 'react'
import { cn } from '@/utils/cn'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'
  size?: 'default' | 'sm' | 'lg' | 'icon'
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    return (
      <button
        className={cn(
          'inline-flex items-center justify-center rounded-sm text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 disabled:pointer-events-none disabled:opacity-50',
          {
            'bg-orange-400 text-white hover:bg-orange-300 dark:text-mono-100': variant === 'default',
            'bg-destructive text-destructive-foreground hover:bg-destructive/90':
              variant === 'destructive',
            'border border-border bg-transparent hover:bg-mono-300 hover:text-foreground':
              variant === 'outline',
            'bg-mono-300 text-foreground hover:bg-mono-400': variant === 'secondary',
            'hover:bg-mono-300 hover:text-foreground': variant === 'ghost',
            'text-orange-400 underline-offset-4 hover:text-orange-300': variant === 'link',
            'h-10 px-4 py-2': size === 'default',
            'h-9 rounded-sm px-3': size === 'sm',
            'h-11 rounded-sm px-8': size === 'lg',
            'h-10 w-10': size === 'icon',
          },
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button }
