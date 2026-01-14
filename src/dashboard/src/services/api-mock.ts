/**
 * Mock API Client
 * 
 * Provides mock implementations of all API endpoints for development and testing.
 * Returns the same types as the real API for seamless switching.
 */

import type { 
  OrderBook, 
  PriceTick, 
  OHLC, 
  TimeAndSale, 
  MarketStatus, 
  CurrencyPair 
} from '../types/market';
import type { 
  Order, 
  OrderRequest, 
  OrderConfirmation, 
  OrderModification 
} from '../types/orders';
import type { 
  LogEntry, 
  TrainingLog 
} from '../types/training';
import type { ResourceUsage } from '../types/resources';

/**
 * Mock API Client Class
 */
export class MockApiClient {
  private orderBookData: Map<string, OrderBook> = new Map();
  private orders: Order[] = [];
  private priceData: Map<string, PriceTick> = new Map();
  private trainingLogs: Map<string, LogEntry[]> = new Map();
  
  constructor() {
    this.initializeMockData();
  }

  /**
   * Initialize mock data
   */
  private initializeMockData(): void {
    // Initialize mock order books
    const symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'];
    symbols.forEach(symbol => {
      this.orderBookData.set(symbol, this.generateOrderBook(symbol));
      this.priceData.set(symbol, this.generatePriceTick(symbol));
    });

    // Initialize mock orders
    this.orders = this.generateMockOrders();
  }

  /**
   * Generate mock order book
   */
  private generateOrderBook(symbol: string): OrderBook {
    const basePrice = this.getBasePrice(symbol);
    const spread = 0.0002;
    
    const bids: Array<{ price: number; volume: number }> = [];
    const asks: Array<{ price: number; volume: number }> = [];
    
    for (let i = 0; i < 20; i++) {
      bids.push({
        price: basePrice - spread / 2 - i * 0.0001,
        volume: Math.random() * 100000 + 10000
      });
      asks.push({
        price: basePrice + spread / 2 + i * 0.0001,
        volume: Math.random() * 100000 + 10000
      });
    }
    
    return {
      symbol,
      bids,
      asks,
      timestamp: new Date().toISOString(),
      spread
    };
  }

  /**
   * Generate mock price tick
   */
  private generatePriceTick(symbol: string): PriceTick {
    const basePrice = this.getBasePrice(symbol);
    const spread = 0.0002;
    const change = (Math.random() - 0.5) * 0.01;
    
    return {
      symbol,
      bid: basePrice - spread / 2,
      ask: basePrice + spread / 2,
      last: basePrice,
      volume: Math.random() * 1000000,
      change,
      changePercent: (change / basePrice) * 100,
      time: new Date().toISOString(),
      high: basePrice * 1.005,
      low: basePrice * 0.995
    };
  }

  /**
   * Get base price for symbol
   */
  private getBasePrice(symbol: string): number {
    const prices: Record<string, number> = {
      'EURUSD': 1.0850,
      'GBPUSD': 1.2650,
      'USDJPY': 148.50,
      'AUDUSD': 0.6550
    };
    return prices[symbol] || 1.0;
  }

  /**
   * Generate mock orders
   */
  private generateMockOrders(): Order[] {
    const symbols = ['EURUSD', 'GBPUSD', 'USDJPY'];
    const orders: Order[] = [];
    
    for (let i = 0; i < 5; i++) {
      const symbol = symbols[Math.floor(Math.random() * symbols.length)];
      const side: 'buy' | 'sell' = Math.random() > 0.5 ? 'buy' : 'sell';
      const status: Order['status'] = ['pending', 'open', 'partially_filled'][Math.floor(Math.random() * 3)] as Order['status'];
      
      orders.push({
        id: `order-${i + 1}`,
        symbol,
        type: 'limit',
        side,
        status,
        quantity: Math.floor(Math.random() * 100000) + 10000,
        filledQuantity: status === 'partially_filled' ? Math.floor(Math.random() * 50000) : 0,
        price: this.getBasePrice(symbol) * (side === 'buy' ? 0.999 : 1.001),
        timeInForce: 'GTC',
        createdAt: new Date(Date.now() - Math.random() * 86400000).toISOString(),
        updatedAt: new Date().toISOString()
      });
    }
    
    return orders;
  }

  /**
   * Market Data Endpoints
   */
  async getOrderBook(symbol: string): Promise<OrderBook> {
    await this.simulateDelay();
    const orderBook = this.orderBookData.get(symbol);
    if (!orderBook) {
      throw new Error(`Order book not found for symbol: ${symbol}`);
    }
    return { ...orderBook, timestamp: new Date().toISOString() };
  }

