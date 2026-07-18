import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as echarts from 'echarts/core';
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts';
import {
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  MarkPointComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { TechnicalChartResponse } from '../../../api/technicalChart';
import {
  buildTechnicalChartOption,
} from '../buildTechnicalChartOption';
import type { TechnicalChartThemeColors } from '../themeColors';

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
  TitleComponent,
  LegendComponent,
  CanvasRenderer,
]);

const colors: TechnicalChartThemeColors = {
  up: '#ef4444',
  down: '#22c55e',
  text: '#111827',
  muted: '#6b7280',
  border: '#e5e7eb',
  background: 'transparent',
  tooltipBg: '#ffffff',
  ma5: '#38bdf8',
  ma10: '#a78bfa',
  ma20: '#f59e0b',
  ma30: '#facc15',
  ma60: '#3b82f6',
  ma90: '#ec4899',
  ma120: '#14b8a6',
  ma250: '#94a3b8',
  bollUpper: '#94a3b8',
  bollMid: '#64748b',
  bollLower: '#94a3b8',
  support: '#16a34a',
  resistance: '#dc2626',
  markHigh: '#dc2626',
  markLow: '#16a34a',
};

function makeResponse(): TechnicalChartResponse {
  return {
    stockCode: '600519',
    stockName: '贵州茅台',
    period: 'daily',
    rangeDays: 120,
    calculationVersion: 'technical-v1',
    dataStatus: 'available',
    dataSource: 'mock',
    updatedAt: '2026-07-14T00:00:00Z',
    items: [
      {
        date: '2026-07-10',
        open: 100,
        high: 110,
        low: 95,
        close: 105,
        volume: 1000,
        ma5: null,
        ma10: null,
        ma20: null,
        ma30: null,
        ma60: null,
        ma90: null,
        ma120: null,
        ma250: null,
        macdDif: null,
        macdDea: null,
        macdBar: null,
        rsi6: null,
        rsi12: null,
        rsi24: null,
        kdjK: null,
        kdjD: null,
        kdjJ: null,
        cci: null,
        bias5: null,
        bias10: null,
        bias20: null,
        volumeRatio: 1.2,
        volumeStatus: 'normal',
      },
      {
        date: '2026-07-11',
        open: 105,
        high: 108,
        low: 101,
        close: 102,
        volume: 800,
        ma5: 103,
        ma10: 104,
        ma20: 105,
        ma30: 106,
        ma60: 107,
        ma90: 108,
        ma120: 109,
        ma250: 110,
        bollUpper: 110,
        bollMid: 105,
        bollLower: 100,
        bollBandwidth: 0.1,
        bollPosition: 0.4,
        macdDif: 1.2,
        macdDea: 0.8,
        macdBar: 0.8,
        rsi6: 62,
        rsi12: 55,
        rsi24: 48,
        kdjK: 70,
        kdjD: 60,
        kdjJ: 90,
        cci: 120,
        bias5: 1.5,
        bias10: 0.8,
        bias20: 0.3,
        volumeRatio: 0.9,
        volumeStatus: 'normal',
      },
    ],
    summary: {
      latestClose: 102,
      latestChangePercent: -2.86,
      latestVolumeStatus: 'normal',
      volumeRatio: 0.9,
      supportLevels: [{ price: 95, label: 'S1', source: 'swing' }],
      resistanceLevels: [{ price: 110, label: 'R1', source: 'swing' }],
      recentHigh: { date: '2026-07-10', price: 110 },
      recentLow: { date: '2026-07-11', price: 101 },
    },
    warnings: [],
  };
}

