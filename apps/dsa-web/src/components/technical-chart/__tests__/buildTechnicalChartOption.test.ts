import { describe, expect, it } from 'vitest';
import type { TechnicalChartResponse } from '../../../api/technicalChart';
import {
  buildPanelIndexMap,
  buildTechnicalChartOption,
  enforceSingleSubplot,
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
    expect(parseVisiblePanels(null).kdj).toBe(false);
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
    expect(next.kdj).toBe(true);
    expect(next.macd).toBe(true);
  });

  it('enforces a single subplot panel', () => {
    const next = enforceSingleSubplot(
      {
        ...TECHNICAL_CHART_PC_DEFAULT_PANELS,
        macd: true,
        rsi: true,
        kdj: false,
      },
      'rsi',
    );
    expect(next.rsi).toBe(true);
    expect(next.macd).toBe(false);
  });
});

describe('buildPanelIndexMap', () => {
  it('reindexes later panels when a middle panel is closed', () => {
    const withVolume = buildPanelIndexMap({
      ...TECHNICAL_CHART_PC_DEFAULT_PANELS,
      volume: true,
      macd: true,
      rsi: true,
      kdj: false,
    });
    expect(withVolume).toMatchObject({ price: 0, volume: 1, macd: 2, rsi: 3, kdj: undefined });

    const withoutVolume = buildPanelIndexMap({
      ...TECHNICAL_CHART_PC_DEFAULT_PANELS,
      volume: false,
      macd: true,
      rsi: true,
      kdj: false,
    });
    expect(withoutVolume).toMatchObject({ price: 0, volume: undefined, macd: 1, rsi: 2 });
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
    expect((option.grid as unknown[]).length).toBe(7);
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
});
