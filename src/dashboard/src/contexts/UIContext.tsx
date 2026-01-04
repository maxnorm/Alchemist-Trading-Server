import { createContext, useContext, useState, useCallback, useMemo, ReactNode } from 'react'

type Theme = 'light' | 'dark'

interface UIContextValue {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
}

const UIContext = createContext<UIContextValue | undefined>(undefined)

export function UIContextProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(
    (localStorage.getItem('theme') as Theme) || 'light'
  )
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const setTheme = useCallback((newTheme: Theme) => {
    localStorage.setItem('theme', newTheme)
    document.documentElement.classList.toggle('dark', newTheme === 'dark')
    setThemeState(newTheme)
  }, [])

  const toggleTheme = useCallback(() => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
  }, [theme, setTheme])

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => !prev)
  }, [])

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      sidebarCollapsed,
      toggleSidebar,
      setSidebarCollapsed,
    }),
    [theme, setTheme, toggleTheme, sidebarCollapsed, toggleSidebar]
  )

  return <UIContext.Provider value={value}>{children}</UIContext.Provider>
}

export function useUI() {
  const context = useContext(UIContext)
  if (!context) {
    throw new Error('useUI must be used within UIContextProvider')
  }
  return context
}
