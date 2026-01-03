import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface QuickStatsData {
  experiments: {
    total: number
    active: number
    completed: number
  }
  models: {
    staging: number
    paper: number
    production: number
  }
  features: number
  accounts: {
    total: number
    active: number
  }
}

interface QuickStatsProps {
  stats: QuickStatsData
}

export function QuickStats({ stats }: QuickStatsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Quick Stats</CardTitle>
        <CardDescription>System overview at a glance</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-sm text-muted-foreground">Experiments</div>
            <div className="text-2xl font-bold">{stats.experiments.total}</div>
            <div className="text-xs text-muted-foreground">
              {stats.experiments.active} active, {stats.experiments.completed} completed
            </div>
          </div>

          <div>
            <div className="text-sm text-muted-foreground">Models</div>
            <div className="text-2xl font-bold">
              {stats.models.staging + stats.models.paper + stats.models.production}
            </div>
            <div className="text-xs text-muted-foreground">
              {stats.models.production} production, {stats.models.paper} paper
            </div>
          </div>

          <div>
            <div className="text-sm text-muted-foreground">Features</div>
            <div className="text-2xl font-bold">{stats.features}</div>
            <div className="text-xs text-muted-foreground">Available features</div>
          </div>

          <div>
            <div className="text-sm text-muted-foreground">MT5 Accounts</div>
            <div className="text-2xl font-bold">{stats.accounts.total}</div>
            <div className="text-xs text-muted-foreground">{stats.accounts.active} active</div>
          </div>
        </div>

        <div className="mt-4 flex gap-2">
          <Link
            to="/experiments"
            className="flex-1 text-center rounded-md border px-3 py-2 text-sm hover:bg-accent transition-colors"
          >
            View Experiments
          </Link>
          <Link
            to="/models"
            className="flex-1 text-center rounded-md border px-3 py-2 text-sm hover:bg-accent transition-colors"
          >
            View Models
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
