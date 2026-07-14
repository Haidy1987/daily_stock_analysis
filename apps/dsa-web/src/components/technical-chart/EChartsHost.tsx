import { useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';
import type { EChartsOption } from 'echarts';
import * as echarts from 'echarts/core';
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts';
import {
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  CandlestickChart,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  DataZoomComponent,
  AxisPointerComponent,
  MarkLineComponent,
  MarkPointComponent,
  LegendComponent,
  CanvasRenderer,
]);

type EChartsHostProps = {
  option: EChartsOption | null;
  className?: string;
  style?: CSSProperties;
  ariaLabel?: string;
  /** Force full replace so previous stock marks/series never linger. */
  resetKey?: string;
};

/**
 * Minimal ECharts lifecycle host: init / setOption / resize / dispose.
 * Designed to survive React StrictMode double-mount.
 */
export function EChartsHost({
  option,
  className = '',
  style,
  ariaLabel = 'technical chart',
  resetKey,
}: EChartsHostProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.EChartsType | null>(null);
  const lastResetKeyRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;

    let chart = echarts.getInstanceByDom(el);
    if (!chart) {
      chart = echarts.init(el, undefined, { renderer: 'canvas' });
    }
    chartRef.current = chart;

    let resizeObserver: ResizeObserver | null = null;
    const handleResize = () => {
      chartRef.current?.resize();
    };

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => handleResize());
      resizeObserver.observe(el);
    } else if (typeof window !== 'undefined') {
      window.addEventListener('resize', handleResize);
    }

    return () => {
      resizeObserver?.disconnect();
      if (typeof window !== 'undefined') {
        window.removeEventListener('resize', handleResize);
      }
      // Dispose only the instance we own for this DOM node.
      const current = echarts.getInstanceByDom(el);
      current?.dispose();
      if (chartRef.current === current) {
        chartRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || chart.isDisposed() || !option) {
      return;
    }
    const shouldReset = resetKey !== undefined && resetKey !== lastResetKeyRef.current;
    lastResetKeyRef.current = resetKey;
    if (shouldReset || resetKey === undefined) {
      chart.setOption(option, { notMerge: true, lazyUpdate: false });
    } else {
      // Keep zoom range while replacing grids/axes/series when panels toggle.
      chart.setOption(option, {
        notMerge: false,
        lazyUpdate: false,
        replaceMerge: ['series', 'xAxis', 'yAxis', 'grid', 'legend'],
      });
    }
    // Always resize after option updates in case the container became visible.
    chart.resize();
  }, [option, resetKey]);

  return (
    <div
      ref={containerRef}
      className={className}
      style={style}
      data-testid="technical-chart-echarts-host"
      role="img"
      aria-label={ariaLabel}
    />
  );
}

export default EChartsHost;
