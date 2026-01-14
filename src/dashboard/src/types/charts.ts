/**
 * Chart Data Types
 * 
 * Generic types for chart data visualization.
 */

export interface ChartPoint {
  x: number | string | Date;
  y: number;
  label?: string;
  metadata?: Record<string, any>;
}

export interface MultiSeriesChartPoint {
  x: number | string | Date;
  [key: string]: number | string | Date;
}

export interface ScatterPoint {
  x: number;
  y: number;
  label?: string;
  color?: string;
  size?: number;
  metadata?: Record<string, any>;
}

export interface HistogramBin {
  binStart: number;
  binEnd: number;
  count: number;
  percentage?: number;
}

export interface DistributionData {
  bins: HistogramBin[];
  mean: number;
  median: number;
  stdDev: number;
  min: number;
  max: number;
}

export interface HeatmapCell {
  x: string | number;
  y: string | number;
  value: number;
  label?: string;
}

export interface HeatmapData {
  cells: HeatmapCell[];
  xLabels: string[];
  yLabels: string[];
  minValue: number;
  maxValue: number;
}

export interface TimeSeriesPoint {
  timestamp: string;
  value: number;
  label?: string;
}

export interface CandlestickData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export type ChartDensity = 'comfortable' | 'dense' | 'ultra-dense';

export interface ChartTheme {
  backgroundColor: string;
  textColor: string;
  gridColor: string;
  lineColor: string;
  accentColor: string;
}

export interface ChartConfig {
  density?: ChartDensity;
  showGrid?: boolean;
  showLegend?: boolean;
  showTooltip?: boolean;
  animate?: boolean;
  theme?: ChartTheme;
}
