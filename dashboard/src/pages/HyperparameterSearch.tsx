import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { useOptunaSearch } from '@/features/optuna/hooks/useOptunaSearch'

export default function HyperparameterSearch() {
  const {
    selectedExperimentId,
    setSelectedExperimentId,
    study,
    trials,
    startSearch,
    isStarting,
  } = useOptunaSearch()

  const { data: experiments } = useQuery({
    queryKey: ['experiments'],
    queryFn: () => api.getExperiments(),
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Hyperparameter Search</h1>
        <p className="text-muted-foreground">Configure and monitor Optuna hyperparameter optimization</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Select Experiment</CardTitle>
          <CardDescription>Choose an experiment to run hyperparameter search on</CardDescription>
        </CardHeader>
        <CardContent>
          <select
            className="w-full rounded-md border border-input bg-background px-3 py-2"
            value={selectedExperimentId || ''}
            onChange={(e) => setSelectedExperimentId(Number(e.target.value) || null)}
          >
            <option value="">Select an experiment...</option>
            {experiments?.map((exp) => (
              <option key={exp.id} value={exp.id}>
                {exp.name} ({exp.status})
              </option>
            ))}
          </select>
        </CardContent>
      </Card>

      {selectedExperimentId && (
        <>
          {study && (
            <Card>
              <CardHeader>
                <CardTitle>Study Status</CardTitle>
                <CardDescription>
                  Status: {study.status} | Trials: {trials.length}/{study.n_trials}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {study.status === 'running' && (
                  <div className="space-y-2">
                    <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full bg-primary transition-all"
                        style={{ width: `${(trials.length / study.n_trials) * 100}%` }}
                      />
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {trials.length} of {study.n_trials} trials completed
                    </p>
                  </div>
                )}
                {study.best_value && (
                  <div className="mt-4">
                    <p className="text-sm font-medium">Best Value: {study.best_value.toFixed(4)}</p>
                    {study.best_params && (
                      <div className="mt-2 text-sm">
                        <p className="font-medium">Best Parameters:</p>
                        <pre className="mt-1 rounded bg-muted p-2 text-xs">
                          {JSON.stringify(study.best_params, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
                {study.status !== 'running' && (
                  <Button
                    onClick={() => startSearch(selectedExperimentId)}
                    disabled={isStarting}
                    className="mt-4"
                  >
                    {isStarting ? <LoadingSpinner size="sm" /> : 'Start Search'}
                  </Button>
                )}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>Trial Results</CardTitle>
              <CardDescription>Top performing trials</CardDescription>
            </CardHeader>
            <CardContent>
              {trials.length === 0 ? (
                <p className="text-muted-foreground">No trials yet. Start a search to begin.</p>
              ) : (
                <div className="space-y-2">
                  {trials.slice(0, 10).map((trial: any) => (
                    <div
                      key={trial.id}
                      className="rounded-md border p-3 text-sm"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">Trial #{trial.trial_number}</span>
                        <span className="text-muted-foreground">State: {trial.state}</span>
                      </div>
                      {trial.value !== undefined && (
                        <p className="mt-1 font-medium">Value: {trial.value.toFixed(4)}</p>
                      )}
                      {trial.params && (
                        <pre className="mt-2 rounded bg-muted p-2 text-xs">
                          {JSON.stringify(trial.params, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
