import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

interface ExperimentFormCurrencyPairsProps {
  currencyPairs: string[]
  selected: string[]
  onToggle: (pair: string) => void
  onSelectAll: () => void
  onDeselectAll: () => void
  isLoading?: boolean
  errors?: Record<string, string>
}

export function ExperimentFormCurrencyPairs({
  currencyPairs,
  selected,
  onToggle,
  onSelectAll,
  onDeselectAll,
  isLoading = false,
  errors,
}: ExperimentFormCurrencyPairsProps) {
  const allPairsSelected = currencyPairs.length > 0 && selected.length === currencyPairs.length

  return (
    <Card>
      <CardHeader>
        <CardTitle>Currency Pairs</CardTitle>
        <CardDescription>Select currency pairs to trade</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <LoadingSpinner />
        ) : (
          <div className="space-y-3">
            {selected.length > 0 && currencyPairs.length > 0 && (
              <div className="text-sm text-muted-foreground">
                {selected.length} of {currencyPairs.length} selected
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {currencyPairs && currencyPairs.length > 0 ? (
                <>
                  {currencyPairs.map((pair) => (
                    <button
                      key={pair}
                      type="button"
                      onClick={() => onToggle(pair)}
                      className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                        selected.includes(pair)
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border hover:bg-accent'
                      }`}
                    >
                      {pair}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={allPairsSelected ? onDeselectAll : onSelectAll}
                    className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                      allPairsSelected
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border hover:bg-accent'
                    }`}
                  >
                    {allPairsSelected ? 'Deselect All' : 'Select All'}
                  </button>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">No currency pairs available</p>
              )}
            </div>
            {errors?.currency_pairs && (
              <p className="text-sm text-red-600 mt-2">{errors.currency_pairs}</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
