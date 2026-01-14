/**
 * TimeAndSales Component
 * 
 * Displays a real-time feed of executed trades (time and sales).
 * Auto-scrolls to show latest trades.
 */

import { useEffect, useState, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api-factory';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard';
import { StatusBadge } from '@/components/common/StatusBadge';
import type { TimeAndSale } from '@/types/market';
import { cn } from '@/utils/cn';

interface TimeAndSalesProps {
  symbol: string;
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
  maxItems?: number;
  autoScroll?: boolean;
}

export function TimeAndSales({ 
  symbol,
  density = 'dense',
  className,
  maxItems = 50,
  autoScroll = true
}: TimeAndSalesProps) {
  const [trades, setTrades] = useState<TimeAndSale[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { subscribe } = useWebSocketContext();

  // Fetch initial historical trades
  const { data: historicalTrades } = useQuery({
    queryKey: ['timeAndSales', symbol],
    queryFn: () => api.getTimeAndSales?.(symbol, maxItems) || Promise.resolve([]),
  });

  useEffect(() => {
    if (historicalTrades) {
      setTrades(historicalTrades);
    }
  }, [historicalTrades]);

  // Subscribe to real-time trades
  useEffect(() => {
    const handleTrade = (trade: TimeAndSale) => {
      if (trade.symbol !== symbol) return;

      setTrades(prev => {
        const newTrades = [trade, ...prev];
        // Keep only maxItems
        return newTrades.slice(0, maxItems);
      });
    };

    const unsubscribe = subscribe('/ws/trades', handleTrade);

    return () => {
      unsubscribe();
    };
  }, [subscribe, symbol, maxItems]);

  // Auto-scroll to top when new trades arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [trades, autoScroll]);

  // Format time
  const formatTime = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  // Format price
  const formatPrice = (price: number): string => {
    const decimals = symbol.includes('JPY') ? 3 : 5;
    return price.toFixed(decimals);
  };

  // Format volume
  const formatVolume = (volume: number): string => {
    if (volume >= 1000000) {
      return `${(volume / 1000000).toFixed(2)}M`;
    } else if (volume >= 1000) {
      return `${(volume / 1000).toFixed(1)}K`;
    }
    return volume.toString();
  };

  // Get row height based on density
  const getRowHeight = () => {
    switch (density) {
      case 'comfortable':
        return 'h-12';
      case 'ultra-dense':
        return 'h-6';
      default:
        return 'h-8';
    }
  };

  // Get container height based on density
  const getContainerHeight = () => {
    switch (density) {
      case 'comfortable':
        return 'max-h-[600px]';
      case 'ultra-dense':
        return 'max-h-[300px]';
      default:
        return 'max-h-[400px]';
    }
  };

  return (
    <DenseCard density={density} className={className}>
      <DenseCardHeader 
        title="Time & Sales"
        description={symbol}
      />
      <DenseCardContent>
        {/* Header */}
        <div className={cn('grid grid-cols-4 gap-2 px-2 pb-2 border-b border-mono-300', getRowHeight())}>
          <div className="text-technical text-xs">TIME</div>
          <div className="text-technical text-xs text-right">PRICE</div>
          <div className="text-technical text-xs text-right">SIZE</div>
          <div className="text-technical text-xs text-center">SIDE</div>
        </div>

        {/* Trades List */}
        <div 
          ref={scrollRef}
          className={cn('overflow-y-auto', getContainerHeight())}
        >
          {trades.length === 0 ? (
            <div className="flex items-center justify-center p-8">
              <div className="text-mono-500 text-sm">No trades yet</div>
            </div>
          ) : (
            trades.map((trade, index) => (
              <div
                key={trade.id}
                className={cn(
                  'grid grid-cols-4 gap-2 px-2 items-center border-b border-mono-200 hover:bg-mono-200 transition-colors',
                  getRowHeight(),
                  index === 0 && 'bg-mono-250 animate-pulse'
                )}
              >
                {/* Time */}
                <div className="font-mono-data text-xs text-mono-500">
                  {formatTime(trade.timestamp)}
                </div>

                {/* Price */}
                <div 
                  className={cn(
                    'font-mono-data text-sm text-right font-semibold',
                    trade.side === 'buy' ? 'text-success' : 'text-destructive'
                  )}
                >
                  {formatPrice(trade.price)}
                </div>

                {/* Volume */}
                <div className="font-mono-data text-xs text-right text-mono-600">
                  {formatVolume(trade.volume)}
                </div>

                {/* Side */}
                <div className="flex justify-center">
                  <StatusBadge
                    severity={trade.side === 'buy' ? 'success' : 'error'}
                  >
                    {trade.side.toUpperCase()}
                  </StatusBadge>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="mt-2 pt-2 border-t border-mono-300 flex items-center justify-between">
          <div className="text-xs text-mono-500">
            Showing {trades.length} trades
          </div>
          <div className="text-xs text-mono-500 font-mono-data">
            Auto-scroll: {autoScroll ? 'ON' : 'OFF'}
          </div>
        </div>
      </DenseCardContent>
    </DenseCard>
  );
}
