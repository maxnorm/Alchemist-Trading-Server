/**
 * ParameterImportanceChart Component
 * 
 * Displays parameter importance scores from Optuna hyperparameter search.
 * Uses horizontal bar chart to show relative importance.
 */

import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api-factory';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Cell
} from 'recharts';
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard';

interface ParameterImportanceChartProps {
  experimentId: number;
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
}

interface ImportanceData {
  parameter: string;
  importance: number;
}

export function ParameterImportanceChart({ 
  experimentId,
  density = 'dense',
  className
}: ParameterImportanceChartProps) {
  // Fetch parameter importance
  const { data: importanceData, isLoading, error } = useQuery({
    queryKey: ['parameterImportance', experimentId],
    queryFn: async () => {
      const response = await api.getParameterImportance?.(experimentId);
      
      // Transform response to chart data format
      if (response && response.importance) {
        return Object.entries(response.importance).map(([param, value]) => ({
          parameter: param,
          importance: value as number,
        })) as ImportanceData[];
      }
      
      return [] as ImportanceData[];
    },
  });

  // Sort by importance (descending)
  const sortedData = importanceData
    ? [...importanceData].sort((a, b) => b.importance - a.importance)
    : [];

  // Get max importance for normalization
  const maxImportance = sortedData.length > 0 
    ? Math.max(...sortedData.map(d => d.importance))
    : 1;

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || payload.length === 0) return null;

    const data = payload[0].payload;
    const percentage = (data.importance / maxImportance) * 100;

    return (
      <div className="bg-mono-300 border border-mono-400 p-3 rounded shadow-lg">
        <p className="font-mono-data text-sm font-semibold text-mono-700 mb-1">
          {data.parameter}
        </p>
        <p className="font-mono-data text-sm text-orange-400">
          Importance: {data.importance.toFixed(4)}
        </p>
        <p className="font-mono-data text-xs text-mono-500 mt-1">
          Relative: {percentage.toFixed(1)}%
        </p>
      </div>
    );
  };

  // Get chart height based on density and number of parameters
  const getChartHeight = () => {
    const baseHeight = sortedData.length * 40; // 40px per bar
    const minHeight = density === 'comfortable' ? 300 : density === 'ultra-dense' ? 200 : 250;
    const maxHeight = density === 'comfortable' ? 600 : density === 'ultra-dense' ? 400 : 500;
    
    return Math.min(Math.max(baseHeight, minHeight), maxHeight);
  };

  if (error) {
    return (
      <DenseCard density={density} className={className}>
        <DenseCardHeader title="Parameter Importance" />
        <DenseCardContent>
          <div className="flex items-center justify-center p-8">
            <div className="text-destructive">Error loading parameter importance</div>
          </div>
        </DenseCardContent>
      </DenseCard>
    );
  }

  if (isLoading) {
    return (
      <DenseCard density={density} className={className}>
        <DenseCardHeader title="Parameter Importance" />
        <DenseCardContent>
          <div className="flex items-center justify-center p-8">
            <div className="text-mono-500">Loading parameter importance...</div>
          </div>
        </DenseCardContent>
      </DenseCard>
    );
  }

  if (sortedData.length === 0) {
    return (
      <DenseCard density={density} className={className}>
        <DenseCardHeader title="Parameter Importance" />
        <DenseCardContent>
          <div className="flex items-center justify-center p-8">
            <div className="text-mono-500">No parameter importance data available</div>
          </div>
        </DenseCardContent>
      </DenseCard>
    );
  }

  return (
    <DenseCard density={density} className={className}>
      <DenseCardHeader 
        title="Parameter Importance"
        description={`${sortedData.length} parameters analyzed`}
      />
      <DenseCardContent>
        <ResponsiveContainer width="100%" height={getChartHeight()}>
          <BarChart
            data={sortedData}
            layout="vertical"
            margin={{ top: 10, right: 30, left: 100, bottom: 10 }}
          >
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke="hsl(var(--mono-300))" 
              horizontal={false}
            />
            <XAxis
              type="number"
              stroke="hsl(var(--mono-500))"
              style={{ fontSize: '12px', fontFamily: 'var(--font-mono-data)' }}
              tick={{ fill: 'hsl(var(--mono-500))' }}
              tickFormatter={(value) => value.toFixed(2)}
            />
            <YAxis
              type="category"
              dataKey="parameter"
              stroke="hsl(var(--mono-500))"
              style={{ fontSize: '12px', fontFamily: 'var(--font-mono-data)' }}
              tick={{ fill: 'hsl(var(--mono-600))' }}
              width={90}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar 
              dataKey="importance" 
              radius={[0, 4, 4, 0]}
              isAnimationActive={false}
            >
              {sortedData.map((_entry, index) => (
                <Cell 
                  key={`cell-${index}`}
                  fill={index === 0 ? 'hsl(var(--orange-400))' : 'hsl(var(--mono-500))'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* Top 3 Parameters Summary */}
        <div className="mt-6 pt-4 border-t border-mono-300">
          <div className="text-technical text-xs mb-3">TOP 3 PARAMETERS</div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {sortedData.slice(0, 3).map((param, index) => {
              const percentage = (param.importance / maxImportance) * 100;
              return (
                <div 
                  key={param.parameter}
                  className="bg-mono-200 p-3 rounded border border-mono-300"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-mono-500">#{index + 1}</span>
                    <span className="font-mono-data text-xs text-mono-600">
                      {percentage.toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-sm font-semibold text-mono-700 mb-1">
                    {param.parameter}
                  </div>
                  <div className="font-mono-data text-lg font-bold text-orange-400">
                    {param.importance.toFixed(4)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </DenseCardContent>
    </DenseCard>
  );
}
