/**
 * Resource Monitoring Types
 * 
 * Types for system resource usage monitoring.
 */

export interface CPUUsage {
  overall: number;
  perCore: number[];
  timestamp: string;
}

export interface MemoryUsage {
  used: number;
  total: number;
  percentage: number;
  available: number;
  timestamp: string;
}

export interface GPUUsage {
  id: number;
  name: string;
  utilization: number;
  memoryUsed: number;
  memoryTotal: number;
  memoryPercentage: number;
  temperature?: number;
  powerDraw?: number;
  powerLimit?: number;
  timestamp: string;
}

export interface DiskUsage {
  path: string;
  used: number;
  total: number;
  percentage: number;
  available: number;
  timestamp: string;
}

export interface NetworkUsage {
  bytesReceived: number;
  bytesSent: number;
  packetsReceived: number;
  packetsSent: number;
  timestamp: string;
}

export interface ResourceUsage {
  cpu: CPUUsage;
  memory: MemoryUsage;
  gpus: GPUUsage[];
  disk?: DiskUsage[];
  network?: NetworkUsage;
  timestamp: string;
}

export interface ResourceAlert {
  id: string;
  type: 'cpu' | 'memory' | 'gpu' | 'disk' | 'network';
  severity: 'info' | 'warning' | 'critical';
  message: string;
  value: number;
  threshold: number;
  timestamp: string;
}

export interface ResourceThresholds {
  cpuWarning: number;
  cpuCritical: number;
  memoryWarning: number;
  memoryCritical: number;
  gpuWarning: number;
  gpuCritical: number;
  diskWarning: number;
  diskCritical: number;
}

export interface ResourceHistory {
  cpu: Array<{ timestamp: string; value: number }>;
  memory: Array<{ timestamp: string; value: number }>;
  gpu: Array<{ timestamp: string; value: number; gpuId: number }>;
  startTime: string;
  endTime: string;
}