  async getPriceTick(symbol: string): Promise<PriceTick> {
    await this.simulateDelay();
    const tick = this.priceData.get(symbol);
    if (!tick) {
      throw new Error(`Price tick not found for symbol: ${symbol}`);
    }
    // Update with slight variation
    const variation = (Math.random() - 0.5) * 0.0001;
    return {
      ...tick,
      bid: tick.bid + variation,
      ask: tick.ask + variation,
      time: new Date().toISOString()
    };
  }

  async getOHLC(symbol: string, _timeframe: string = '1h', limit: number = 100): Promise<OHLC[]> {
    await this.simulateDelay();
    const basePrice = this.getBasePrice(symbol);
    const data: OHLC[] = [];
    
    for (let i = limit; i > 0; i--) {
      const time = new Date(Date.now() - i * 3600000).toISOString();
      const open = basePrice * (1 + (Math.random() - 0.5) * 0.01);
      const close = open * (1 + (Math.random() - 0.5) * 0.01);
      const high = Math.max(open, close) * (1 + Math.random() * 0.005);
      const low = Math.min(open, close) * (1 - Math.random() * 0.005);
      
      data.push({
        time,
        open,
        high,
        low,
        close,
        volume: Math.random() * 1000000
      });
    }
    
    return data;
  }

  async getTimeAndSales(symbol: string, limit: number = 50): Promise<TimeAndSale[]> {
    await this.simulateDelay();
    const basePrice = this.getBasePrice(symbol);
    const data: TimeAndSale[] = [];
    
    for (let i = limit; i > 0; i--) {
      data.push({
        id: `trade-${Date.now()}-${i}`,
        symbol,
        price: basePrice * (1 + (Math.random() - 0.5) * 0.001),
        volume: Math.random() * 100000,
        side: Math.random() > 0.5 ? 'buy' : 'sell',
        timestamp: new Date(Date.now() - i * 1000).toISOString()
      });
    }
    
    return data;
  }

  async getCurrencyPairs(): Promise<CurrencyPair[]> {
    await this.simulateDelay();
    return [
      {
        symbol: 'EURUSD',
        base: 'EUR',
        quote: 'USD',
        displayName: 'EUR/USD',
        minSize: 1000,
        maxSize: 10000000,
        tickSize: 0.00001
      },
      {
        symbol: 'GBPUSD',
        base: 'GBP',
        quote: 'USD',
        displayName: 'GBP/USD',
        minSize: 1000,
        maxSize: 10000000,
        tickSize: 0.00001
      },
      {
        symbol: 'USDJPY',
        base: 'USD',
        quote: 'JPY',
        displayName: 'USD/JPY',
        minSize: 1000,
        maxSize: 10000000,
        tickSize: 0.001
      },
      {
        symbol: 'AUDUSD',
        base: 'AUD',
        quote: 'USD',
        displayName: 'AUD/USD',
        minSize: 1000,
        maxSize: 10000000,
        tickSize: 0.00001
      }
    ];
  }

  async getMarketStatus(symbol: string): Promise<MarketStatus> {
    await this.simulateDelay();
    // Forex is open 24/5
    const now = new Date();
    const day = now.getUTCDay();
    const hour = now.getUTCHours();
    
    const isWeekend = day === 0 || day === 6;
    const isFridayClose = day === 5 && hour >= 21;
    const isMondayOpen = day === 1 && hour < 21;
    
    return {
      symbol,
      status: isWeekend || isFridayClose || isMondayOpen ? 'closed' : 'open',
      nextOpen: isWeekend ? new Date(now.getTime() + 86400000).toISOString() : undefined,
      nextClose: !isWeekend ? new Date(now.getTime() + 86400000).toISOString() : undefined
    };
  }

  /**
   * Order Management Endpoints
   */
  async getOrders(status?: string): Promise<Order[]> {
    await this.simulateDelay();
    if (status) {
      return this.orders.filter(o => o.status === status);
    }
    return [...this.orders];
  }

  async getOrder(orderId: string): Promise<Order> {
    await this.simulateDelay();
    const order = this.orders.find(o => o.id === orderId);
    if (!order) {
      throw new Error(`Order not found: ${orderId}`);
    }
    return { ...order };
  }

