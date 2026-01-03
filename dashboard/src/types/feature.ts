export interface Feature {
  id: number
  name: string
  data_type: string
  source: string
  description?: string
  category?: string
  available: boolean
  min_value?: number
  max_value?: number
  mean_value?: number
  created_at: string
  updated_at?: string
}

export interface FeatureFilters {
  source?: string
  category?: string
  data_type?: string
  available?: boolean
}
