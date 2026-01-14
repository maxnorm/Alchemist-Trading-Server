/**
 * Market Data Types
 * 
 * Types for market data, order books, price ticks, and OHLC data.
 */

export interface OrderBookEntry {
  price: number;
  volume: number;
  timestamp?: string;
}

export interface OrderBook {
  symbol: string;
  bids: OrderBookEntry[];
  asks: OrderBookEntry[];
  timestamp: string;
  spread?: number;
}

export interface PriceTick {
  symbol: string;
  bid: number;
  ask: number;
  last?: number;
  volume?: number;
  change?: number;
  changePercent?: number;
  time: string;
  high?: number;
  low?: number;
}

export interface OHLC {
  open: number;
  high: number;
  low: number;
  close: number;
  time: string;
  volume?: number;
}

export interface CandleData extends OHLC {
  volume: number;
}

export interface MarketDepth {
  symbol: string;
  bids: OrderBookEntry[];
  asks: OrderBookEntry[];
  timestamp: string;
}

export interface TimeAndSale {
  id: string;
  symbol: string;
  price: number;
  volume: number;
  side: 'buy' | 'sell';
  timestamp: string;
}

export interface MarketStatus {
  symbol: string;
  status: 'open' | 'closed' | 'pre_market' | 'post_market';
  nextOpen?: string;
  nextClose?: string;
}

export interface CurrencyPair {
  symbol: string;
  base: string;
  quote: string;
  displayName: string;
  minSize: number;
  maxSize: number;
  tickSize: number;
}
