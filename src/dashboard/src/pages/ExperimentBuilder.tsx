import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import toast from 'react-hot-toast'
import { useExperimentForm } from '@/features/experiments/hooks/useExperimentForm'
import { ExperimentFormBasicInfo } from '@/features/experiments/components/ExperimentFormBasicInfo'
import { ExperimentFormFeatures } from '@/features/experiments/components/ExperimentFormFeatures'
import { ExperimentFormCurrencyPairs } from '@/features/experiments/components/ExperimentFormCurrencyPairs'

export default function ExperimentBuilder() {
  const queryClient = useQueryClient()
  const { formData, actions, errors, isValid } = useExperimentForm()

  const { data: features, isLoading: featuresLoading } = useQuery({
    queryKey: ['features'],
    queryFn: () => api.getFeatures(),
  })

  const { data: currencyPairs, isLoading: pairsLoading } = useQuery({
    queryKey: ['currency-pairs'],
    queryFn: () => api.getCurrencyPairs(),
  })

  const createMutation = useMutation({
    mutationFn: (data: typeof formData) => api.createExperiment(data),
    onSuccess: () => {
      toast.success('Experiment created successfully')
      queryClient.invalidateQueries({ queryKey: ['experiments'] })
      actions.reset()
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to create experiment')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!isValid) {
      toast.error('Please fill in all required fields')
      return
    }
    createMutation.mutate(formData)
  }

  const handleSelectAllPairs = () => {
    if (currencyPairs && currencyPairs.length > 0) {
      actions.selectAllCurrencyPairs(currencyPairs)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Experiment Builder</h1>
        <p className="text-muted-foreground">Create and configure new trading experiments</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <ExperimentFormBasicInfo
          name={formData.name}
          description={formData.description || ''}
          onNameChange={(value) => actions.setField('name', value)}
          onDescriptionChange={(value) => actions.setField('description', value)}
          errors={errors}
        />

        <ExperimentFormFeatures
          features={features || []}
          selected={formData.features}
          onToggle={actions.toggleFeature}
          isLoading={featuresLoading}
          errors={errors}
        />

        <ExperimentFormCurrencyPairs
          currencyPairs={currencyPairs || []}
          selected={formData.currency_pairs}
          onToggle={actions.toggleCurrencyPair}
          onSelectAll={handleSelectAllPairs}
          onDeselectAll={actions.deselectAllCurrencyPairs}
          isLoading={pairsLoading}
          errors={errors}
        />

        <Card>
          <CardHeader>
            <CardTitle>Training Mode</CardTitle>
            <CardDescription>Choose how to train the model</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => actions.setField('training_mode', 'live')}
                className={`flex-1 rounded-md border p-4 text-left transition-colors ${
                  formData.training_mode === 'live'
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:bg-accent'
                }`}
              >
                <div className="font-medium">Live Training</div>
                <div className="text-sm text-muted-foreground">
                  Train on real-time data from MT5
                </div>
              </button>
              <button
                type="button"
                onClick={() => actions.setField('training_mode', 'historical')}
                className={`flex-1 rounded-md border p-4 text-left transition-colors ${
                  formData.training_mode === 'historical'
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:bg-accent'
                }`}
              >
                <div className="font-medium">Historical Backtest</div>
                <div className="text-sm text-muted-foreground">
                  Train on historical data (when available)
                </div>
              </button>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end gap-4">
          <Button type="button" variant="outline">
            Save Draft
          </Button>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? <LoadingSpinner size="sm" /> : 'Create Experiment'}
          </Button>
        </div>
      </form>
    </div>
  )
}
