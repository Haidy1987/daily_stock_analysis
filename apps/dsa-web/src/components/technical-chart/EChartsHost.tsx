import { useEffect, useRef, useState } from 'react';
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

export type EChartsHostErrorPhase = 'init' | 'setOption' | 'resize' | 'dispose';

export type EChartsHostError = {
  phase: EChartsHostErrorPhase;
  message: string;
};

type EChartsHostProps = {
  option: EChartsOption | null;
  className?: string;
  style?: CSSProperties;
  ariaLabel?: string;
  /** Force full replace so previous stock marks/series never linger. */
  resetKey?: string;
  onError?: (error: EChartsHostError) => void;
};

const MAX_INIT_SIZE_RETRIES = 5;

function resolveDevicePixelRatio(): number {
  if (typeof window === 'undefined') {
    return 1;
  }
  return Math.min(window.devicePixelRatio || 1, 2);
}

function hasValidContainerSize(el: HTMLElement): boolean {
  const width = el.clientWidth || el.offsetWidth;
  const height = el.clientHeight || el.offsetHeight;
  return width > 0 && height > 0;
}

function reportHostError(
  onError: EChartsHostProps['onError'],
  phase: EChartsHostErrorPhase,
  error: unknown,
) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Technical chart ${phase} failed`, error);
  onError?.({ phase, message });
}

/**
 * Minimal ECharts lifecycle host: init / setOption / resize / dispose.
 * Designed to survive React StrictMode double-mount and degrade locally on failure.
 */
export function EChartsHost({
  option,
  className = '',
  style,
  ariaLabel = 'technical chart',
  resetKey,
  onError,
}: EChartsHostProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.EChartsType | null>(null);
  const lastResetKeyRef = useRef<string | undefined>(undefined);
  const initRetryCountRef = useRef(0);
  const initFrameRef = useRef<number | null>(null);
  const [chartReadyVersion, setChartReadyVersion] = useState(0);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const el = containerRef.current;
    if (!el) {
      return undefined;
    }

    let disposed = false;
    let resizeObserver: ResizeObserver | null = null;

    const safeResize = () => {
      const chart = chartRef.current;
      if (!chart) {
        return;
      }
      try {
        if (chart.isDisposed()) {
          return;
        }
        chart.resize();
      } catch (error) {
        reportHostError(onError, 'resize', error);
      }
    };

    const attachResizeListeners = () => {
      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(() => safeResize());
        resizeObserver.observe(el);
        return;
      }
      window.addEventListener('resize', safeResize);
    };

    const detachResizeListeners = () => {
      resizeObserver?.disconnect();
      resizeObserver = null;
      window.removeEventListener('resize', safeResize);
    };

    const createChart = (): boolean => {
      if (disposed || typeof window === 'undefined') {
        return false;
      }

      if (!hasValidContainerSize(el)) {
        if (initRetryCountRef.current >= MAX_INIT_SIZE_RETRIES) {
          reportHostError(onError, 'init', new Error('Chart container has zero size'));
          return false;
        }
        initRetryCountRef.current += 1;
        initFrameRef.current = window.requestAnimationFrame(() => {
          initFrameRef.current = null;
          createChart();
        });
        return false;
      }

      initRetryCountRef.current = 0;

      try {
        let chart = echarts.getInstanceByDom(el);
        if (!chart || chart.isDisposed()) {
          chart = echarts.init(el, undefined, {
            renderer: 'canvas',
            devicePixelRatio: resolveDevicePixelRatio(),
          });
        }
        chartRef.current = chart;
        attachResizeListeners();
        setChartReadyVersion((value) => value + 1);
        return true;
      } catch (error) {
        reportHostError(onError, 'init', error);
        return false;
      }
    };

    createChart();

    return () => {
      disposed = true;

      if (initFrameRef.current != null) {
        window.cancelAnimationFrame(initFrameRef.current);
        initFrameRef.current = null;
      }

      detachResizeListeners();

      const chart = chartRef.current;
      chartRef.current = null;

      // Dispose failures must never surface as UI errors — they often mask the
      // original init/setOption/resize failure that already triggered remount.
      try {
        if (chart && !chart.isDisposed()) {
          chart.dispose();
        }
      } catch (error) {
        console.warn('Technical chart dispose failed', error);
      }
    };
  }, [onError]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !option) {
      return;
    }

    try {
      if (chart.isDisposed()) {
        return;
      }
      const shouldReset = resetKey !== undefined && resetKey !== lastResetKeyRef.current;
      lastResetKeyRef.current = resetKey;
      if (shouldReset || resetKey === undefined) {
        chart.setOption(option, { notMerge: true, lazyUpdate: false });
      } else {
        chart.setOption(option, {
          notMerge: false,
          lazyUpdate: false,
          replaceMerge: ['series', 'xAxis', 'yAxis', 'grid', 'legend'],
        });
      }
    } catch (error) {
      reportHostError(onError, 'setOption', error);
      return;
    }

    try {
      if (chart.isDisposed()) {
        return;
      }
      chart.resize();
    } catch (error) {
      reportHostError(onError, 'resize', error);
    }
  }, [onError, option, resetKey, chartReadyVersion]);

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
