/**
 * API Factory
 * 
 * Factory to create either real or mock API client based on environment configuration.
 */

import { ApiClient } from './api';
import { MockApiClient } from './api-mock';
import type { OrderBook, PriceTick, OHLC, TimeAndSale, MarketStatus } from '../types/market';
import type { Order, OrderRequest, OrderConfirmation, OrderModification } from '../types/orders';
import type { TrainingLog } from '../types/training';
import type { ResourceUsage } from '../types/resources';

/**
 * Determine if mock API should be used
 */
const useMockApi = import.meta.env.VITE_USE_MOCK_API === 'true';

/**
 * Extended API interface that includes both real and mock methods
 */
export interface ExtendedApiClient {
  // Market Data
  getOrderBook?: (symbol: string) => Promise<OrderBook>;
  getPriceTick?: (symbol: string) => Promise<PriceTick>;
  getOHLC?: (symbol: string, timeframe?: string, limit?: number) => Promise<OHLC[]>;
  getTimeAndSales?: (symbol: string, limit?: number) => Promise<TimeAndSale[]>;
  getCurrencyPairs?: () => Promise<string[]>;
  getMarketStatus?: (symbol: string) => Promise<MarketStatus>;
  
  // Order Management
  getOrders?: (status?: string) => Promise<Order[]>;
  getOrder?: (orderId: string) => Promise<Order>;
  createOrder?: (request: OrderRequest) => Promise<OrderConfirmation>;
  modifyOrder?: (modification: OrderModification) => Promise<OrderConfirmation>;
  cancelOrder?: (orderId: string) => Promise<void>;
  
  // Training
  getTrainingLogs?: (experimentId: string, level?: string, limit?: number) => Promise<TrainingLog>;
  
  // Resources
  getResourceUsage?: () => Promise<ResourceUsage>;
}

/**
 * Create API client (real or mock based on environment)
 */
function createApiClient(): ApiClient & ExtendedApiClient {
  if (useMockApi) {
    console.log('[API Factory] Using mock API client');
    const mockClient = new MockApiClient();
    const realClient = new ApiClient();
    
    // Merge mock methods into real client
    return Object.assign(realClient, {
      getOrderBook: mockClient.getOrderBook.bind(mockClient),
      getPriceTick: mockClient.getPriceTick.bind(mockClient),
      getOHLC: mockClient.getOHLC.bind(mockClient),
      getTimeAndSales: mockClient.getTimeAndSales.bind(mockClient),
      getCurrencyPairs: mockClient.getCurrencyPairs.bind(mockClient),
      getMarketStatus: mockClient.getMarketStatus.bind(mockClient),
      getOrders: mockClient.getOrders.bind(mockClient),
      getOrder: mockClient.getOrder.bind(mockClient),
      createOrder: mockClient.createOrder.bind(mockClient),
      modifyOrder: mockClient.modifyOrder.bind(mockClient),
      cancelOrder: mockClient.cancelOrder.bind(mockClient),
      getTrainingLogs: mockClient.getTrainingLogs.bind(mockClient),
      getResourceUsage: mockClient.getResourceUsage.bind(mockClient),
    });
  } else {
    console.log('[API Factory] Using real API client');
    return new ApiClient();
  }
}

/**
 * Singleton API client instance
 */
export const api = createApiClient();

/**
 * Export for testing or manual instantiation
 */
export { ApiClient } from './api';
export { MockApiClient } from './api-mock';
