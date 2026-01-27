import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/utils/cn'

export function Layout() {
  const { sidebarCollapsed } = useUIStore()
  
  return (
    <div className="flex h-screen overflow-hidden bg-mono-100 dark:bg-mono-100">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className={cn(
          "flex-1 overflow-y-auto bg-mono-100 dark:bg-mono-100 py-4 transition-all duration-300",
          sidebarCollapsed ? "px-16" : "px-6"
        )}>
          {/* Suspense boundary inside Layout - header/sidebar always visible */}
          <Suspense
            fallback={
              <div className="flex items-center justify-center h-full">
                <LoadingSpinner />
              </div>
            }
          >
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
