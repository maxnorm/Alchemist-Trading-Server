/**
 * Mock WebSocket Service
 * 
 * Simulates WebSocket connections and real-time data streams for development.
 */

import type { PriceTick } from '../types/market';
import type { TrainingMetrics } from '../types/training';
import type { ResourceUsage } from '../types/resources';

type MessageHandler = (data: unknown) => void;
type ConnectionHandler = () => void;

interface Subscription {
  channel: string;
  handler: MessageHandler;
}

/**
 * Mock WebSocket Client
 */
export class MockWebSocketClient {
  private subscriptions: Map<string, Subscription[]> = new Map();
  private intervals: Map<string, NodeJS.Timeout> = new Map();
  private connected: boolean = false;
  private connectionHandlers: ConnectionHandler[] = [];
  private disconnectionHandlers: ConnectionHandler[] = [];

  /**
   * Connect to mock WebSocket
   */
  connect(): Promise<void> {
    return new Promise((resolve) => {
      setTimeout(() => {
        this.connected = true;
        this.connectionHandlers.forEach(handler => handler());
        console.log('[Mock WebSocket] Connected');
        resolve();
      }, 100);
    });
  }

  /**
   * Disconnect from mock WebSocket
   */
  disconnect(): void {
    this.connected = false;
    this.intervals.forEach(interval => clearInterval(interval));
    this.intervals.clear();
    this.disconnectionHandlers.forEach(handler => handler());
    console.log('[Mock WebSocket] Disconnected');
  }

  /**
   * Subscribe to a channel
   */
  subscribe(channel: string, handler: MessageHandler): void {
    if (!this.subscriptions.has(channel)) {
      this.subscriptions.set(channel, []);
    }

    this.subscriptions.get(channel)!.push({ channel, handler });

    // Start simulating data for this channel
    this.startSimulation(channel);

    console.log(`[Mock WebSocket] Subscribed to ${channel}`);
  }

  /**
   * Unsubscribe from a channel
   */
  unsubscribe(channel: string, handler?: MessageHandler): void {
    if (!handler) {
      // Remove all subscriptions for this channel
      this.subscriptions.delete(channel);
      this.stopSimulation(channel);
    } else {
      // Remove specific handler
      const subs = this.subscriptions.get(channel);
      if (subs) {
        const filtered = subs.filter(sub => sub.handler !== handler);
        if (filtered.length === 0) {
          this.subscriptions.delete(channel);
          this.stopSimulation(channel);
        } else {
          this.subscriptions.set(channel, filtered);
        }
      }
    }

    console.log(`[Mock WebSocket] Unsubscribed from ${channel}`);
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.connected;
  }

  /**
   * Add connection handler
   */
  onConnect(handler: ConnectionHandler): void {
    this.connectionHandlers.push(handler);
  }

  /**
   * Add disconnection handler
   */
  onDisconnect(handler: ConnectionHandler): void {
    this.disconnectionHandlers.push(handler);
  }

  /**
   * Start simulating data for a channel
   */
  private startSimulation(channel: string): void {
    if (this.intervals.has(channel)) {
      return; // Already simulating
    }

    let interval: NodeJS.Timeout;

    if (channel.startsWith('/ws/ticks')) {
      interval = this.simulatePriceTicks(channel);
    } else if (channel.startsWith('/ws/training')) {
      interval = this.simulateTrainingMetrics(channel);
    } else if (channel.startsWith('/ws/positions')) {
      interval = this.simulatePositions(channel);
    } else if (channel.startsWith('/ws/metrics')) {
      interval = this.simulateMetrics(channel);
    } else if (channel.startsWith('/ws/optuna')) {
      interval = this.simulateOptuna(channel);
    } else if (channel.startsWith('/ws/resources')) {
      interval = this.simulateResources(channel);
    } else {
      // Default simulation
      interval = setInterval(() => {
        this.broadcast(channel, { timestamp: new Date().toISOString() });
      }, 5000);
    }

    this.intervals.set(channel, interval);
  }

  /**
   * Stop simulating data for a channel
   */
  private stopSimulation(channel: string): void {
    const interval = this.intervals.get(channel);
    if (interval) {
      clearInterval(interval);
      this.intervals.delete(channel);
    }
  }

  /**
   * Broadcast data to all subscribers of a channel
   */
  private broadcast(channel: string, data: unknown): void {
    const subs = this.subscriptions.get(channel);
    if (subs) {
      subs.forEach(sub => sub.handler(data));
    }
  }

  /**
   * Simulate price ticks
   */
  private simulatePriceTicks(channel: string): NodeJS.Timeout {
    const symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'];
    const basePrices: Record<string, number> = {
      'EURUSD': 1.0850,
      'GBPUSD': 1.2650,
      'USDJPY': 148.50,
      'AUDUSD': 0.6550
    };

    return setInterval(() => {
      symbols.forEach(symbol => {
        const basePrice = basePrices[symbol];
        const variation = (Math.random() - 0.5) * 0.0002;
        const spread = 0.0002;

        const tick: PriceTick = {
          symbol,
          bid: basePrice + variation - spread / 2,
          ask: basePrice + variation + spread / 2,
          last: basePrice + variation,
          volume: Math.random() * 1000000,
          change: variation,
          changePercent: (variation / basePrice) * 100,
          time: new Date().toISOString(),
          high: basePrice * 1.005,
          low: basePrice * 0.995
        };

        this.broadcast(channel, tick);
      });
    }, 1000);
  }

