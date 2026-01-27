/**
 * Training Metrics Types
 * 
 * Types for ML training progress, metrics, and logs.
 */

export interface TrainingMetrics {
  step: number;
  episode?: number;
  epoch?: number;
  loss: number;
  reward?: number;
  sharpe?: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1Score?: number;
  learningRate?: number;
  timestamp: string;
  customMetrics?: Record<string, number>;
}

export interface TrainingProgress {
  experimentId: string;
  currentStep: number;
  totalSteps: number;
  currentEpoch?: number;
  totalEpochs?: number;
  elapsedTime: number;
  estimatedTimeRemaining?: number;
  status: 'running' | 'paused' | 'completed' | 'failed';
  metrics: TrainingMetrics;
}

export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  message: string;
  source?: string;
  metadata?: Record<string, unknown>;
}

export interface TrainingLog {
  experimentId: string;
  entries: LogEntry[];
  totalEntries: number;
  hasMore: boolean;
}

export interface TrainingConfig {
  experimentId: string;
  modelType: string;
  hyperparameters: Record<string, unknown>;
  datasetPath: string;
  outputPath: string;
  checkpointInterval?: number;
  validationInterval?: number;
}

export interface CheckpointInfo {
  id: string;
  experimentId: string;
  step: number;
  epoch?: number;
  timestamp: string;
  metrics: Record<string, number>;
  filePath: string;
  fileSize: number;
}

export interface ValidationResult {
  experimentId: string;
  step: number;
  timestamp: string;
  metrics: Record<string, number>;
  passed: boolean;
  warnings?: string[];
  errors?: string[];
}

export interface EpochProgress {
  current: number;
  total: number;
  percentage: number;
  stepsInEpoch: number;
  totalStepsInEpoch: number;
}

export interface MetricHistory {
  metricName: string;
  values: ChartPoint[];
  smoothedValues?: ChartPoint[];
  best: number;
  worst: number;
  current: number;
}

// Import ChartPoint from charts.ts
import type { ChartPoint } from './charts';
