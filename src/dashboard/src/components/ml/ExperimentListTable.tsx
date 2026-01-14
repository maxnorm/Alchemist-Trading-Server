/**
 * ExperimentListTable Component
 * 
 * Displays a list of experiments with sorting and filtering capabilities.
 * Follows the terminal/print aesthetic design system.
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
import { Button } from '@/components/ui/button';
import type { Experiment } from '@/types/experiment';

interface ExperimentListTableProps {
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
  statusFilter?: string;
}

export function ExperimentListTable({ 
  density = 'dense',
  className,
  statusFilter
}: ExperimentListTableProps) {
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<string>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Fetch experiments
  const { data: experiments, isLoading, error } = useQuery<Experiment[]>({
    queryKey: ['experiments'],
    queryFn: () => api.getExperiments(),
  });

  // Filter experiments by status
  const filteredExperiments = experiments?.filter(exp => {
    if (!statusFilter) return true;
    return exp.status === statusFilter;
  }) || [];

  // Sort experiments
  const sortedExperiments = [...filteredExperiments].sort((a, b) => {
    let aVal: any = a[sortKey as keyof Experiment];
    let bVal: any = b[sortKey as keyof Experiment];

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
  const handleRowClick = (experiment: Experiment) => {
    navigate(`/experiments/${experiment.id}`);
  };

  // Get status severity
  const getStatusSeverity = (status: string): 'success' | 'warning' | 'error' | 'info' => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'success';
      case 'running':
        return 'info';
      case 'failed':
        return 'error';
      case 'pending':
      case 'paused':
        return 'warning';
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
      key: 'name',
      header: 'Name',
      sortable: true,
      render: (experiment: Experiment) => (
        <span className="font-semibold text-mono-700">{experiment.name}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (experiment: Experiment) => (
        <StatusBadge 
          severity={getStatusSeverity(experiment.status)}
        >
          {experiment.status.toUpperCase()}
        </StatusBadge>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      render: (experiment: Experiment) => (
        <span className="font-mono-data text-mono-500 text-sm">
          {formatDate(experiment.created_at)}
        </span>
      ),
    },
    {
      key: 'updated_at',
      header: 'Updated',
      sortable: true,
      render: (experiment: Experiment) => (
        <span className="font-mono-data text-mono-500 text-sm">
          {experiment.updated_at ? formatDate(experiment.updated_at) : '-'}
        </span>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (experiment: Experiment) => (
        <span className="text-mono-600 text-sm truncate max-w-md">
          {experiment.description || '-'}
        </span>
      ),
    },
  ];

  if (error) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-destructive">Error loading experiments</div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-mono-500">Loading experiments...</div>
      </div>
    );
  }

  if (sortedExperiments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 gap-4">
        <div className="text-mono-500">No experiments found</div>
        <Button
          onClick={() => navigate('/experiments/new')}
          className="focus:ring-2 focus:ring-orange-400"
        >
          Create Experiment
        </Button>
      </div>
    );
  }

  return (
    <div className={className}>
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
          {sortedExperiments.map((experiment) => (
            <DataTableRow 
              key={experiment.id}
              onClick={() => handleRowClick(experiment)}
            >
              {columns.map((col) => (
                <DataTableCell key={col.key}>
                  {col.render(experiment)}
                </DataTableCell>
              ))}
            </DataTableRow>
          ))}
        </DataTableBody>
      </DataTable>
    </div>
  );
}
