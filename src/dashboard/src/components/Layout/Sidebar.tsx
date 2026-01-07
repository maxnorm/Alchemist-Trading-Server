import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/utils/cn'
import {
  Home,
  FlaskConical,
  Search,
  Activity,
  List,
  Bot,
  TrendingUp,
  Building2,
  BarChart3,
} from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: Home },
  { name: 'Experiments', href: '/experiments', icon: FlaskConical },
  { name: 'Hyperparameter Search', href: '/hyperparameters', icon: Search },
  { name: 'Training Monitor', href: '/training', icon: Activity },
  { name: 'Feature Catalog', href: '/features', icon: List },
  { name: 'Model Registry', href: '/models', icon: Bot },
  { name: 'Live Trading', href: '/trading', icon: TrendingUp },
  { name: 'Accounts', href: '/accounts', icon: Building2 },
  { name: 'Performance', href: '/performance', icon: BarChart3 },
]

export function Sidebar() {
  const location = useLocation()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()

  return (
    <div
      className={cn(
        'flex h-screen flex-col border-r bg-card transition-all duration-300',
        sidebarCollapsed ? 'w-16' : 'w-64'
      )}
    >
      <div className="flex h-16 items-center border-b px-4">
        {!sidebarCollapsed && (
          <h1 className="text-xl font-bold">Alchemist</h1>
        )}
        <button
          onClick={toggleSidebar}
          className="ml-auto rounded-md p-2 hover:bg-accent"
          aria-label="Toggle sidebar"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d={sidebarCollapsed ? 'M9 5l7 7-7 7' : 'M15 19l-7-7 7-7'}
            />
          </svg>
        </button>
      </div>
      <nav className="flex-1 space-y-1 p-4">
        {navigation.map((item) => {
          const isActive = 
            (item.href === '/dashboard' && (location.pathname === '/' || location.pathname === '/dashboard')) ||
            (item.href !== '/dashboard' && (location.pathname === item.href || location.pathname.startsWith(item.href + '/')))
          const Icon = item.icon
          return (
            <Link
              key={item.name}
              to={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg text-sm font-medium transition-colors',
                'border-l-2',
                sidebarCollapsed 
                  ? 'justify-center px-2 py-3' 
                  : 'px-3 py-2',
                isActive
                  ? 'border-primary text-foreground bg-accent/50'
                  : 'border-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground'
              )}
              title={sidebarCollapsed ? item.name : undefined}
            >
              <Icon className="h-5 w-5 flex-shrink-0" />
              {!sidebarCollapsed && <span>{item.name}</span>}
            </Link>
          )
        })}
      </nav>
    </div>
  )
}
