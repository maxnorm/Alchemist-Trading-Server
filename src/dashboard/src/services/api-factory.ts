/**
 * API Factory
 * 
 * Factory to create either real or mock API client based on environment configuration.
 */

import { ApiClient } from './api';
import { MockApiClient } from './api-mock';

/**
 * Determine if mock API should be used
 */
const useMockApi = import.meta.env.VITE_USE_MOCK_API === 'true';

/**
 * Extended API interface that includes both real and mock methods
 */
export interface ExtendedApiClient {
  // Market Data
  getOrderBook?: (symbol: string) => Promise<any>;
  getPriceTick?: (symbol: string) => Promise<any>;
  getOHLC?: (symbol: string, timeframe?: string, limit?: number) => Promise<any>;
  getTimeAndSales?: (symbol: string, limit?: number) => Promise<any>;
  getCurrencyPairs?: () => Promise<any>;
  getMarketStatus?: (symbol: string) => Promise<any>;
  
  // Order Management
  getOrders?: (status?: string) => Promise<any>;
  getOrder?: (orderId: string) => Promise<any>;
  createOrder?: (request: any) => Promise<any>;
  modifyOrder?: (modification: any) => Promise<any>;
  cancelOrder?: (orderId: string) => Promise<void>;
  
  // Training
  getTrainingLogs?: (experimentId: string, level?: string, limit?: number) => Promise<any>;
  
  // Resources
  getResourceUsage?: () => Promise<any>;
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
