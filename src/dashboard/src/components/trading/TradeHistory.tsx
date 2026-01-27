/**
 * TradeHistory Component
 * 
 * Displays historical trades with filtering and pagination.
 * Follows the terminal/print aesthetic design system.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api-factory';
import { 
  DataTable, 
  DataTableHeader, 
  DataTableBody, 
  DataTableRow, 
  DataTableCell 
} from '@/components/common/DataTable';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { Trade } from '@/types/performance';

interface TradeHistoryProps {
  density?: 'comfortable' | 'dense' | 'ultra-dense';
  className?: string;
  experimentId?: number;
  limit?: number;
}

export function TradeHistory({ 
  density = 'dense',
  className,
  experimentId,
  limit = 100
}: TradeHistoryProps) {
  const [filters, setFilters] = useState({
    symbol: '',
    startDate: '',
    endDate: '',
    experimentId: experimentId,
    limit: limit,
    offset: 0,
  });

  const [currentPage, setCurrentPage] = useState(0);

  // Fetch trade history
  const { data, isLoading, error } = useQuery({
    queryKey: ['tradeHistory', filters],
    queryFn: () => api.getTradeHistory?.(filters) || Promise.resolve({ trades: [], total: 0 }),
  });

  const trades = data?.trades || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / filters.limit);

  // Format currency
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

  // Handle filter changes
  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
      offset: 0, // Reset to first page
    }));
    setCurrentPage(0);
  };

  // Handle pagination
  const handleNextPage = () => {
    if (currentPage < totalPages - 1) {
      const nextPage = currentPage + 1;
      setCurrentPage(nextPage);
      setFilters(prev => ({
        ...prev,
        offset: nextPage * filters.limit,
      }));
    }
  };

  const handlePrevPage = () => {
    if (currentPage > 0) {
      const prevPage = currentPage - 1;
      setCurrentPage(prevPage);
      setFilters(prev => ({
        ...prev,
        offset: prevPage * filters.limit,
      }));
    }
  };

  // Export trades to CSV
  const handleExport = () => {
    if (trades.length === 0) return;

    const headers = ['Symbol', 'Side', 'Volume', 'Entry Price', 'Exit Price', 'P&L', 'P&L %', 'Opened', 'Closed', 'Duration'];
    const rows = trades.map(trade => [
      trade.symbol,
      trade.side || trade.order_type,
      trade.volume,
      trade.entry_price,
      trade.exit_price || '',
      trade.pnl ?? '',
      trade.pnl_pct ?? '',
      trade.entry_time,
      trade.closed_at || trade.exit_time || '',
      trade.duration_seconds ?? '',
    ]);

    const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trade-history-${new Date().toISOString()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns = [
    {
      key: 'symbol',
      header: 'Symbol',
      render: (trade: Trade) => (
        <span className="text-technical">{trade.symbol}</span>
      ),
    },
    {
      key: 'side',
      header: 'Side',
      render: (trade: Trade) => {
        const side = trade.side || trade.order_type;
        return (
          <StatusBadge 
            severity={side === 'BUY' ? 'success' : 'error'}
          >
            {side}
          </StatusBadge>
        );
      },
    },
    {
      key: 'volume',
      header: 'Volume',
      render: (trade: Trade) => (
        <span className="font-mono-data">{trade.volume.toLocaleString()}</span>
      ),
    },
    {
      key: 'entry_price',
      header: 'Entry',
      render: (trade: Trade) => (
        <span className="font-mono-data">{trade.entry_price.toFixed(5)}</span>
      ),
    },
    {
      key: 'exit_price',
      header: 'Exit',
      render: (trade: Trade) => (
        <span className="font-mono-data">{trade.exit_price?.toFixed(5) || '-'}</span>
      ),
    },
    {
      key: 'pnl',
      header: 'P&L',
      render: (trade: Trade) => (
        <span 
          className={`font-mono-data ${
            (trade.pnl ?? 0) > 0 
              ? 'text-success' 
              : (trade.pnl ?? 0) < 0 
              ? 'text-destructive' 
              : 'text-warning'
          }`}
        >
          {formatCurrency(trade.pnl ?? 0)}
        </span>
      ),
    },
    {
      key: 'pnl_pct',
      header: 'P&L %',
      render: (trade: Trade) => (
        <span 
          className={`font-mono-data ${
            (trade.pnl_pct ?? 0) > 0 
              ? 'text-success' 
              : (trade.pnl_pct ?? 0) < 0 
              ? 'text-destructive' 
              : 'text-warning'
          }`}
        >
          {formatPercent(trade.pnl_pct ?? 0)}
        </span>
      ),
    },
    {
      key: 'closed_at',
      header: 'Closed',
      render: (trade: Trade) => {
        const date = trade.closed_at || trade.exit_time;
        if (!date) return <span className="font-mono-data text-mono-500">-</span>;
        return (
          <span className="font-mono-data text-mono-500">
            {new Date(date).toLocaleDateString()}
          </span>
        );
      },
    },
    {
      key: 'duration',
      header: 'Duration',
      render: (trade: Trade) => {
        if (!trade.duration_seconds) {
          return <span className="font-mono-data text-mono-500">-</span>;
        }
        const hours = Math.floor(trade.duration_seconds / 3600);
        const minutes = Math.floor((trade.duration_seconds % 3600) / 60);
        return (
          <span className="font-mono-data text-mono-500">
            {hours}h {minutes}m
          </span>
        );
      },
    },
  ];

  if (error) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-destructive">Error loading trade history</div>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="text-technical text-xs mb-2 block">Symbol</label>
          <Input
            placeholder="Filter by symbol..."
            value={filters.symbol}
            onChange={(e) => handleFilterChange('symbol', e.target.value)}
            className="font-mono-data"
          />
        </div>
        <div className="flex-1 min-w-[200px]">
          <label className="text-technical text-xs mb-2 block">Start Date</label>
          <Input
            type="date"
            value={filters.startDate}
            onChange={(e) => handleFilterChange('startDate', e.target.value)}
            className="font-mono-data"
          />
        </div>
        <div className="flex-1 min-w-[200px]">
          <label className="text-technical text-xs mb-2 block">End Date</label>
          <Input
            type="date"
            value={filters.endDate}
            onChange={(e) => handleFilterChange('endDate', e.target.value)}
            className="font-mono-data"
          />
        </div>
        <Button
          onClick={handleExport}
          disabled={trades.length === 0}
          variant="outline"
          className="focus:ring-2 focus:ring-orange-400"
        >
          Export CSV
        </Button>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex items-center justify-center p-8">
          <div className="text-mono-500">Loading trades...</div>
        </div>
      ) : trades.length === 0 ? (
        <div className="flex items-center justify-center p-8">
          <div className="text-mono-500">No trades found</div>
        </div>
      ) : (
        <>
          <DataTable density={density}>
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
              {trades.map((trade) => (
                <DataTableRow key={trade.id}>
                  {columns.map((col) => (
                    <DataTableCell key={col.key}>
                      {col.render(trade)}
                    </DataTableCell>
                  ))}
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>

          {/* Pagination */}
          <div className="mt-4 flex items-center justify-between">
            <div className="text-mono-500 text-sm font-mono-data">
              Showing {filters.offset + 1} - {Math.min(filters.offset + filters.limit, total)} of {total} trades
            </div>
            <div className="flex gap-2">
              <Button
                onClick={handlePrevPage}
                disabled={currentPage === 0}
                variant="outline"
                size="sm"
                className="focus:ring-2 focus:ring-orange-400"
              >
                Previous
              </Button>
              <Button
                onClick={handleNextPage}
                disabled={currentPage >= totalPages - 1}
                variant="outline"
                size="sm"
                className="focus:ring-2 focus:ring-orange-400"
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
