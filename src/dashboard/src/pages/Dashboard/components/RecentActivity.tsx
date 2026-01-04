import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { AlertTriangle, Clock } from 'lucide-react'

interface ActivityItem {
  id: string
  type: 'trade' | 'experiment' | 'model' | 'alert'
  message: string
  timestamp: string
  link?: string
}

interface RecentActivityProps {
  activities: ActivityItem[]
}

export function RecentActivity({ activities }: RecentActivityProps) {
  if (activities.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>Latest system events and updates</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No recent activity</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Activity</CardTitle>
        <CardDescription>Latest system events and updates</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {activities.map((activity) => {
            const Icon = activity.type === 'alert' ? AlertTriangle : Clock
            const content = activity.link ? (
              <Link
                to={activity.link}
                className="flex items-start gap-3 rounded-md p-2 text-sm hover:bg-accent transition-colors"
              >
                <Icon className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium">{activity.message}</div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(activity.timestamp).toLocaleString()}
                  </div>
                </div>
              </Link>
            ) : (
              <div className="flex items-start gap-3 rounded-md p-2 text-sm">
                <Icon className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="font-medium">{activity.message}</div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(activity.timestamp).toLocaleString()}
                  </div>
                </div>
              </div>
            )
            return <div key={activity.id}>{content}</div>
          })}
        </div>
      </CardContent>
    </Card>
  )
}
