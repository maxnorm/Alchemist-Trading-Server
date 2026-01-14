/**
 * DrawdownChart Component
 * 
 * Visualizes portfolio drawdown over time using equity curve data.
 * Follows the terminal/print aesthetic with monochrome colors and orange accents.
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api-factory';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard';
import type { EquityPoint } from '@/types/performance';

interface DrawdownChartProps {
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
  modelId?: number;
  startDate?: string;
  endDate?: string;
}

export function DrawdownChart({ 
  density = 'dense',
  className,
  modelId,
  startDate,
  endDate
}: DrawdownChartProps) {
  // Fetch equity curve data
  const { data: equityData, isLoading } = useQuery<EquityPoint[]>({
    queryKey: ['equityCurve', modelId, startDate, endDate],
    queryFn: () => {
      if (modelId) {
        return api.getModelEquityCurve(modelId, startDate, endDate);
      }
      return api.getPortfolioEquityCurve(startDate, endDate);
    },
  });

  // Calculate drawdown from equity curve
  const drawdownData = useMemo(() => {
    if (!equityData || equityData.length === 0) return [];

    let peak = equityData[0].equity;
    return equityData.map(point => {
      if (point.equity > peak) {
        peak = point.equity;
      }
      const drawdown = peak > 0 ? ((point.equity - peak) / peak) * 100 : 0;
      
      return {
        timestamp: point.timestamp,
        drawdown: drawdown,
        equity: point.equity,
        peak: peak,
      };
    });
  }, [equityData]);

  // Calculate max drawdown
  const maxDrawdown = useMemo(() => {
    if (drawdownData.length === 0) return 0;
    return Math.min(...drawdownData.map(d => d.drawdown));
  }, [drawdownData]);

  // Format date for tooltip
  const formatDate = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: 'numeric'
    });
  };

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || payload.length === 0) return null;

    const data = payload[0].payload;
    return (
      <div className="bg-mono-300 border border-mono-400 p-3 rounded shadow-lg">
        <p className="font-mono-data text-xs text-mono-600 mb-2">
          {formatDate(data.timestamp)}
        </p>
        <p className="font-mono-data text-sm text-destructive">
          Drawdown: {data.drawdown.toFixed(2)}%
        </p>
        <p className="font-mono-data text-xs text-mono-500 mt-1">
          Equity: ${data.equity.toLocaleString()}
        </p>
        <p className="font-mono-data text-xs text-mono-500">
          Peak: ${data.peak.toLocaleString()}
        </p>
      </div>
    );
  };

  // Get chart height based on density
  const getChartHeight = () => {
    switch (density) {
      case 'comfortable':
        return 400;
      case 'ultra-dense':
        return 200;
      default:
        return 300;
    }
  };

  if (isLoading) {
    return (
      <DenseCard density={density} className={className}>
        <DenseCardHeader title="Drawdown Chart" />
        <DenseCardContent>
          <div className="flex items-center justify-center" style={{ height: getChartHeight() }}>
            <div className="text-mono-500">Loading drawdown data...</div>
          </div>
        </DenseCardContent>
      </DenseCard>
    );
  }

  if (drawdownData.length === 0) {
    return (
      <DenseCard density={density} className={className}>
        <DenseCardHeader title="Drawdown Chart" />
        <DenseCardContent>
          <div className="flex items-center justify-center" style={{ height: getChartHeight() }}>
            <div className="text-mono-500">No drawdown data available</div>
          </div>
        </DenseCardContent>
      </DenseCard>
    );
  }

  return (
    <DenseCard density={density} className={className}>
      <DenseCardHeader 
        title="Drawdown Chart"
        description={`Max Drawdown: ${maxDrawdown.toFixed(2)}%`}
      />
      <DenseCardContent>
        <ResponsiveContainer width="100%" height={getChartHeight()}>
          <AreaChart
            data={drawdownData}
            margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="hsl(var(--destructive))" stopOpacity={0.3} />
                <stop offset="95%" stopColor="hsl(var(--destructive))" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke="hsl(var(--mono-300))" 
              vertical={false}
            />
            <XAxis
              dataKey="timestamp"
              tickFormatter={(value) => {
                const date = new Date(value);
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
              }}
              stroke="hsl(var(--mono-500))"
              style={{ fontSize: '12px', fontFamily: 'var(--font-mono-data)' }}
              tick={{ fill: 'hsl(var(--mono-500))' }}
            />
            <YAxis
              tickFormatter={(value) => `${value.toFixed(1)}%`}
              stroke="hsl(var(--mono-500))"
              style={{ fontSize: '12px', fontFamily: 'var(--font-mono-data)' }}
              tick={{ fill: 'hsl(var(--mono-500))' }}
              domain={[maxDrawdown * 1.1, 0]}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="hsl(var(--destructive))"
              strokeWidth={2}
              fill="url(#drawdownGradient)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </DenseCardContent>
    </DenseCard>
  );
}
