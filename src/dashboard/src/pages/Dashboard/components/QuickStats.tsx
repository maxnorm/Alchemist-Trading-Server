import { Link } from 'react-router-dom'
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard'

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
    <DenseCard density="dense" hover>
      <DenseCardHeader
        title="Quick Stats"
        description="System overview at a glance"
      />
      <DenseCardContent>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Experiments</div>
            <div className="text-2xl font-bold font-mono-data mt-1">{stats.experiments.total}</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {stats.experiments.active} active, {stats.experiments.completed} completed
            </div>
          </div>

          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Models</div>
            <div className="text-2xl font-bold font-mono-data mt-1">
              {stats.models.staging + stats.models.paper + stats.models.production}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {stats.models.production} production, {stats.models.paper} paper
            </div>
          </div>

          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Features</div>
            <div className="text-2xl font-bold font-mono-data mt-1">{stats.features}</div>
            <div className="text-xs text-muted-foreground mt-0.5">Available features</div>
          </div>

          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">MT5 Accounts</div>
            <div className="text-2xl font-bold font-mono-data mt-1">{stats.accounts.total}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{stats.accounts.active} active</div>
          </div>
        </div>

        <div className="mt-3 flex gap-2">
          <Link
            to="/experiments"
            className="flex-1 text-center rounded-sm border border-border px-3 py-2 text-xs hover:bg-orange-400/10 hover:border-orange-400/50 transition-colors"
          >
            View Experiments
          </Link>
          <Link
            to="/models"
            className="flex-1 text-center rounded-sm border border-border px-3 py-2 text-xs hover:bg-orange-400/10 hover:border-orange-400/50 transition-colors"
          >
            View Models
          </Link>
        </div>
      </DenseCardContent>
    </DenseCard>
  )
}