  /**
   * Simulate training metrics
   */
  private simulateTrainingMetrics(channel: string): NodeJS.Timeout {
    let step = 0;
    let baseLoss = 1.0;

    return setInterval(() => {
      step++;
      baseLoss = Math.max(0.1, baseLoss * 0.995 + (Math.random() - 0.5) * 0.01);

      const metrics: TrainingMetrics = {
        step,
        episode: Math.floor(step / 100),
        epoch: Math.floor(step / 1000),
        loss: baseLoss,
        reward: Math.random() * 100 - 50,
        sharpe: Math.random() * 3 - 1,
        accuracy: 0.5 + Math.random() * 0.3,
        learningRate: 0.001 * Math.pow(0.99, step / 100),
        timestamp: new Date().toISOString()
      };

      this.broadcast(channel, metrics);
    }, 2000);
  }

  /**
   * Simulate positions
   */
  private simulatePositions(channel: string): NodeJS.Timeout {
    return setInterval(() => {
      const positions = [
        {
          id: '1',
          symbol: 'EURUSD',
          side: 'buy',
          quantity: 100000,
          entryPrice: 1.0850,
          currentPrice: 1.0850 + (Math.random() - 0.5) * 0.01,
          pnl: (Math.random() - 0.5) * 1000,
          pnlPercent: (Math.random() - 0.5) * 2,
          timestamp: new Date().toISOString()
        },
        {
          id: '2',
          symbol: 'GBPUSD',
          side: 'sell',
          quantity: 50000,
          entryPrice: 1.2650,
          currentPrice: 1.2650 + (Math.random() - 0.5) * 0.01,
          pnl: (Math.random() - 0.5) * 800,
          pnlPercent: (Math.random() - 0.5) * 1.5,
          timestamp: new Date().toISOString()
        }
      ];

      this.broadcast(channel, positions);
    }, 3000);
  }

  /**
   * Simulate general metrics
   */
  private simulateMetrics(channel: string): NodeJS.Timeout {
    return setInterval(() => {
      const metrics = {
        sharpe: Math.random() * 3 - 1,
        sortino: Math.random() * 3 - 0.5,
        maxDrawdown: Math.random() * 0.3,
        winRate: 0.4 + Math.random() * 0.3,
        profitFactor: 1 + Math.random() * 2,
        timestamp: new Date().toISOString()
      };

      this.broadcast(channel, metrics);
    }, 5000);
  }

  /**
   * Simulate Optuna trials
   */
  private simulateOptuna(channel: string): NodeJS.Timeout {
    let trialNumber = 0;
    let bestValue = -Infinity;

    return setInterval(() => {
      trialNumber++;
      const value = Math.random() * 2 - 1;
      if (value > bestValue) {
        bestValue = value;
      }

      const trial = {
        trialNumber,
        value,
        bestValue,
        state: 'COMPLETE',
        params: {
          learning_rate: Math.random() * 0.01,
          batch_size: Math.floor(Math.random() * 128) + 32,
          hidden_size: Math.floor(Math.random() * 256) + 64
        },
        timestamp: new Date().toISOString()
      };

      this.broadcast(channel, trial);
    }, 3000);
  }

  /**
   * Simulate resource usage
   */
  private simulateResources(channel: string): NodeJS.Timeout {
    return setInterval(() => {
      const usage: ResourceUsage = {
        cpu: {
          overall: 30 + Math.random() * 40,
          perCore: Array.from({ length: 8 }, () => Math.random() * 100),
          timestamp: new Date().toISOString()
        },
        memory: {
          used: (20 + Math.random() * 10) * 1024 * 1024 * 1024,
          total: 32 * 1024 * 1024 * 1024,
          percentage: 60 + Math.random() * 20,
          available: (10 + Math.random() * 5) * 1024 * 1024 * 1024,
          timestamp: new Date().toISOString()
        },
        gpus: [
          {
            id: 0,
            name: 'NVIDIA RTX 4090',
            utilization: 70 + Math.random() * 20,
            memoryUsed: (18 + Math.random() * 4) * 1024 * 1024 * 1024,
            memoryTotal: 24 * 1024 * 1024 * 1024,
            memoryPercentage: 75 + Math.random() * 15,
            temperature: 65 + Math.random() * 10,
            powerDraw: 350 + Math.random() * 50,
            powerLimit: 450,
            timestamp: new Date().toISOString()
          }
        ],
        timestamp: new Date().toISOString()
      };

      this.broadcast(channel, usage);
    }, 2000);
  }
}

/**
 * Create mock WebSocket client instance
 */
export function createMockWebSocket(): MockWebSocketClient {
  return new MockWebSocketClient();
}
