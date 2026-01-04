import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import type { Feature } from '@/types/feature'

interface ExperimentFormFeaturesProps {
  features: Feature[]
  selected: string[]
  onToggle: (name: string) => void
  isLoading?: boolean
  errors?: Record<string, string>
}

export function ExperimentFormFeatures({
  features,
  selected,
  onToggle,
  isLoading = false,
  errors,
}: ExperimentFormFeaturesProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Features</CardTitle>
        <CardDescription>Select features to use in this experiment</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <LoadingSpinner />
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-4">
              {features.map((feature) => (
                <button
                  key={feature.id}
                  type="button"
                  onClick={() => onToggle(feature.name)}
                  className={`rounded-md border p-2 text-left text-sm transition-colors ${
                    selected.includes(feature.name)
                      ? 'border-primary bg-primary/10'
                      : 'border-border hover:bg-accent'
                  }`}
                >
                  <div className="font-medium">{feature.name}</div>
                  <div className="text-xs text-muted-foreground">{feature.source}</div>
                </button>
              ))}
            </div>
            {selected.length > 0 && (
              <div className="mt-4">
                <p className="text-sm font-medium">Selected: {selected.length}</p>
              </div>
            )}
            {errors?.features && (
              <p className="text-sm text-red-600 mt-2">{errors.features}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
