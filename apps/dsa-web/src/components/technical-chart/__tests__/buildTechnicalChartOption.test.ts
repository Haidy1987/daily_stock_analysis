import { describe, expect, it } from 'vitest';
import type { TechnicalChartResponse } from '../../../api/technicalChart';
import {
  buildPanelIndexMap,
  buildTechnicalChartOption,
  formatTooltipValue,
  isUpBar,
  nullableSeriesValue,
  panelsToIndicatorsCsv,
  parseVisiblePanels,
  toCandlestickValue,
  togglePanel,
  estimateTechnicalChartHeight,
  TECHNICAL_CHART_PC_DEFAULT_PANELS,
} from '../buildTechnicalChartOption';
import type { TechnicalChartThemeColors } from '../themeColors';

const colors: TechnicalChartThemeColors = {
  up: 'up-red',
  down: 'down-green',
  text: 'text',
  muted: 'muted',
  border: 'border',
  background: 'transparent',
  tooltipBg: 'tooltip',
  ma5: 'ma5',
  ma10: 'ma10',
  ma20: 'ma20',
  ma30: 'ma30',
  ma60: 'ma60',
  ma90: 'ma90',
  ma120: 'ma120',
  ma250: 'ma250',
  bollUpper: 'bu',
  bollMid: 'bm',
  bollLower: 'bl',
  support: 'support',
  resistance: 'resistance',
  markHigh: 'high',
  markLow: 'low',
};

function makeResponse(overrides: Partial<TechnicalChartResponse> = {}): TechnicalChartResponse {
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
        ma10: null,
        ma20: null,
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
        bias20: -0.4,
        volumeRatio: 0.8,
        volumeStatus: 'shrink',
      },
    ],
    summary: {
      latestClose: 102,
      latestChangePercent: -2.8,
      latestVolumeStatus: 'shrink',
      volumeRatio: 0.8,
      supportLevels: [
        { price: 95, label: 'S1', source: 'swing' },
        { price: 95.2, label: 'S1-near', source: 'swing' },
        { price: 90, label: 'S2', source: 'swing' },
      ],
      resistanceLevels: [
        { price: 110, label: 'R1', source: 'swing' },
      ],
      recentHigh: { price: 110, date: '2026-07-10' },
      recentLow: { price: 101, date: '2026-07-11' },
    },
    warnings: [],
    ...overrides,
  };
}

describe('toCandlestickValue', () => {
  it('uses ECharts open/close/low/high order', () => {
    expect(toCandlestickValue({ open: 1, close: 2, low: 0.5, high: 3 })).toEqual([1, 2, 0.5, 3]);
  });
});

describe('nullableSeriesValue / formatTooltipValue', () => {
  it('keeps null/NaN as null instead of filling zero', () => {
    expect(nullableSeriesValue(null)).toBeNull();
    expect(nullableSeriesValue(undefined)).toBeNull();
    expect(nullableSeriesValue(Number.NaN)).toBeNull();
    expect(nullableSeriesValue(12.5)).toBe(12.5);
  });

  it('formats tooltip null as -- without inventing 0 or re-scaling percents', () => {
    expect(formatTooltipValue(null)).toBe('--');
    expect(formatTooltipValue(1.5)).toBe('1.50');
    expect(formatTooltipValue(1.2345, 2)).toBe('1.23');
  });
});

describe('parseVisiblePanels / panelsToIndicatorsCsv', () => {
  it('uses PC defaults when indicators are empty', () => {
    expect(parseVisiblePanels('')).toEqual(TECHNICAL_CHART_PC_DEFAULT_PANELS);
    expect(parseVisiblePanels(null).kdj).toBe(true);
    expect(parseVisiblePanels(null).macd).toBe(true);
  });

  it('parses tokens and round-trips through CSV', () => {
    const visible = parseVisiblePanels('ma,volume,macd,kdj,support_resistance');
    expect(visible).toEqual({
      ma: true,
      boll: false,
      volume: true,
      macd: true,
      rsi: false,
      kdj: true,
      cci: false,
      bias: false,
      supportResistance: true,
    });
    expect(panelsToIndicatorsCsv(visible)).toBe('ma,volume,macd,kdj,support_resistance');
  });

  it('toggles a panel independently', () => {
    const next = togglePanel(TECHNICAL_CHART_PC_DEFAULT_PANELS, 'kdj');
    expect(next.kdj).toBe(false);
    expect(next.macd).toBe(true);
  });
});

