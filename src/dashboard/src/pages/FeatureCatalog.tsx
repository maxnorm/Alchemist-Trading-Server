import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { useFeatureFilters } from '@/features/features/hooks/useFeatureFilters'
import { PageHeader } from '@/components/common/PageHeader'
import { HealthDot } from '@/components/common/StatusBadge'
import { RefreshCw, Download } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'

export default function FeatureCatalog() {
  const { features, isLoading, filters, setFilters, searchQuery, setSearchQuery } =
    useFeatureFilters()
  const queryClient = useQueryClient()

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['features'] })
    toast.success('Features refreshed')
  }

  const handleExport = () => {
    if (features.length === 0) {
      toast.error('No features to export')
      return
    }

    const headers = ['Name', 'Source', 'Category', 'Type', 'Available', 'Description']
    const rows = features.map((feature) => [
      feature.name,
      feature.source || '',
      feature.category || '',
      feature.data_type || '',
      feature.available ? 'Yes' : 'No',
      feature.description || '',
    ])

    const csv = [headers, ...rows]
      .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
      .join('\n')

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `feature-catalog-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
    toast.success(`Exported ${features.length} features`)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Feature Catalog"
        description="Browse and explore all available features"
        actions={
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isLoading}
              className="gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              disabled={features.length === 0}
              className="gap-2"
            >
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
            <HealthDot 
              status={features.length > 0 ? 'ok' : 'error'} 
              label="Feature Catalog" 
            />
          </div>
        }
      />

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
              className="rounded-md border border-input bg-background pl-3 pr-8 py-2"
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
              className="rounded-md border border-input bg-background pl-3 pr-8 py-2"
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

      {isLoading && features.length === 0 ? (
        <LoadingSpinner />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {features.length === 0 ? (
            <Card className="col-span-full">
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">No features found</p>
              </CardContent>
            </Card>
          ) : (
            features.map((feature) => (
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
            ))
          )}
        </div>
      )}
    </div>
  )
}
