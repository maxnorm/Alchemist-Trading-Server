/**
 * TrainingMetricsChart Component
 * 
 * Displays real-time training metrics with multiple series support.
 * Includes metric selection, smoothing, and follows the terminal/print aesthetic.
 */

import { useEffect, useState, useMemo } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { WS_CHANNELS } from '@/services/websocket';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend,
  ResponsiveContainer 
} from 'recharts';
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard';
import { Button } from '@/components/ui/button';
import type { TrainingMetrics } from '@/types/training';

interface TrainingMetricsChartProps {
  experimentId: string;
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
  maxDataPoints?: number;
}

export function TrainingMetricsChart({ 
  experimentId: _experimentId,
  density = 'dense',
  className,
  maxDataPoints = 100
}: TrainingMetricsChartProps) {
  const [metricsData, setMetricsData] = useState<TrainingMetrics[]>([]);
  const [selectedMetrics, setSelectedMetrics] = useState<Set<string>>(new Set(['loss', 'reward']));
  const [smoothing, setSmoothing] = useState<number>(0);
  const { subscribe } = useWebSocketContext();

  // Available metrics
  const availableMetrics = [
    { key: 'loss', label: 'Loss', color: 'hsl(var(--destructive))' },
    { key: 'reward', label: 'Reward', color: 'hsl(var(--success))' },
    { key: 'sharpe', label: 'Sharpe', color: 'hsl(var(--orange-400))' },
    { key: 'accuracy', label: 'Accuracy', color: 'hsl(var(--info))' },
    { key: 'learningRate', label: 'Learning Rate', color: 'hsl(var(--warning))' },
  ];

  // Subscribe to training metrics
  useEffect(() => {
    const handleMetrics = (metrics: TrainingMetrics) => {
      setMetricsData(prev => {
        const newData = [...prev, metrics];
        // Keep only maxDataPoints
        return newData.slice(-maxDataPoints);
      });
    };

    const unsubscribe = subscribe(WS_CHANNELS.trainingMetrics, handleMetrics);

    return () => {
      unsubscribe();
    };
  }, [subscribe, maxDataPoints]);

  // Apply smoothing using exponential moving average
  const smoothedData = useMemo(() => {
    if (smoothing === 0 || metricsData.length === 0) return metricsData;

    const alpha = 1 - smoothing / 100;
    const smoothed: TrainingMetrics[] = [];

    metricsData.forEach((point, index) => {
      if (index === 0) {
        smoothed.push({ ...point });
      } else {
        const prev = smoothed[index - 1];
        const smoothedPoint: TrainingMetrics = { ...point };

        // Smooth each numeric metric
        if (point.loss !== undefined && prev.loss !== undefined) {
          smoothedPoint.loss = alpha * point.loss + (1 - alpha) * prev.loss;
        }
        if (point.reward !== undefined && prev.reward !== undefined) {
          smoothedPoint.reward = alpha * point.reward + (1 - alpha) * prev.reward;
        }
        if (point.sharpe !== undefined && prev.sharpe !== undefined) {
          smoothedPoint.sharpe = alpha * point.sharpe + (1 - alpha) * prev.sharpe;
        }
        if (point.accuracy !== undefined && prev.accuracy !== undefined) {
          smoothedPoint.accuracy = alpha * point.accuracy + (1 - alpha) * prev.accuracy;
        }
        if (point.learningRate !== undefined && prev.learningRate !== undefined) {
          smoothedPoint.learningRate = alpha * point.learningRate + (1 - alpha) * prev.learningRate;
        }

        smoothed.push(smoothedPoint);
      }
    });

    return smoothed;
  }, [metricsData, smoothing]);

  // Toggle metric selection
  const toggleMetric = (metricKey: string) => {
    setSelectedMetrics(prev => {
      const newSet = new Set(prev);
      if (newSet.has(metricKey)) {
        newSet.delete(metricKey);
      } else {
        newSet.add(metricKey);
      }
      return newSet;
    });
  };

  // Custom tooltip
  interface TooltipEntry {
    name?: string;
    value?: number | string;
    dataKey?: string;
    color?: string;
    payload?: TrainingMetrics;
  }

  interface TooltipProps {
    active?: boolean;
    payload?: TooltipEntry[];
  }

  const CustomTooltip = ({ active, payload }: TooltipProps) => {
    if (!active || !payload || payload.length === 0) return null;

    const data = payload[0].payload;
    return (
      <div className="bg-mono-300 border border-mono-400 p-3 rounded shadow-lg">
        <p className="font-mono-data text-xs text-mono-600 mb-2">
          Step: {data?.step}
        </p>
        {payload.map((entry) => (
          <p key={entry.dataKey} className="font-mono-data text-sm" style={{ color: entry.color }}>
            {entry.name}: {typeof entry.value === 'number' ? entry.value.toFixed(4) : entry.value}
          </p>
        ))}
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

  return (
    <DenseCard density={density} className={className}>
      <DenseCardHeader 
        title="Training Metrics"
        description={`${metricsData.length} data points`}
      />
      <DenseCardContent>
        {/* Metric Selection */}
        <div className="mb-4 flex flex-wrap gap-2">
          {availableMetrics.map(metric => (
            <Button
              key={metric.key}
              onClick={() => toggleMetric(metric.key)}
              variant={selectedMetrics.has(metric.key) ? 'default' : 'outline'}
              size="sm"
              className="focus:ring-2 focus:ring-orange-400"
              style={{
                backgroundColor: selectedMetrics.has(metric.key) ? metric.color : undefined,
                borderColor: metric.color,
              }}
            >
              {metric.label}
            </Button>
          ))}
        </div>

        {/* Smoothing Slider */}
        <div className="mb-4 flex items-center gap-4">
          <label className="text-technical text-xs">Smoothing:</label>
          <input
            type="range"
            min="0"
            max="90"
            value={smoothing}
            onChange={(e) => setSmoothing(Number(e.target.value))}
            className="flex-1 max-w-xs accent-orange-400"
          />
          <span className="font-mono-data text-sm text-mono-600 min-w-[3rem]">
            {smoothing}%
          </span>
        </div>

        {/* Chart */}
        {smoothedData.length === 0 ? (
          <div className="flex items-center justify-center" style={{ height: getChartHeight() }}>
            <div className="text-mono-500">Waiting for training data...</div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={getChartHeight()}>
            <LineChart
              data={smoothedData}
              margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
            >
              <CartesianGrid 
                strokeDasharray="3 3" 
                stroke="hsl(var(--mono-300))" 
                vertical={false}
              />
              <XAxis
                dataKey="step"
                stroke="hsl(var(--mono-500))"
                style={{ fontSize: '12px', fontFamily: 'var(--font-mono-data)' }}
                tick={{ fill: 'hsl(var(--mono-500))' }}
              />
              <YAxis
                stroke="hsl(var(--mono-500))"
                style={{ fontSize: '12px', fontFamily: 'var(--font-mono-data)' }}
                tick={{ fill: 'hsl(var(--mono-500))' }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend 
                wrapperStyle={{ fontSize: '12px', fontFamily: 'var(--font-mono-data)' }}
              />
              {availableMetrics.map(metric => 
                selectedMetrics.has(metric.key) && (
                  <Line
                    key={metric.key}
                    type="monotone"
                    dataKey={metric.key}
                    name={metric.label}
                    stroke={metric.color}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                )
              )}
            </LineChart>
          </ResponsiveContainer>
        )}

        {/* Stats */}
        {metricsData.length > 0 && (
          <div className="mt-4 pt-4 border-t border-mono-300 grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from(selectedMetrics).map(metricKey => {
              const metric = availableMetrics.find(m => m.key === metricKey);
              if (!metric) return null;

              const latestValue = smoothedData[smoothedData.length - 1]?.[metricKey as keyof TrainingMetrics];
              
              return (
                <div key={metricKey}>
                  <div className="text-technical text-xs mb-1">{metric.label}</div>
                  <div className="font-mono-data text-lg font-semibold" style={{ color: metric.color }}>
                    {typeof latestValue === 'number' ? latestValue.toFixed(4) : '-'}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </DenseCardContent>
    </DenseCard>
  );
}
