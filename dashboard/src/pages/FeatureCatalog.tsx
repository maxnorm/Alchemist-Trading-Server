import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { useFeatureFilters } from '@/features/features/hooks/useFeatureFilters'

export default function FeatureCatalog() {
  const { features, isLoading, filters, setFilters, searchQuery, setSearchQuery } =
    useFeatureFilters()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Feature Catalog</h1>
        <p className="text-muted-foreground">Browse and explore all available features</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            placeholder="Search features..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <div className="flex gap-4">
            <select
              className="rounded-md border border-input bg-background px-3 py-2"
              value={filters.source || ''}
              onChange={(e) =>
                setFilters((prev) => ({ ...prev, source: e.target.value || undefined }))
              }
            >
              <option value="">All Sources</option>
              <option value="price">Price</option>
              <option value="indicator">Indicator</option>
            </select>
            <select
              className="rounded-md border border-input bg-background px-3 py-2"
              value={filters.category || ''}
              onChange={(e) =>
                setFilters((prev) => ({ ...prev, category: e.target.value || undefined }))
              }
            >
              <option value="">All Categories</option>
              <option value="technical">Technical</option>
              <option value="price">Price</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Card key={feature.id}>
              <CardHeader>
                <CardTitle className="text-lg">{feature.name}</CardTitle>
                <CardDescription>{feature.source}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div>
                    <span className="font-medium">Type:</span> {feature.data_type}
                  </div>
                  {feature.category && (
                    <div>
                      <span className="font-medium">Category:</span> {feature.category}
                    </div>
                  )}
                  {feature.description && (
                    <p className="text-muted-foreground">{feature.description}</p>
                  )}
                  <div className="flex items-center gap-2">
                    <span
                      className={`h-2 w-2 rounded-full ${
                        feature.available ? 'bg-green-500' : 'bg-red-500'
                      }`}
                    />
                    <span className="text-xs">
                      {feature.available ? 'Available' : 'Unavailable'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