  async createOrder(request: OrderRequest): Promise<OrderConfirmation> {
    await this.simulateDelay();
    
    const order: Order = {
      id: `order-${Date.now()}`,
      symbol: request.symbol,
      type: request.type,
      side: request.side,
      status: 'pending',
      quantity: request.quantity,
      filledQuantity: 0,
      price: request.price,
      stopPrice: request.stopPrice,
      limitPrice: request.limitPrice,
      timeInForce: request.timeInForce || 'GTC',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      notes: request.notes
    };
    
    this.orders.push(order);
    
    const basePrice = this.getBasePrice(request.symbol);
    const estimatedPrice = request.price || basePrice;
    
    return {
      order,
      estimatedCost: estimatedPrice * request.quantity,
      estimatedCommission: estimatedPrice * request.quantity * 0.0001,
      marginRequired: estimatedPrice * request.quantity * 0.01,
      riskWarning: request.quantity > 100000 ? 'Large position size' : undefined
    };
  }

  async modifyOrder(modification: OrderModification): Promise<Order> {
    await this.simulateDelay();
    
    const order = this.orders.find(o => o.id === modification.orderId);
    if (!order) {
      throw new Error(`Order not found: ${modification.orderId}`);
    }
    
    if (modification.quantity) order.quantity = modification.quantity;
    if (modification.price) order.price = modification.price;
    if (modification.stopPrice) order.stopPrice = modification.stopPrice;
    order.updatedAt = new Date().toISOString();
    
    return { ...order };
  }

  async cancelOrder(orderId: string): Promise<void> {
    await this.simulateDelay();
    
    const order = this.orders.find(o => o.id === orderId);
    if (!order) {
      throw new Error(`Order not found: ${orderId}`);
    }
    
    order.status = 'cancelled';
    order.updatedAt = new Date().toISOString();
  }

  /**
   * Training Endpoints
   */
  async getTrainingLogs(experimentId: string, level?: string, limit: number = 100): Promise<TrainingLog> {
    await this.simulateDelay();
    
    let logs = this.trainingLogs.get(experimentId);
    if (!logs) {
      logs = this.generateTrainingLogs(experimentId);
      this.trainingLogs.set(experimentId, logs);
    }
    
    let filtered = logs;
    if (level) {
      filtered = logs.filter(log => log.level === level);
    }
    
    const entries = filtered.slice(0, limit);
    
    return {
      experimentId,
      entries,
      totalEntries: filtered.length,
      hasMore: filtered.length > limit
    };
  }

  private generateTrainingLogs(_experimentId: string): LogEntry[] {
    const logs: LogEntry[] = [];
    const levels: Array<'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'> = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
    const messages = [
      'Training step completed',
      'Model checkpoint saved',
      'Validation metrics computed',
      'Learning rate adjusted',
      'Batch processed successfully',
      'GPU memory usage: 85%',
      'Data preprocessing completed',
      'Model weights updated'
    ];
    
    for (let i = 0; i < 200; i++) {
      logs.push({
        id: `log-${i}`,
        timestamp: new Date(Date.now() - (200 - i) * 1000).toISOString(),
        level: levels[Math.floor(Math.random() * levels.length)],
        message: messages[Math.floor(Math.random() * messages.length)],
        source: 'training_loop',
        metadata: { step: i }
      });
    }
    
    return logs;
  }

  /**
   * Resource Monitoring Endpoints
   */
  async getResourceUsage(): Promise<ResourceUsage> {
    await this.simulateDelay();
    
    return {
      cpu: {
        overall: Math.random() * 100,
        perCore: Array.from({ length: 8 }, () => Math.random() * 100),
        timestamp: new Date().toISOString()
      },
      memory: {
        used: Math.random() * 32 * 1024 * 1024 * 1024,
        total: 32 * 1024 * 1024 * 1024,
        percentage: Math.random() * 100,
        available: Math.random() * 16 * 1024 * 1024 * 1024,
        timestamp: new Date().toISOString()
      },
      gpus: [
        {
          id: 0,
          name: 'NVIDIA RTX 4090',
          utilization: Math.random() * 100,
          memoryUsed: Math.random() * 24 * 1024 * 1024 * 1024,
          memoryTotal: 24 * 1024 * 1024 * 1024,
          memoryPercentage: Math.random() * 100,
          temperature: 60 + Math.random() * 20,
          powerDraw: 300 + Math.random() * 150,
          powerLimit: 450,
          timestamp: new Date().toISOString()
        }
      ],
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Utility method to simulate network delay
   */
  private async simulateDelay(ms: number = 50 + Math.random() * 150): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Create mock API client instance
 */
export function createMockApi(): MockApiClient {
  return new MockApiClient();
}
