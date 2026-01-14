/**
 * ModelRegistryTable Component
 * 
 * Displays registered models with their stages and metrics.
 * Supports filtering by stage and navigation to model details.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/services/api-factory';
import { 
  DataTable, 
  DataTableHeader, 
  DataTableBody, 
  DataTableRow, 
  DataTableCell 
} from '@/components/common/DataTable';
import { StatusBadge } from '@/components/common/StatusBadge';
import type { Model, ModelStage } from '@/types/model';

interface ModelRegistryTableProps {
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
  stageFilter?: ModelStage;
}

export function ModelRegistryTable({ 
  density = 'dense',
  className,
  stageFilter
}: ModelRegistryTableProps) {
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<string>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Fetch models
  const { data: modelsResponse, isLoading, error } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.getModels(),
  });

  const models = modelsResponse || [];

  // Filter models by stage
  const filteredModels = models.filter(model => {
    if (!stageFilter) return true;
    return model.stage === stageFilter;
  });

  // Sort models
  const sortedModels = [...filteredModels].sort((a, b) => {
    let aVal: any = a[sortKey as keyof Model];
    let bVal: any = b[sortKey as keyof Model];

    // Handle date strings
    if (sortKey === 'created_at' || sortKey === 'updated_at') {
      aVal = new Date(aVal).getTime();
      bVal = new Date(bVal).getTime();
    }

    if (sortDirection === 'asc') {
      return aVal > bVal ? 1 : -1;
    } else {
      return aVal < bVal ? 1 : -1;
    }
  });

  // Handle sort
  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDirection('desc');
    }
  };

  // Handle row click
  const handleRowClick = (model: Model) => {
    navigate(`/models/${model.id}`);
  };

  // Get stage color
  const getStageColor = (stage: ModelStage): 'success' | 'warning' | 'error' | 'info' => {
    switch (stage) {
      case 'production':
        return 'success';
      case 'paper':
        return 'info';
      case 'staging':
        return 'warning';
      case 'archived':
        return 'error';
      default:
        return 'info';
    }
  };

  // Format date
  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const columns = [
    {
      key: 'version',
      header: 'Version',
      sortable: true,
      render: (model: Model) => (
        <span className="font-mono-data font-semibold text-mono-700">
          v{model.version}
        </span>
      ),
    },
    {
      key: 'stage',
      header: 'Stage',
      sortable: true,
      render: (model: Model) => (
        <StatusBadge 
          severity={getStageColor(model.stage)}
        >
          {model.stage.toUpperCase()}
        </StatusBadge>
      ),
    },
    {
      key: 'experiment_id',
      header: 'Experiment',
      sortable: true,
      render: (model: Model) => (
        <span className="font-mono-data text-mono-600">
          #{model.experiment_id}
        </span>
      ),
    },
    {
      key: 'model_type',
      header: 'Type',
      render: (model: Model) => (
        <span className="text-technical text-sm">
          {model.model_type || '-'}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      render: (model: Model) => (
        <span className="font-mono-data text-mono-500 text-sm">
          {formatDate(model.created_at)}
        </span>
      ),
    },
    {
      key: 'updated_at',
      header: 'Updated',
      sortable: true,
      render: (model: Model) => (
        <span className="font-mono-data text-mono-500 text-sm">
          {model.updated_at ? formatDate(model.updated_at) : '-'}
        </span>
      ),
    },
  ];

  if (error) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-destructive">Error loading models</div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-mono-500">Loading models...</div>
      </div>
    );
  }

  if (sortedModels.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 gap-4">
        <div className="text-mono-500">
          {stageFilter 
            ? `No models in ${stageFilter} stage` 
            : 'No models found'}
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Stage Filter Summary */}
      <div className="mb-4 flex items-center gap-4">
        <span className="text-technical text-xs">STAGE DISTRIBUTION:</span>
        <div className="flex gap-2">
          {(['staging', 'paper', 'production', 'archived'] as ModelStage[]).map(stage => {
            const count = models.filter(m => m.stage === stage).length;
            return (
              <div key={stage} className="flex items-center gap-1">
                <StatusBadge 
                  severity={getStageColor(stage)}
                >
                  {stage.toUpperCase()}
                </StatusBadge>
                <span className="font-mono-data text-xs text-mono-600">
                  ({count})
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Table */}
      <DataTable density={density}>
        <DataTableHeader>
          <tr>
            {columns.map((col) => (
              <DataTableCell 
                key={col.key} 
                header 
                align={col.key === 'created_at' || col.key === 'updated_at' ? 'right' : 'left'}
              >
                <div className="flex items-center gap-2">
                  {col.header}
                  {col.sortable && (
                    <button
                      onClick={() => handleSort(col.key)}
                      className="text-mono-500 hover:text-foreground"
                    >
                      {sortKey === col.key ? (sortDirection === 'asc' ? '↑' : '↓') : '↕'}
                    </button>
                  )}
                </div>
              </DataTableCell>
            ))}
          </tr>
        </DataTableHeader>
        <DataTableBody>
          {sortedModels.map((model) => (
            <DataTableRow 
              key={model.id}
              onClick={() => handleRowClick(model)}
            >
              {columns.map((col) => (
                <DataTableCell key={col.key}>
                  {col.render(model)}
                </DataTableCell>
              ))}
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>
    </div>
  );
}
