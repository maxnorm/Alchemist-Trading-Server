import { useTradingStore } from '@/stores/tradingStore'
import { useUI } from '@/contexts/UIContext'
import { Moon, Sun, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function Header() {
  const { theme, toggleTheme } = useUI()
  const { status } = useTradingStore()

  return (
    <header className="flex h-16 items-center border-b bg-background px-6">
      <div className="flex flex-1 items-center gap-4">
        {status?.kill_switch_active && (
          <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-1.5 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" />
            <span>Kill Switch Active</span>
          </div>
        )}
        {status?.circuit_breaker_active && (
          <div className="flex items-center gap-2 rounded-md bg-yellow-500/10 px-3 py-1.5 text-sm text-yellow-600 dark:text-yellow-400">
            <AlertTriangle className="h-4 w-4" />
            <span>Circuit Breaker Active</span>
          </div>
        )}
        {status?.is_active && !status.kill_switch_active && !status.circuit_breaker_active && (
          <div className="flex items-center gap-2 rounded-md bg-green-500/10 px-3 py-1.5 text-sm text-green-600 dark:text-green-400">
            <div className="h-2 w-2 rounded-full bg-green-500" />
            <span>Trading Active</span>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme">
          {theme === 'light' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
        </Button>
      </div>
    </header>
  )
}
