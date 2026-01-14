/**
 * PositionTable Component
 * 
 * Displays current trading positions with real-time updates.
 * Supports density variants and follows the terminal/print aesthetic.
 */

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api-factory';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { 
  DataTable, 
  DataTableHeader, 
  DataTableBody, 
  DataTableRow, 
  DataTableCell 
} from '@/components/common/DataTable';
import { StatusBadge } from '@/components/common/StatusBadge';
import type { Position } from '@/types/trading';

interface PositionTableProps {
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
  onPositionClick?: (position: Position) => void;
}

export function PositionTable({ 
  density = 'dense',
  className,
  onPositionClick
}: PositionTableProps) {
  const [positions, setPositions] = useState<Position[]>([]);

  // Fetch initial positions
  const { data: initialPositions, isLoading } = useQuery({
    queryKey: ['positions'],
    queryFn: () => api.getPositions?.() || Promise.resolve([]),
    refetchInterval: 30000, // Fallback polling every 30s
  });

  // Subscribe to real-time position updates via WebSocket
  const { subscribe } = useWebSocketContext();

  useEffect(() => {
    if (initialPositions) {
      setPositions(initialPositions);
    }
  }, [initialPositions]);

  useEffect(() => {
    const handlePositionUpdate = (data: Position[]) => {
      setPositions(data);
    };

    const unsubscribe = subscribe('/ws/positions', handlePositionUpdate);

    return () => {
      unsubscribe();
    };
  }, [subscribe]);

  // Format currency values
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  // Format percentage
  const formatPercent = (value: number): string => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
  };


  const columns = [
    {
      key: 'symbol',
      header: 'Symbol',
      render: (position: Position) => (
        <span className="text-technical">{position.symbol}</span>
      ),
    },
    {
      key: 'order_type',
      header: 'Side',
      render: (position: Position) => (
        <StatusBadge 
          severity={position.order_type === 'BUY' ? 'success' : 'error'}
        >
          {position.order_type}
        </StatusBadge>
      ),
    },
    {
      key: 'volume',
      header: 'Volume',
      render: (position: Position) => (
        <span className="font-mono-data">{position.volume.toLocaleString()}</span>
      ),
    },
    {
      key: 'entry_price',
      header: 'Entry Price',
      render: (position: Position) => (
        <span className="font-mono-data">{position.entry_price.toFixed(5)}</span>
      ),
    },
    {
      key: 'current_price',
      header: 'Current Price',
      render: (position: Position) => (
        <span className="font-mono-data">{position.current_price.toFixed(5)}</span>
      ),
    },
    {
      key: 'unrealized_pnl',
      header: 'P&L',
      render: (position: Position) => (
        <span 
          className={`font-mono-data ${
            position.unrealized_pnl > 0 
              ? 'text-success' 
              : position.unrealized_pnl < 0 
              ? 'text-destructive' 
              : 'text-warning'
          }`}
        >
          {formatCurrency(position.unrealized_pnl)}
        </span>
      ),
    },
    {
      key: 'unrealized_pnl_pct',
      header: 'P&L %',
      render: (position: Position) => (
        <span 
          className={`font-mono-data ${
            position.unrealized_pnl_pct > 0 
              ? 'text-success' 
              : position.unrealized_pnl_pct < 0 
              ? 'text-destructive' 
              : 'text-warning'
          }`}
        >
          {formatPercent(position.unrealized_pnl_pct)}
        </span>
      ),
    },
    {
      key: 'opened_at',
      header: 'Opened',
      render: (position: Position) => {
        const date = new Date(position.opened_at);
        return (
          <span className="font-mono-data text-mono-500">
            {date.toLocaleDateString()} {date.toLocaleTimeString()}
          </span>
        );
      },
    },
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-mono-500">Loading positions...</div>
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-mono-500">No open positions</div>
      </div>
    );
  }

  return (
    <DataTable density={density} className={className}>
      <DataTableHeader>
        <tr>
          {columns.map((col) => (
            <DataTableCell key={col.key} header>
              {col.header}
            </DataTableCell>
          ))}
        </tr>
      </DataTableHeader>
      <DataTableBody>
        {positions.map((position) => (
          <DataTableRow 
            key={position.id}
            onClick={() => onPositionClick?.(position)}
          >
            {columns.map((col) => (
              <DataTableCell key={col.key}>
                {col.render(position)}
              </DataTableCell>
            ))}
          </DataTableRow>
        ))}
      </DataTableBody>
    </DataTable>
  );
}
