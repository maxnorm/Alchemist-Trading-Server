import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Button } from '@/components/ui/button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import toast from 'react-hot-toast'
import { useExperimentForm } from '@/features/experiments/hooks/useExperimentForm'
import { ExperimentFormBasicInfo } from '@/features/experiments/components/ExperimentFormBasicInfo'
import { ExperimentFormFeatures } from '@/features/experiments/components/ExperimentFormFeatures'
import { ExperimentFormCurrencyPairs } from '@/features/experiments/components/ExperimentFormCurrencyPairs'
import { PageHeader } from '@/components/common/PageHeader'
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard'
import { AnimatedPanel } from '@/components/common/AnimatedPanel'

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
    <div className="space-y-4">
      <PageHeader
        title="Experiment Builder"
        description="Create and configure new trading experiments"
        actions={
          <Button type="submit" form="experiment-form" disabled={createMutation.isPending}>
            {createMutation.isPending ? <LoadingSpinner size="sm" /> : 'Create Experiment'}
          </Button>
        }
      />

      <form id="experiment-form" onSubmit={handleSubmit} className="space-y-4">
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

        <AnimatedPanel delay={0.15}>
          <DenseCard density="dense">
            <DenseCardHeader
              title="Training Mode"
              description="Choose how to train the model"
            />
            <DenseCardContent>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => actions.setField('training_mode', 'live')}
                  className={`flex-1 rounded-sm border p-4 text-left transition-colors ${
                    formData.training_mode === 'live'
                      ? 'border-orange-400 bg-orange-400/10 text-orange-400'
                      : 'border-border hover:bg-mono-300'
                  }`}
                >
                  <div className="font-medium">Live Training</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    Train on real-time data
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => actions.setField('training_mode', 'historical')}
                  className={`flex-1 rounded-sm border p-4 text-left transition-colors ${
                    formData.training_mode === 'historical'
                      ? 'border-orange-400 bg-orange-400/10 text-orange-400'
                      : 'border-border hover:bg-mono-300'
                  }`}
                >
                  <div className="font-medium">Historical Backtest</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    Train on historical data
                  </div>
                </button>
              </div>
            </DenseCardContent>
          </DenseCard>
        </AnimatedPanel>

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline">
            Save Draft
          </Button>
        </div>
      </form>
    </div>
  )
}
