/**
 * Order Management Types
 * 
 * Types for order creation, management, and execution.
 */

export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit';
export type OrderSide = 'buy' | 'sell';
export type OrderStatus = 'pending' | 'open' | 'filled' | 'partially_filled' | 'cancelled' | 'rejected' | 'expired';
export type TimeInForce = 'GTC' | 'IOC' | 'FOK' | 'DAY';

export interface Order {
  id: string;
  symbol: string;
  type: OrderType;
  side: OrderSide;
  status: OrderStatus;
  quantity: number;
  filledQuantity: number;
  price?: number;
  stopPrice?: number;
  limitPrice?: number;
  timeInForce: TimeInForce;
  createdAt: string;
  updatedAt: string;
  filledAt?: string;
  averagePrice?: number;
  commission?: number;
  notes?: string;
}

export interface OrderRequest {
  symbol: string;
  type: OrderType;
  side: OrderSide;
  quantity: number;
  price?: number;
  stopPrice?: number;
  limitPrice?: number;
  timeInForce?: TimeInForce;
  notes?: string;
}

export interface OrderModification {
  orderId: string;
  quantity?: number;
  price?: number;
  stopPrice?: number;
}

export interface OrderCancellation {
  orderId: string;
  reason?: string;
}

export interface OrderConfirmation {
  order: Order;
  estimatedCost: number;
  estimatedCommission: number;
  marginRequired?: number;
  riskWarning?: string;
}

export interface QuickOrderPreset {
  id: string;
  name: string;
  symbol: string;
  type: OrderType;
  side: OrderSide;
  quantity: number;
  price?: number;
}