describe('buildPanelIndexMap', () => {
  it('reindexes later panels when a middle panel is closed', () => {
    const withVolume = buildPanelIndexMap({
      ...TECHNICAL_CHART_PC_DEFAULT_PANELS,
      volume: true,
      boll: true,
      macd: true,
      rsi: true,
      kdj: false,
    });
    expect(withVolume).toMatchObject({
      price: 0,
      volume: 1,
      boll: 2,
      macd: 3,
      rsi: 4,
      kdj: undefined,
    });

    const withoutVolume = buildPanelIndexMap({
      ...TECHNICAL_CHART_PC_DEFAULT_PANELS,
      volume: false,
      boll: false,
      macd: true,
      rsi: true,
      kdj: false,
    });
    expect(withoutVolume).toMatchObject({ price: 0, volume: undefined, boll: undefined, macd: 1, rsi: 2 });
  });
});

describe('buildTechnicalChartOption', () => {
  it('aligns candles, MA/BOLL nulls and volume colors', () => {
    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible: { ...TECHNICAL_CHART_PC_DEFAULT_PANELS, macd: false, rsi: false },
    });
    const xAxis = option.xAxis as Array<{ data: string[] }>;
    expect(xAxis[0].data).toEqual(['2026-07-10', '2026-07-11']);

    const series = option.series as Array<Record<string, unknown>>;
    const candle = series.find((item) => item.type === 'candlestick') as {
      data: Array<[number, number, number, number]>;
      markLine?: { data: Array<{ yAxis: number }> };
    };
    expect(candle.data[0]).toEqual([100, 105, 95, 110]);
    expect(candle.data[1]).toEqual([105, 102, 101, 108]);

    const ma5 = series.find((item) => item.name === 'MA5') as { data: Array<number | null> };
    expect(ma5.data).toEqual([null, 103]);
    expect(series.filter((item) => /^MA(5|10|20|30|60|90|120|250)$/.test(String(item.name))))
      .toHaveLength(8);
    const ma250 = series.find((item) => item.name === 'MA250') as { data: Array<number | null> };
    expect(ma250.data).toEqual([null, 110]);

    const volume = series.find((item) => item.name === 'Vol') as {
      data: Array<{ value: number | null; itemStyle: { color: string } }>;
      xAxisIndex: number;
      yAxisIndex: number;
    };
    expect(volume.xAxisIndex).toBe(1);
    expect(volume.data[0].itemStyle.color).toBe(colors.up);
    expect(volume.data[1].itemStyle.color).toBe(colors.down);
    expect(isUpBar({ open: 105, close: 102 })).toBe(false);

    const markYs = (candle.markLine?.data || []).map((row) => row.yAxis).sort((a, b) => a - b);
    expect(markYs).toEqual([90, 95, 110]);
  });

  it('places BOLL on an independent subplot (not the main price panel)', () => {
    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible: {
        ma: true,
        boll: true,
        volume: false,
        macd: false,
        rsi: false,
        kdj: false,
        cci: false,
        bias: false,
        supportResistance: false,
      },
    });

    expect((option.grid as unknown[]).length).toBe(2);

    const series = option.series as Array<{
      name?: string;
      type?: string;
      xAxisIndex?: number;
      yAxisIndex?: number;
      lineStyle?: { color?: string; type?: string; width?: number };
    }>;
    const candle = series.find((item) => item.type === 'candlestick');
    expect(candle?.xAxisIndex).toBe(0);
    expect(candle?.yAxisIndex).toBe(0);

    const bollUpper = series.find((item) => item.name === 'BOLL.U');
    const bollMid = series.find((item) => item.name === 'BOLL.M');
    const bollLower = series.find((item) => item.name === 'BOLL.L');
    expect(bollUpper).toMatchObject({ xAxisIndex: 1, yAxisIndex: 1 });
    expect(bollMid).toMatchObject({ xAxisIndex: 1, yAxisIndex: 1 });
    expect(bollLower).toMatchObject({ xAxisIndex: 1, yAxisIndex: 1 });
    expect(series.filter((item) => item.type === 'candlestick')).toHaveLength(2);
    expect(series.find((item) => item.name === 'K · BOLL')).toMatchObject({
      type: 'candlestick',
      xAxisIndex: 1,
      yAxisIndex: 1,
    });
    expect(bollUpper?.lineStyle).toMatchObject({ color: colors.bollUpper, type: 'solid' });
    expect(bollMid?.lineStyle).toMatchObject({ color: colors.bollMid, type: 'solid' });
    expect(bollLower?.lineStyle).toMatchObject({ color: colors.bollLower, type: 'solid' });

    const titles = option.title as Array<{ text?: string }>;
    expect(titles.map((title) => title.text)).toEqual(['BOLL (20, 2)']);

    const priceSeriesNames = series
      .filter((item) => item.xAxisIndex === 0)
      .map((item) => item.name);
    expect(priceSeriesNames).not.toContain('BOLL.U');
    expect(priceSeriesNames).not.toContain('BOLL.M');
    expect(priceSeriesNames).not.toContain('BOLL.L');
  });

  it('keeps volume, BOLL and MACD on three independent panels', () => {
    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible: {
        ma: false,
        boll: true,
        volume: true,
        macd: true,
        rsi: false,
        kdj: false,
        cci: false,
        bias: false,
        supportResistance: false,
      },
    });

    expect((option.grid as unknown[]).length).toBe(4);
    const series = option.series as Array<{ name?: string; xAxisIndex?: number; yAxisIndex?: number }>;
    expect(series.find((item) => item.name === 'Vol')).toMatchObject({ xAxisIndex: 1, yAxisIndex: 1 });
    expect(series.find((item) => item.name === 'BOLL.M')).toMatchObject({ xAxisIndex: 2, yAxisIndex: 2 });
    expect(series.find((item) => item.name === 'DIF')).toMatchObject({ xAxisIndex: 3, yAxisIndex: 3 });

    const yAxis = option.yAxis as Array<{ gridIndex: number }>;
    expect(yAxis.map((axis) => axis.gridIndex)).toEqual([0, 1, 2, 3]);

    const titles = option.title as Array<{ text?: string }>;
    expect(titles.map((title) => title.text)).toEqual([
      'Vol',
      'BOLL (20, 2)',
      'MACD (12, 26, 9)',
    ]);
  });

  it('gives each oscillator its own panel indexes and grows chart height', () => {
    const visibleAll = {
      ma: false,
      boll: true,
      volume: false,
      macd: true,
      rsi: true,
      kdj: true,
      cci: true,
      bias: true,
      supportResistance: false,
    };
    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible: visibleAll,
    });

    const series = option.series as Array<{ name?: string; xAxisIndex?: number; yAxisIndex?: number }>;
    const bollAxis = series.find((item) => item.name === 'BOLL.M')?.xAxisIndex;
    const macdAxis = series.find((item) => item.name === 'DIF')?.xAxisIndex;
    const rsiAxis = series.find((item) => item.name === 'RSI6')?.xAxisIndex;
    const kdjAxis = series.find((item) => item.name === 'KDJ.K')?.xAxisIndex;
    const cciAxis = series.find((item) => item.name === 'CCI')?.xAxisIndex;
    const biasAxis = series.find((item) => item.name === 'BIAS5')?.xAxisIndex;

    expect([bollAxis, macdAxis, rsiAxis, kdjAxis, cciAxis, biasAxis]).toEqual([1, 2, 3, 4, 5, 6]);
    expect(new Set([bollAxis, macdAxis, rsiAxis, kdjAxis, cciAxis, biasAxis]).size).toBe(6);
    expect((option.grid as unknown[]).length).toBe(7);
    const titles = option.title as Array<{ text?: string }>;
    expect(titles.map((title) => title.text)).toEqual([
      'BOLL (20, 2)',
      'MACD (12, 26, 9)',
      'RSI (6, 12, 24)',
      'KDJ (9, 3, 3)',
      'CCI (14)',
      'BIAS (5, 10, 20)',
    ]);

    const heightAll = estimateTechnicalChartHeight(visibleAll);
    const heightFewer = estimateTechnicalChartHeight({
      ...visibleAll,
      kdj: false,
      cci: false,
      bias: false,
    });
    expect(heightAll).toBeGreaterThan(heightFewer);
  });

  it('maps MACD/RSI/KDJ/CCI/BIAS with independent axis indexes and reference lines', () => {
    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible: {
        ma: false,
        boll: false,
        volume: false,
        macd: true,
        rsi: true,
        kdj: true,
        cci: true,
        bias: true,
        supportResistance: false,
      },
    });

    const series = option.series as Array<Record<string, unknown>>;
    const macdBar = series.find((item) => item.name === 'MACD') as {
      type: string;
      xAxisIndex: number;
      data: Array<{ value: number | null }>;
      markLine: { data: Array<{ yAxis: number }> };
    };
    expect(macdBar.type).toBe('bar');
    expect(macdBar.xAxisIndex).toBe(1);
    expect(macdBar.data[0].value).toBeNull();
    expect(macdBar.data[1].value).toBe(0.8);
    expect(macdBar.markLine.data.some((row) => row.yAxis === 0)).toBe(true);

    const rsi6 = series.find((item) => item.name === 'RSI6') as {
      xAxisIndex: number;
      data: Array<number | null>;
      markLine: { data: Array<{ yAxis: number }> };
    };
    expect(rsi6.xAxisIndex).toBe(2);
    expect(rsi6.data).toEqual([null, 62]);
    expect(rsi6.markLine.data.map((row) => row.yAxis).sort()).toEqual([30, 70]);

    const k = series.find((item) => item.name === 'KDJ.K') as {
      xAxisIndex: number;
      markLine: { data: Array<{ yAxis: number }> };
    };
    expect(k.xAxisIndex).toBe(3);
    expect(k.markLine.data.map((row) => row.yAxis).sort()).toEqual([20, 80]);

    const cci = series.find((item) => item.name === 'CCI') as {
      xAxisIndex: number;
      markLine: { data: Array<{ yAxis: number }> };
    };
    expect(cci.xAxisIndex).toBe(4);
    expect(cci.markLine.data.map((row) => row.yAxis).sort((a, b) => a - b)).toEqual([-100, 0, 100]);

    const bias5 = series.find((item) => item.name === 'BIAS5') as {
      xAxisIndex: number;
      data: Array<number | null>;
    };
    expect(bias5.xAxisIndex).toBe(5);
    expect(bias5.data).toEqual([null, 1.5]);

    const yAxis = option.yAxis as Array<{ min?: number; max?: number; gridIndex: number }>;
    const rsiAxis = yAxis.find((axis) => axis.gridIndex === 2);
    expect(rsiAxis).toMatchObject({ min: 0, max: 100 });
  });

  it('keeps later panel indexes correct after closing volume', () => {
    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible: {
        ma: false,
        boll: false,
        volume: false,
        macd: true,
        rsi: true,
        kdj: false,
        cci: false,
        bias: false,
        supportResistance: false,
      },
    });
    const series = option.series as Array<{ name?: string; xAxisIndex?: number }>;
    expect(series.find((item) => item.name === 'DIF')?.xAxisIndex).toBe(1);
    expect(series.find((item) => item.name === 'RSI6')?.xAxisIndex).toBe(2);
    expect((option.dataZoom as Array<{ xAxisIndex: number[] }>)[0].xAxisIndex).toEqual([0, 1, 2]);
  });

  it('supports enabling every indicator together', () => {
    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible: {
        ma: true,
        boll: true,
        volume: true,
        macd: true,
        rsi: true,
        kdj: true,
        cci: true,
        bias: true,
        supportResistance: true,
      },
    });
    const series = option.series as Array<{ type?: string }>;
    expect(series.some((item) => item.type === 'candlestick')).toBe(true);
    expect((option.grid as unknown[]).length).toBe(8);
  });

  it('handles empty items and all-null indicator columns', () => {
    const option = buildTechnicalChartOption({
      response: makeResponse({
        items: [{
          date: '2026-07-11',
          open: 1,
          high: 1,
          low: 1,
          close: 1,
          macdDif: null,
          macdDea: null,
          macdBar: null,
          rsi6: null,
          rsi12: null,
          rsi24: null,
        }],
        summary: {
          latestClose: 1,
          latestChangePercent: null,
          latestVolumeStatus: null,
          volumeRatio: null,
          supportLevels: [],
          resistanceLevels: [],
          recentHigh: null,
          recentLow: null,
        },
      }),
      colors,
      visible: {
        ...TECHNICAL_CHART_PC_DEFAULT_PANELS,
        volume: false,
        macd: true,
        rsi: true,
        supportResistance: false,
      },
    });
    const series = option.series as Array<{ name?: string; data?: unknown[] }>;
    const dif = series.find((item) => item.name === 'DIF') as { data: Array<number | null> };
    expect(dif.data).toEqual([null]);
  });

  it('uses compact layout heights and bottom tooltip positioning', () => {
    const visible = {
      ...TECHNICAL_CHART_PC_DEFAULT_PANELS,
      rsi: false,
    };
    const compactHeight = estimateTechnicalChartHeight(visible, { compact: true });
    const desktopHeight = estimateTechnicalChartHeight(visible, { compact: false });
    expect(compactHeight).toBeLessThan(desktopHeight);

    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible,
      layout: { compact: true },
    });
    expect(typeof option.tooltip).toBe('object');
    expect((option.tooltip as { position?: unknown }).position).toEqual(expect.any(Function));
  });

  it('omits axisPointer on the sole labeled xAxis (showLabel=true)', () => {
    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible: {
        ma: true,
        boll: false,
        volume: false,
        macd: false,
        rsi: false,
        kdj: false,
        cci: false,
        bias: false,
        supportResistance: false,
      },
    });
    const xAxis = option.xAxis as Array<Record<string, unknown>>;
    expect(xAxis).toHaveLength(1);
    expect(Object.prototype.hasOwnProperty.call(xAxis[0], 'axisPointer')).toBe(false);
  });

  it('hides axisPointer labels on unlabeled axes and omits axisPointer on the last labeled axis', () => {
    const option = buildTechnicalChartOption({
      response: makeResponse(),
      colors,
      visible: {
        ma: false,
        boll: false,
        volume: true,
        macd: true,
        rsi: true,
        kdj: false,
        cci: false,
        bias: false,
        supportResistance: false,
      },
    });
    type AxisWithPointer = {
      axisPointer?: { label?: { show?: boolean } };
    };
    const xAxis = option.xAxis as AxisWithPointer[];
    expect(xAxis).toHaveLength(4);

    // Price + volume + macd: showLabel=false → hide axisPointer labels
    for (let i = 0; i < xAxis.length - 1; i += 1) {
      expect(xAxis[i].axisPointer?.label?.show).toBe(false);
    }
    // Last subplot (rsi): showLabel=true → omit axisPointer entirely
    expect(Object.prototype.hasOwnProperty.call(xAxis[xAxis.length - 1], 'axisPointer')).toBe(false);
  });
});
