/**
 * PriceTicker Component
 * 
 * Displays real-time price updates for multiple symbols.
 * Uses WebSocket for live price feeds with animated price changes.
 */

import { useEffect, useState } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { WS_CHANNELS } from '@/services/websocket';
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common/DenseCard';
import type { PriceTick } from '@/types/market';
import { cn } from '@/utils/cn';

interface PriceTickerProps {
  symbols?: string[];
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
  layout?: 'grid' | 'list';
}

export function PriceTicker({ 
  symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'],
  density = 'dense',
  className,
  layout = 'grid'
}: PriceTickerProps) {
  const [prices, setPrices] = useState<Map<string, PriceTick>>(new Map());
  const [priceChanges, setPriceChanges] = useState<Map<string, 'up' | 'down' | 'neutral'>>(new Map());
  const { subscribe } = useWebSocketContext();

  useEffect(() => {
    const handlePriceTick = (tick: PriceTick) => {
      // Only process ticks for symbols we're watching
      if (!symbols.includes(tick.symbol)) return;

      setPrices(prev => {
        const oldTick = prev.get(tick.symbol);
        const newPrices = new Map(prev);
        newPrices.set(tick.symbol, tick);

        // Determine price change direction
        if (oldTick) {
          const oldMid = (oldTick.bid + oldTick.ask) / 2;
          const newMid = (tick.bid + tick.ask) / 2;
          
          setPriceChanges(prevChanges => {
            const newChanges = new Map(prevChanges);
            if (newMid > oldMid) {
              newChanges.set(tick.symbol, 'up');
            } else if (newMid < oldMid) {
              newChanges.set(tick.symbol, 'down');
            } else {
              newChanges.set(tick.symbol, 'neutral');
            }
            return newChanges;
          });

          // Reset animation after 500ms
          setTimeout(() => {
            setPriceChanges(prevChanges => {
              const newChanges = new Map(prevChanges);
              newChanges.set(tick.symbol, 'neutral');
              return newChanges;
            });
          }, 500);
        }

        return newPrices;
      });
    };

    const unsubscribe = subscribe(WS_CHANNELS.ticks, handlePriceTick);

    return () => {
      unsubscribe();
    };
  }, [subscribe, symbols]);

  // Format price with appropriate decimal places
  const formatPrice = (price: number, symbol: string): string => {
    const decimals = symbol.includes('JPY') ? 3 : 5;
    return price.toFixed(decimals);
  };

  // Format percentage
  const formatPercent = (value: number | undefined): string => {
    if (value === undefined) return '-';
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  // Get price change class
  const getPriceChangeClass = (symbol: string): string => {
    const change = priceChanges.get(symbol);
    switch (change) {
      case 'up':
        return 'text-success animate-pulse';
      case 'down':
        return 'text-destructive animate-pulse';
      default:
        return '';
    }
  };

  // Get change indicator
  const getChangeIndicator = (changePercent: number | undefined) => {
    if (changePercent === undefined) return null;
    if (changePercent > 0) return '▲';
    if (changePercent < 0) return '▼';
    return '●';
  };

  const renderTickerItem = (symbol: string) => {
    const tick = prices.get(symbol);
    
    if (!tick) {
      return (
        <div key={symbol} className="p-4 bg-mono-200 rounded border border-mono-300">
          <div className="text-technical text-sm mb-2">{symbol}</div>
          <div className="text-mono-500 text-sm">Waiting for data...</div>
        </div>
      );
    }

    // const mid = (tick.bid + tick.ask) / 2;
    const spread = tick.ask - tick.bid;

    return (
      <div 
        key={symbol} 
        className="p-4 bg-mono-200 rounded border border-mono-300 hover:border-orange-400 transition-colors"
      >
        {/* Symbol */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-technical text-sm">{symbol}</span>
          {tick.changePercent !== undefined && (
            <span 
              className={cn(
                'text-xs font-mono-data',
                tick.changePercent > 0 ? 'text-success' : 
                tick.changePercent < 0 ? 'text-destructive' : 
                'text-warning'
              )}
            >
              {getChangeIndicator(tick.changePercent)} {formatPercent(tick.changePercent)}
            </span>
          )}
        </div>

        {/* Bid/Ask */}
        <div className="grid grid-cols-2 gap-2 mb-2">
          <div>
            <div className="text-xs text-mono-500 mb-1">BID</div>
            <div className={cn('font-mono-data text-lg font-semibold', getPriceChangeClass(symbol))}>
              {formatPrice(tick.bid, symbol)}
            </div>
          </div>
          <div>
            <div className="text-xs text-mono-500 mb-1">ASK</div>
            <div className={cn('font-mono-data text-lg font-semibold', getPriceChangeClass(symbol))}>
              {formatPrice(tick.ask, symbol)}
            </div>
          </div>
        </div>

        {/* Additional Info */}
        <div className="flex items-center justify-between text-xs text-mono-500">
          <span className="font-mono-data">
            Spread: {formatPrice(spread, symbol)}
          </span>
          {tick.volume && (
            <span className="font-mono-data">
              Vol: {(tick.volume / 1000000).toFixed(2)}M
            </span>
          )}
        </div>
      </div>
    );
  };

  return (
    <DenseCard density={density} className={className}>
      <DenseCardHeader 
        title="Live Prices"
        description={`${symbols.length} pairs`}
      />
      <DenseCardContent>
        <div 
          className={cn(
            layout === 'grid' 
              ? 'grid gap-4' 
              : 'flex flex-col gap-2',
            layout === 'grid' && 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4'
          )}
        >
          {symbols.map(renderTickerItem)}
        </div>
      </DenseCardContent>
    </DenseCard>
  );
}
