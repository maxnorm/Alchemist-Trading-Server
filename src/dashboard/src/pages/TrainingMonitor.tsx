import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import toast from 'react-hot-toast'
import { formatRelativeTime } from '@/utils/formatters'
import { useExperimentProgress } from '@/hooks/useExperimentProgress'
import type { Experiment } from '@/types/experiment'
import { PageHeader } from '@/components/common/PageHeader'
import { HealthDot } from '@/components/common/StatusBadge'

function ExperimentCard({ experiment, onStop }: { experiment: Experiment; onStop: (id: number) => void }) {
  const { latest } = useExperimentProgress(experiment.id)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>{experiment.name}</CardTitle>
            <CardDescription>
              Started {experiment.started_at ? formatRelativeTime(experiment.started_at) : 'recently'}
            </CardDescription>
          </div>
          <Button variant="destructive" size="sm" onClick={() => onStop(experiment.id)}>
            Stop
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {latest && (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Step</p>
                <p className="text-lg font-semibold">{latest.step.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Episode</p>
                <p className="text-lg font-semibold">{latest.episode.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Loss</p>
                <p className="text-lg font-semibold">{latest.loss.toFixed(4)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Reward</p>
                <p className="text-lg font-semibold">{latest.reward.toFixed(2)}</p>
              </div>
            </div>
            {latest.sharpe_ratio && (
              <div>
                <p className="text-sm text-muted-foreground">Sharpe Ratio</p>
                <p className="text-lg font-semibold">{latest.sharpe_ratio.toFixed(2)}</p>
              </div>
            )}
          </div>
        )}
        {!latest && <p className="text-sm text-muted-foreground">Waiting for training data...</p>}
      </CardContent>
    </Card>
  )
}

export default function TrainingMonitor() {
  const queryClient = useQueryClient()

  const { data: experiments, isLoading } = useQuery({
    queryKey: ['experiments'],
    queryFn: () => api.getExperiments(),
  })

  const activeExperiments = experiments?.filter((exp) => exp.status === 'training') || []

  const stopMutation = useMutation({
    mutationFn: (id: number) => api.stopExperiment(id),
    onSuccess: () => {
      toast.success('Experiment stopped')
      queryClient.invalidateQueries({ queryKey: ['experiments'] })
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to stop experiment')
    },
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Training Monitor"
        description="Monitor active training experiments in real-time"
        actions={
          <div className="flex items-center gap-3">
            <HealthDot 
              status={activeExperiments.length > 0 ? 'ok' : 'error'} 
              label="Active Experiments" 
            />
          </div>
        }
      />

      {isLoading && !experiments ? (
        <LoadingSpinner />
      ) : activeExperiments.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No active experiments. Create one from the Experiment Builder.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          {activeExperiments.map((experiment) => (
            <ExperimentCard
              key={experiment.id}
              experiment={experiment}
              onStop={(id) => stopMutation.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
