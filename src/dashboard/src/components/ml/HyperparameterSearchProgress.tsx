/**
 * HyperparameterSearchProgress Component
 * 
 * Displays Optuna hyperparameter search progress with real-time updates.
 * Shows trial completion, best value, and best parameters.
 */

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api-factory';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { WS_CHANNELS } from '@/services/websocket';
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard';
import { StatusBadge } from '@/components/common/StatusBadge';
import type { OptunaStudy } from '@/types/optuna';

interface HyperparameterSearchProgressProps {
  experimentId: number;
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
}

export function HyperparameterSearchProgress({ 
  experimentId,
  density = 'dense',
  className
}: HyperparameterSearchProgressProps) {
  const [studyData, setStudyData] = useState<OptunaStudy | null>(null);

  // Fetch initial study status
  const { data: initialStudy, isLoading } = useQuery<OptunaStudy>({
    queryKey: ['optunaStatus', experimentId],
    queryFn: () => api.getOptunaStatus(experimentId),
    refetchInterval: 10000, // Fallback polling every 10s
  });

  // Subscribe to real-time updates
  const { subscribe } = useWebSocketContext();

  useEffect(() => {
    if (initialStudy) {
      setStudyData(initialStudy);
    }
  }, [initialStudy]);

  useEffect(() => {
    const handleUpdate = (data: {
      trialNumber?: number;
      bestValue?: number;
      params?: Record<string, unknown>;
    }) => {
      // Update study data with new trial information
      setStudyData(prev => {
        if (!prev) return prev;
        
        return {
          ...prev,
          n_trials: data.trialNumber || prev.n_trials,
          best_value: data.bestValue !== undefined ? data.bestValue : prev.best_value,
          best_params: data.params || prev.best_params,
        };
      });
    };

    const unsubscribe = subscribe(WS_CHANNELS.optunaTrials(experimentId), handleUpdate);

    return () => {
      unsubscribe();
    };
  }, [subscribe, experimentId]);

  // Calculate progress percentage
  const progressPercent = studyData && studyData.n_trials_target
    ? (studyData.n_trials / studyData.n_trials_target) * 100
    : 0;

  // Get status color
  const getStatusColor = (state: string): 'success' | 'warning' | 'error' | 'info' => {
    switch (state?.toLowerCase()) {
      case 'complete':
      case 'completed':
        return 'success';
      case 'running':
        return 'info';
      case 'failed':
        return 'error';
      case 'pruned':
        return 'warning';
      default:
        return 'info';
    }
  };

  if (isLoading) {
    return (
      <DenseCard density={density} className={className}>
        <DenseCardHeader title="Hyperparameter Search" />
        <DenseCardContent>
          <div className="flex items-center justify-center p-8">
            <div className="text-mono-500">Loading search status...</div>
          </div>
        </DenseCardContent>
      </DenseCard>
    );
  }

  if (!studyData) {
    return (
      <DenseCard density={density} className={className}>
        <DenseCardHeader title="Hyperparameter Search" />
        <DenseCardContent>
          <div className="flex items-center justify-center p-8">
            <div className="text-mono-500">No hyperparameter search running</div>
          </div>
        </DenseCardContent>
      </DenseCard>
    );
  }

  return (
    <DenseCard density={density} className={className}>
      <DenseCardHeader 
        title="Hyperparameter Search"
        description={`Study: ${studyData.study_name || 'Unnamed'}`}
      />
      <DenseCardContent>
        {/* Status Badge */}
        <div className="mb-4">
          <StatusBadge 
            severity={getStatusColor(studyData.state || 'running')}
          >
            {(studyData.state || 'RUNNING').toUpperCase()}
          </StatusBadge>
        </div>

        {/* Progress Bar */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-technical text-xs">PROGRESS</span>
            <span className="font-mono-data text-sm text-mono-600">
              {studyData.n_trials} / {studyData.n_trials_target || '∞'} trials
            </span>
          </div>
          <div className="w-full bg-mono-300 rounded-full h-3 overflow-hidden">
            <div 
              className="bg-orange-400 h-full transition-all duration-500 ease-out"
              style={{ width: `${Math.min(progressPercent, 100)}%` }}
            />
          </div>
          {studyData.n_trials_target && (
            <div className="mt-1 text-right">
              <span className="font-mono-data text-xs text-mono-500">
                {progressPercent.toFixed(1)}%
              </span>
            </div>
          )}
        </div>

        {/* Best Value */}
        <div className="mb-6">
          <div className="text-technical text-xs mb-2">BEST VALUE</div>
          <div className="font-mono-data text-3xl font-bold text-orange-400">
            {studyData.best_value !== null && studyData.best_value !== undefined
              ? studyData.best_value.toFixed(6)
              : '-'}
          </div>
          {studyData.direction && (
            <div className="text-xs text-mono-500 mt-1">
              Direction: {studyData.direction}
            </div>
          )}
        </div>

        {/* Best Parameters */}
        {studyData.best_params && Object.keys(studyData.best_params).length > 0 && (
          <div>
            <div className="text-technical text-xs mb-3">BEST PARAMETERS</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(studyData.best_params).map(([key, value]) => (
                <div 
                  key={key}
                  className="bg-mono-200 p-3 rounded border border-mono-300"
                >
                  <div className="text-xs text-mono-500 mb-1">{key}</div>
                  <div className="font-mono-data text-sm font-semibold text-mono-700">
                    {typeof value === 'number' 
                      ? value.toFixed(6) 
                      : String(value)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Additional Info */}
        <div className="mt-6 pt-4 border-t border-mono-300 grid grid-cols-2 gap-4 text-xs">
          {studyData.datetime_start && (
            <div>
              <div className="text-mono-500 mb-1">Started</div>
              <div className="font-mono-data text-mono-600">
                {new Date(studyData.datetime_start).toLocaleString()}
              </div>
            </div>
          )}
          {studyData.datetime_complete && (
            <div>
              <div className="text-mono-500 mb-1">Completed</div>
              <div className="font-mono-data text-mono-600">
                {new Date(studyData.datetime_complete).toLocaleString()}
              </div>
            </div>
          )}
        </div>
      </DenseCardContent>
    </DenseCard>
  );
}
