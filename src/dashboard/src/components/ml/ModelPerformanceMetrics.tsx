/**
 * ModelPerformanceMetrics Component
 * 
 * Displays key performance metrics for a specific model.
 * Shows Sharpe ratio, win rate, P&L, drawdown, and other trading metrics.
 */

import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api-factory';
import { KPICard } from '@/components/common/KPICard';
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard';
import type { ModelMetrics } from '@/types/performance';

interface ModelPerformanceMetricsProps {
  modelId: number;
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
  period?: string;
}

export function ModelPerformanceMetrics({ 
  modelId,
  density = 'dense',
  className,
  period = 'all_time'
}: ModelPerformanceMetricsProps) {
  // Fetch model performance metrics
  const { data: metrics, isLoading, error } = useQuery<ModelMetrics>({
    queryKey: ['modelMetrics', modelId, period],
    queryFn: () => api.getModelMetrics(modelId, period),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Format currency
  const formatCurrency = (value: number | undefined): string => {
    if (value === undefined) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  // Format percentage
  const formatPercent = (value: number | undefined): string => {
    if (value === undefined) return '-';
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  // Format number
  const formatNumber = (value: number | undefined, decimals: number = 2): string => {
    if (value === undefined) return '-';
    return value.toFixed(decimals);
  };

  // Format integer
  const formatInt = (value: number | undefined): string => {
    if (value === undefined) return '-';
    return value.toString();
  };

  if (error) {
    return (
      <DenseCard density={density} className={className}>
        <DenseCardHeader title="Model Performance" />
        <DenseCardContent>
          <div className="flex items-center justify-center p-8">
            <div className="text-destructive">Error loading model metrics</div>
          </div>
        </DenseCardContent>
      </DenseCard>
    );
  }

  if (isLoading) {
    return (
      <DenseCard density={density} className={className}>
        <DenseCardHeader title="Model Performance" />
        <DenseCardContent>
          <div className="flex items-center justify-center p-8">
            <div className="text-mono-500">Loading metrics...</div>
          </div>
        </DenseCardContent>
      </DenseCard>
    );
  }

  if (!metrics) {
    return (
      <DenseCard density={density} className={className}>
        <DenseCardHeader title="Model Performance" />
        <DenseCardContent>
          <div className="flex items-center justify-center p-8">
            <div className="text-mono-500">No metrics available</div>
          </div>
        </DenseCardContent>
      </DenseCard>
    );
  }

  return (
    <DenseCard density={density} className={className}>
      <DenseCardHeader 
        title="Model Performance"
        description={`Model #${modelId} - Period: ${period.replace('_', ' ')}`}
      />
      <DenseCardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Sharpe Ratio */}
          <KPICard
            label="Sharpe Ratio"
            value={formatNumber(metrics.sharpe_ratio)}
            status={metrics.sharpe_ratio && metrics.sharpe_ratio > 1 ? 'positive' : metrics.sharpe_ratio && metrics.sharpe_ratio < 0 ? 'negative' : 'neutral'}
            density={density}
            className="bg-mono-200"
          />

          {/* Win Rate */}
          <KPICard
            label="Win Rate"
            value={metrics.win_rate !== undefined 
              ? formatPercent(metrics.win_rate * 100) 
              : '-'}
            status={metrics.win_rate && metrics.win_rate > 0.5 ? 'positive' : 'negative'}
            density={density}
            className="bg-mono-200"
          />

          {/* Total P&L */}
          <KPICard
            label="Total P&L"
            value={formatCurrency(metrics.total_pnl)}
            status={metrics.total_pnl !== undefined ? (metrics.total_pnl > 0 ? 'positive' : metrics.total_pnl < 0 ? 'negative' : 'neutral') : undefined}
            density={density}
            className="bg-mono-200"
          />

          {/* Max Drawdown */}
          <KPICard
            label="Max Drawdown"
            value={metrics.max_drawdown !== undefined 
              ? formatPercent(metrics.max_drawdown * 100) 
              : '-'}
            status="negative"
            density={density}
            className="bg-mono-200"
          />

          {/* Profit Factor */}
          <KPICard
            label="Profit Factor"
            value={formatNumber(metrics.profit_factor)}
            status={metrics.profit_factor && metrics.profit_factor > 1 ? 'positive' : 'negative'}
            density={density}
            className="bg-mono-200"
          />

          {/* Total Trades */}
          <KPICard
            label="Total Trades"
            value={formatInt(metrics.total_trades)}
            density={density}
            className="bg-mono-200"
          />

          {/* Avg Win */}
          {metrics.avg_win !== undefined && (
            <KPICard
              label="Avg Win"
              value={formatCurrency(metrics.avg_win)}
              density={density}
              className="bg-mono-200"
            />
          )}

          {/* Avg Loss */}
          {metrics.avg_loss !== undefined && (
            <KPICard
              label="Avg Loss"
              value={formatCurrency(metrics.avg_loss)}
              density={density}
              className="bg-mono-200"
            />
          )}

          {/* Sortino Ratio */}
          {metrics.sortino_ratio !== undefined && (
            <KPICard
              label="Sortino Ratio"
              value={formatNumber(metrics.sortino_ratio)}
              density={density}
              className="bg-mono-200"
            />
          )}

          {/* Calmar Ratio */}
          {metrics.calmar_ratio !== undefined && (
            <KPICard
              label="Calmar Ratio"
              value={formatNumber(metrics.calmar_ratio)}
              density={density}
              className="bg-mono-200"
            />
          )}

          {/* Winning Trades */}
          {metrics.winning_trades !== undefined && (
            <KPICard
              label="Winning Trades"
              value={formatInt(metrics.winning_trades)}
              density={density}
              className="bg-mono-200"
            />
          )}

          {/* Losing Trades */}
          {metrics.losing_trades !== undefined && (
            <KPICard
              label="Losing Trades"
              value={formatInt(metrics.losing_trades)}
              density={density}
              className="bg-mono-200"
            />
          )}
        </div>

        {/* Additional Stats */}
        {(metrics.best_trade !== undefined || metrics.worst_trade !== undefined) && (
          <div className="mt-6 pt-4 border-t border-mono-300 grid grid-cols-2 gap-4">
            {metrics.best_trade !== undefined && (
              <div>
                <div className="text-technical text-xs mb-2">BEST TRADE</div>
                <div className="font-mono-data text-xl font-bold text-success">
                  {formatCurrency(metrics.best_trade)}
                </div>
              </div>
            )}
            {metrics.worst_trade !== undefined && (
              <div>
                <div className="text-technical text-xs mb-2">WORST TRADE</div>
                <div className="font-mono-data text-xl font-bold text-destructive">
                  {formatCurrency(metrics.worst_trade)}
                </div>
              </div>
            )}
          </div>
        )}
      </DenseCardContent>
    </DenseCard>
  );
}
