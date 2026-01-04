interface DashboardHeaderProps {
  lastUpdated?: string
}

export function DashboardHeader({ lastUpdated }: DashboardHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-3xl font-bold">Dashboard Overview</h1>
        <p className="text-muted-foreground">Real-time summary of your trading system</p>
      </div>
      {lastUpdated && (
        <div className="text-sm text-muted-foreground">Last updated: {lastUpdated}</div>
      )}
    </div>
  )
}