/** Minimal Canvas 2D stub so real ECharts can init/setOption under jsdom. */
function installCanvasStub() {
  const proto = HTMLCanvasElement.prototype as HTMLCanvasElement & {
    getContext: typeof HTMLCanvasElement.prototype.getContext;
  };
  const original = proto.getContext;
  const noop = () => undefined;
  const gradient = () => ({ addColorStop: noop });
  proto.getContext = function getContext(
    this: HTMLCanvasElement,
    contextId: string,
    options?: CanvasRenderingContext2DSettings,
  ) {
    if (contextId !== '2d') {
      return original.call(this, contextId as '2d', options);
    }
    const base: Record<string, unknown> = {
      canvas: this,
      fillStyle: '#000',
      strokeStyle: '#000',
      lineWidth: 1,
      globalAlpha: 1,
      font: '10px sans-serif',
      textAlign: 'start',
      textBaseline: 'alphabetic',
      measureText: (text: string) => ({ width: String(text).length * 6 }),
      createLinearGradient: gradient,
      createRadialGradient: gradient,
      createPattern: () => null,
      getImageData: () => ({ data: new Uint8ClampedArray(4), width: 1, height: 1 }),
      createImageData: () => ({ data: new Uint8ClampedArray(4), width: 1, height: 1 }),
    };
    return new Proxy(base, {
      get(target, prop, receiver) {
        if (prop in target) {
          return Reflect.get(target, prop, receiver);
        }
        if (typeof prop === 'string') {
          const fn = vi.fn(noop);
          target[prop] = fn;
          return fn;
        }
        return undefined;
      },
      set(target, prop, value) {
        target[prop as string] = value;
        return true;
      },
    }) as unknown as CanvasRenderingContext2D;
  } as typeof HTMLCanvasElement.prototype.getContext;

  return () => {
    proto.getContext = original;
  };
}

describe('buildTechnicalChartOption × real ECharts setOption', () => {
  let chart: echarts.ECharts | undefined;
  let container: HTMLDivElement | undefined;
  let restoreCanvas: (() => void) | undefined;

  beforeEach(() => {
    restoreCanvas = installCanvasStub();
  });

  afterEach(() => {
    try {
      if (chart && !chart.isDisposed()) {
        chart.dispose();
      }
    } catch {
      // jsdom canvas stubs may fail during dispose; ignore cleanup errors.
    }
    chart = undefined;
    container?.remove();
    container = undefined;
    restoreCanvas?.();
    restoreCanvas = undefined;
  });

  it('accepts multi-xAxis option with K/volume/BOLL/MACD, axisPointer.link and tooltip cross without throwing', () => {
    container = document.createElement('div');
    container.style.width = '800px';
    container.style.height = '900px';
    Object.defineProperty(container, 'clientWidth', { configurable: true, value: 800 });
    Object.defineProperty(container, 'clientHeight', { configurable: true, value: 900 });
    Object.defineProperty(container, 'offsetWidth', { configurable: true, value: 800 });
    Object.defineProperty(container, 'offsetHeight', { configurable: true, value: 900 });
    document.body.appendChild(container);

    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible: {
        ma: true,
        boll: true,
        volume: true,
        macd: true,
        rsi: false,
        kdj: false,
        cci: false,
        bias: false,
        supportResistance: true,
      },
    });

    const xAxis = option.xAxis as unknown[];
    expect(xAxis.length).toBe(4);
    expect(option.axisPointer).toMatchObject({ link: [{ xAxisIndex: 'all' }] });
    expect(option.tooltip).toMatchObject({
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    });

    const series = option.series as Array<{ type?: string; name?: string; xAxisIndex?: number }>;
    expect(series.some((item) => item.type === 'candlestick')).toBe(true);
    expect(series.find((item) => item.name === 'Vol')?.xAxisIndex).toBe(1);
    expect(series.find((item) => item.name === 'BOLL.M')?.xAxisIndex).toBe(2);
    expect(series.find((item) => item.name === 'DIF')?.xAxisIndex).toBe(3);

    expect(() => {
      chart = echarts.init(container!, undefined, { renderer: 'canvas', width: 800, height: 900 });
      chart.setOption(option, { notMerge: true, lazyUpdate: false });
    }).not.toThrow();
  });
});
