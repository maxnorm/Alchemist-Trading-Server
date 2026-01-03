import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi, LineData, Time } from 'lightweight-charts'
import type { EquityPoint } from '@/types/performance'

interface EquityCurveChartProps {
  data: EquityPoint[]
  height?: number
  showDrawdown?: boolean
}

export function EquityCurveChart({ data, height = 400, showDrawdown = true }: EquityCurveChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const equitySeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const drawdownSeriesRef = useRef<ISeriesApi<'Area'> | null>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { color: 'transparent' },
        textColor: '#d1d5db',
      },
      grid: {
        vertLines: { color: '#374151' },
        horzLines: { color: '#374151' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#374151',
      },
    })

    chartRef.current = chart

    // Create equity series
    const equitySeries = chart.addLineSeries({
      color: '#3b82f6',
      lineWidth: 2,
      title: 'Equity',
      priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
      },
    })
    equitySeriesRef.current = equitySeries

    // Create drawdown series if enabled
    if (showDrawdown) {
      const drawdownSeries = chart.addAreaSeries({
        lineColor: '#ef4444',
        topColor: 'rgba(239, 68, 68, 0.2)',
        bottomColor: 'rgba(239, 68, 68, 0.05)',
        lineWidth: 1,
        title: 'Drawdown',
        priceFormat: {
          type: 'percent',
          precision: 2,
          minMove: 0.01,
        },
      })
      drawdownSeriesRef.current = drawdownSeries
    }

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chart) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [height, showDrawdown])

  useEffect(() => {
    if (!equitySeriesRef.current || !data.length) return

    // Convert data to chart format
    const equityData: LineData<Time>[] = data.map((point) => ({
      time: (new Date(point.timestamp).getTime() / 1000) as Time,
      value: point.equity,
    }))

    equitySeriesRef.current.setData(equityData)

    // Update drawdown if enabled
    if (showDrawdown && drawdownSeriesRef.current) {
      const drawdownData = data.map((point) => ({
        time: (new Date(point.timestamp).getTime() / 1000) as Time,
        value: point.drawdown_pct / 100, // Convert to decimal
      }))

      drawdownSeriesRef.current.setData(drawdownData)
    }

    // Fit content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent()
    }
  }, [data, showDrawdown])

  return (
    <div className="w-full">
      <div ref={chartContainerRef} className="w-full" style={{ height: `${height}px` }} />
    </div>
  )
}
