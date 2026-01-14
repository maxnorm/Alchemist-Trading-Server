import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

export function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-mono-100 dark:bg-mono-100">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto bg-mono-100 dark:bg-mono-100 p-4">
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
