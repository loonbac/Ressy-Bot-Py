import { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData, Time } from 'lightweight-charts';

interface LatencyChartProps {
  latencyMs: number | null | undefined;
}

export default function LatencyChart({ latencyMs }: LatencyChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const lastTimeRef = useRef<number>(0);
  // Store the latest value in a ref so the interval always reads fresh data
  const latencyRef = useRef<number | null | undefined>(latencyMs);

  // Keep the ref in sync with the prop on every render
  latencyRef.current = latencyMs;

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: 'solid', color: 'transparent' },
        textColor: 'rgba(117, 86, 94, 0.8)',
      },
      grid: {
        vertLines: { color: 'rgba(117, 86, 94, 0.05)' },
        horzLines: { color: 'rgba(117, 86, 94, 0.05)' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: true,
        borderVisible: false,
      },
      localization: {
        timeFormatter: (businessDayOrTimestamp: number) => {
          return new Date(businessDayOrTimestamp * 1000).toLocaleTimeString('es-PE', {
            timeZone: 'America/Lima',
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
          });
        },
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      crosshair: {
        vertLine: { color: 'rgba(183, 19, 41, 0.3)' },
        horzLine: { color: 'rgba(183, 19, 41, 0.3)' },
      },
      handleScroll: false,
      handleScale: false,
    });

    const series = chart.addAreaSeries({
      lineColor: '#b71329',
      topColor: 'rgba(183, 19, 41, 0.3)',
      bottomColor: 'rgba(183, 19, 41, 0.01)',
      lineWidth: 2,
      crosshairMarkerRadius: 4,
    });

    // Populate initial seed data so the chart isn't empty on load
    const currentTime = Math.floor(Date.now() / 1000);
    const initialData: LineData[] = [];
    let prevVal = 20 + Math.random() * 10;
    for (let i = 20; i > 0; i--) {
      prevVal = prevVal + (Math.random() - 0.5) * 5;
      if (prevVal < 5) prevVal = 5;
      initialData.push({
        time: (currentTime - i * 2) as Time,
        value: prevVal,
      });
    }
    series.setData(initialData);
    lastTimeRef.current = currentTime;

    chartRef.current = chart;
    seriesRef.current = series;

    // Fit content initially so the dummy data is fully visible
    chart.timeScale().fitContent();

    // Push a new data point every 2 seconds, reading the latest value from the ref.
    // This guarantees real-time chart movement even if the prop value stays the same.
    const intervalId = setInterval(() => {
      const value = latencyRef.current;
      if (value == null || !Number.isFinite(value) || !seriesRef.current) return;

      let time = Math.floor(Date.now() / 1000);
      if (time <= lastTimeRef.current) {
        time = lastTimeRef.current + 1;
      }
      lastTimeRef.current = time;

      seriesRef.current.update({ time: time as Time, value });
    }, 2000);

    window.addEventListener('resize', handleResize);

    return () => {
      clearInterval(intervalId);
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  return <div ref={chartContainerRef} className="w-full h-full min-h-[80px]" />;
}
