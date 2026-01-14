/**
 * PortfolioSummaryCard Component
 * 
 * Displays key portfolio metrics in a grid of KPI cards.
 * Uses real-time data from trading status and performance endpoints.
 */

import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api-factory';
import { KPICard } from '@/components/common/KPICard';
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard';
import type { TradingStatus } from '@/types/trading';
import type { PortfolioMetrics } from '@/types/performance';

interface PortfolioSummaryCardProps {
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
  period?: string;
}

export function PortfolioSummaryCard({ 
  density = 'dense',
  className,
  period = 'all_time'
}: PortfolioSummaryCardProps) {
  // Fetch trading status for equity/balance
  const { data: tradingStatus } = useQuery<TradingStatus>({
    queryKey: ['tradingStatus'],
    queryFn: () => api.getTradingStatus(),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Fetch portfolio metrics for performance data
  const { data: portfolioMetrics } = useQuery<PortfolioMetrics>({
    queryKey: ['portfolioMetrics', period],
    queryFn: () => api.getPortfolioMetrics(period),
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

  // Calculate P&L from equity and balance
  const totalPnL = tradingStatus 
    ? tradingStatus.total_equity - tradingStatus.total_balance 
    : undefined;

  const pnlPercent = tradingStatus && tradingStatus.total_balance > 0
    ? ((tradingStatus.total_equity - tradingStatus.total_balance) / tradingStatus.total_balance) * 100
    : undefined;

  return (
    <DenseCard density={density} className={className}>
      <DenseCardHeader 
        title="Portfolio Summary"
        description={`Period: ${period.replace('_', ' ')}`}
      />
      <DenseCardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Total Equity */}
          <KPICard
            label="Total Equity"
            value={formatCurrency(tradingStatus?.total_equity)}
            density={density}
            className="bg-mono-200"
          />

          {/* Total P&L */}
          <KPICard
            label="Total P&L"
            value={formatCurrency(totalPnL)}
            delta={pnlPercent !== undefined ? {
              value: formatPercent(pnlPercent),
              status: totalPnL !== undefined ? (totalPnL > 0 ? 'positive' : totalPnL < 0 ? 'negative' : 'neutral') : undefined
            } : undefined}
            density={density}
            className="bg-mono-200"
          />

          {/* Sharpe Ratio */}
          <KPICard
            label="Sharpe Ratio"
            value={formatNumber(portfolioMetrics?.sharpe_ratio)}
            density={density}
            className="bg-mono-200"
          />

          {/* Max Drawdown */}
          <KPICard
            label="Max Drawdown"
            value={portfolioMetrics?.max_drawdown !== undefined 
              ? formatPercent(portfolioMetrics.max_drawdown * 100) 
              : '-'}
            status="negative"
            density={density}
            className="bg-mono-200"
          />

          {/* Win Rate */}
          <KPICard
            label="Win Rate"
            value={portfolioMetrics?.win_rate !== undefined 
              ? formatPercent(portfolioMetrics.win_rate * 100) 
              : '-'}
            density={density}
            className="bg-mono-200"
          />

          {/* Total Trades */}
          <KPICard
            label="Total Trades"
            value={portfolioMetrics?.total_trades?.toString() || '-'}
            density={density}
            className="bg-mono-200"
          />

          {/* Profit Factor */}
          <KPICard
            label="Profit Factor"
            value={formatNumber(portfolioMetrics?.profit_factor)}
            density={density}
            className="bg-mono-200"
          />

          {/* Active Positions */}
          <KPICard
            label="Active Positions"
            value={tradingStatus?.active_positions.toString() || '-'}
            density={density}
            className="bg-mono-200"
          />
        </div>
      </DenseCardContent>
    </DenseCard>
  );
}
