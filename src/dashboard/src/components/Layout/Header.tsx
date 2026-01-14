import { useTradingStore } from '@/stores/tradingStore'
import { useUI } from '@/contexts/UIContext'
import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { UserButton, useUser } from '@clerk/clerk-react'
import { StatusBadge } from '@/components/common/StatusBadge'

export function Header() {
  const { theme, toggleTheme } = useUI()
  const { status } = useTradingStore()
  const { user, isLoaded } = useUser()

  return (
    <header className="flex h-16 items-center border-b border-border bg-mono-200 dark:bg-mono-200 px-6">
      <div className="flex flex-1 items-center gap-3">
        {status?.kill_switch_active && (
          <StatusBadge severity="error" dot>
            Kill Switch Active
          </StatusBadge>
        )}
        {status?.circuit_breaker_active && (
          <StatusBadge severity="warning" dot>
            Circuit Breaker Active
          </StatusBadge>
        )}
        {status?.is_active && !status.kill_switch_active && !status.circuit_breaker_active && (
          <StatusBadge severity="success" dot>
            Trading Active
          </StatusBadge>
        )}
      </div>
      <div className="flex items-center gap-3">
        {isLoaded && user && (
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground hidden sm:inline font-mono">
              {user.emailAddresses[0]?.emailAddress}
            </span>
            <UserButton afterSignOutUrl="/sign-in" />
          </div>
        )}
        <Button 
          variant="ghost" 
          size="icon" 
          onClick={toggleTheme} 
          aria-label="Toggle theme"
          className="hover:bg-orange-400/10"
        >
          {theme === 'light' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
        </Button>
      </div>
    </header>
  )
}
