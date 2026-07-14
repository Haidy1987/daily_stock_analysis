import type { EChartsOption, SeriesOption } from 'echarts';
import type {
  ChartExtreme,
  ChartLevel,
  TechnicalChartItem,
  TechnicalChartResponse,
} from '../../api/technicalChart';
import type { TechnicalChartThemeColors } from './themeColors';

export type TechnicalChartVisiblePanels = {
  ma: boolean;
  boll: boolean;
  volume: boolean;
  macd: boolean;
  rsi: boolean;
  kdj: boolean;
  cci: boolean;
  bias: boolean;
  supportResistance: boolean;
};

export type SubPanelId = 'volume' | 'macd' | 'rsi' | 'kdj' | 'cci' | 'bias';

export const SUB_PANEL_ORDER: SubPanelId[] = ['volume', 'macd', 'rsi', 'kdj', 'cci', 'bias'];

export const TECHNICAL_CHART_PC_DEFAULT_PANELS: TechnicalChartVisiblePanels = {
  ma: true,
  boll: true,
  volume: true,
  macd: true,
  rsi: true,
  kdj: false,
  cci: false,
  bias: false,
  supportResistance: true,
};

export const TECHNICAL_CHART_MOBILE_DEFAULT_PANELS: TechnicalChartVisiblePanels = {
  ma: true,
  boll: true,
  volume: true,
  macd: true,
  rsi: false,
  kdj: false,
  cci: false,
  bias: false,
  supportResistance: true,
};

export const SUBPLOT_TOGGLE_KEYS: Array<keyof TechnicalChartVisiblePanels> = [
  'macd',
  'rsi',
  'kdj',
  'cci',
  'bias',
];

const PANEL_TOKEN_BY_KEY: Array<{ key: keyof TechnicalChartVisiblePanels; token: string }> = [
  { key: 'ma', token: 'ma' },
  { key: 'boll', token: 'boll' },
  { key: 'volume', token: 'volume' },
  { key: 'macd', token: 'macd' },
  { key: 'rsi', token: 'rsi' },
  { key: 'kdj', token: 'kdj' },
  { key: 'cci', token: 'cci' },
  { key: 'bias', token: 'bias' },
  { key: 'supportResistance', token: 'support_resistance' },
];

export type BuildTechnicalChartOptionInput = {
  response: TechnicalChartResponse;
  colors: TechnicalChartThemeColors;
  visible?: Partial<TechnicalChartVisiblePanels>;
  labels?: Partial<Record<string, string>>;
  layout?: {
    compact?: boolean;
  };
};

const PRICE_GRID_HEIGHT = 420;
const PRICE_GRID_HEIGHT_COMPACT = 300;
const SUB_GRID_HEIGHT = 150;
const SUB_GRID_HEIGHT_COMPACT = 110;
const GRID_GAP = 18;
const GRID_GAP_COMPACT = 12;
const GRID_TOP = 40;
const GRID_TOP_COMPACT = 32;
const SLIDER_RESERVE = 48;
const SLIDER_RESERVE_COMPACT = 40;

/** ECharts candlestick value order: [open, close, low, high]. */
export function toCandlestickValue(item: Pick<TechnicalChartItem, 'open' | 'close' | 'low' | 'high'>): [
  number,
  number,
  number,
  number,
] {
  return [item.open, item.close, item.low, item.high];
}

export function isUpBar(item: Pick<TechnicalChartItem, 'open' | 'close'>): boolean {
  return item.close >= item.open;
}

export function nullableSeriesValue(value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) {
    return null;
  }
  return value;
}

export function formatTooltipValue(
  value: number | null | undefined,
  digits = 2,
): string {
  if (value == null || Number.isNaN(value)) {
    return '--';
  }
  return value.toFixed(digits);
}

export function parseVisiblePanels(
  indicatorsCsv: string | undefined | null,
  defaults: TechnicalChartVisiblePanels = TECHNICAL_CHART_PC_DEFAULT_PANELS,
): TechnicalChartVisiblePanels {
  const tokens = new Set(
    (indicatorsCsv || '')
      .split(',')
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean),
  );
  if (tokens.size === 0) {
    return { ...defaults };
  }
  return {
    ma: tokens.has('ma'),
    boll: tokens.has('boll'),
    volume: tokens.has('volume'),
    macd: tokens.has('macd'),
    rsi: tokens.has('rsi'),
    kdj: tokens.has('kdj'),
    cci: tokens.has('cci'),
    bias: tokens.has('bias'),
    supportResistance: tokens.has('support_resistance'),
  };
}

export function panelsToIndicatorsCsv(visible: TechnicalChartVisiblePanels): string {
  return PANEL_TOKEN_BY_KEY
    .filter(({ key }) => visible[key])
    .map(({ token }) => token)
    .join(',');
}

export function togglePanel(
  visible: TechnicalChartVisiblePanels,
  key: keyof TechnicalChartVisiblePanels,
): TechnicalChartVisiblePanels {
  return { ...visible, [key]: !visible[key] };
}

/** On compact screens, keep at most one of MACD/RSI/KDJ/CCI/BIAS enabled. */
export function enforceSingleSubplot(
  visible: TechnicalChartVisiblePanels,
  enabledKey?: keyof TechnicalChartVisiblePanels,
): TechnicalChartVisiblePanels {
  const next = { ...visible };
  if (enabledKey && SUBPLOT_TOGGLE_KEYS.includes(enabledKey) && next[enabledKey]) {
    for (const key of SUBPLOT_TOGGLE_KEYS) {
      if (key !== enabledKey) {
        next[key] = false;
      }
    }
    return next;
  }
  const active = SUBPLOT_TOGGLE_KEYS.filter((key) => next[key]);
  if (active.length <= 1) {
    return next;
  }
  const keep = active[0];
  for (const key of SUBPLOT_TOGGLE_KEYS) {
    next[key] = key === keep;
  }
  return next;
}

export function resolveActiveSubPanels(visible: TechnicalChartVisiblePanels): SubPanelId[] {
  return SUB_PANEL_ORDER.filter((id) => visible[id]);
}

export function buildPanelIndexMap(visible: TechnicalChartVisiblePanels): Record<'price' | SubPanelId, number | undefined> {
  const map: Record<'price' | SubPanelId, number | undefined> = {
    price: 0,
    volume: undefined,
    macd: undefined,
    rsi: undefined,
    kdj: undefined,
    cci: undefined,
    bias: undefined,
  };
  let index = 1;
  for (const id of resolveActiveSubPanels(visible)) {
    map[id] = index;
    index += 1;
  }
  return map;
}

export function estimateTechnicalChartHeight(
  visible: TechnicalChartVisiblePanels,
  options?: { compact?: boolean },
): number {
  const compact = Boolean(options?.compact);
  const priceH = compact ? PRICE_GRID_HEIGHT_COMPACT : PRICE_GRID_HEIGHT;
  const subH = compact ? SUB_GRID_HEIGHT_COMPACT : SUB_GRID_HEIGHT;
  const gap = compact ? GRID_GAP_COMPACT : GRID_GAP;
  const top = compact ? GRID_TOP_COMPACT : GRID_TOP;
  const slider = compact ? SLIDER_RESERVE_COMPACT : SLIDER_RESERVE;
  const subCount = resolveActiveSubPanels(visible).length;
  return top + priceH + subCount * (subH + gap) + slider;
}

function formatLevelLabel(level: ChartLevel, prefix: string): string {
  const base = level.label?.trim() || prefix;
  return `${base} ${level.price.toFixed(2)}`;
}

function dedupeLevels(levels: ChartLevel[], toleranceRatio = 0.005): ChartLevel[] {
  const sorted = [...levels]
    .filter((level) => Number.isFinite(level.price))
    .sort((a, b) => a.price - b.price);
  const result: ChartLevel[] = [];
  for (const level of sorted) {
    const last = result[result.length - 1];
    if (last && Math.abs(level.price - last.price) / Math.max(Math.abs(last.price), 1e-9) <= toleranceRatio) {
      continue;
    }
    result.push(level);
  }
  return result;
}

function findCategoryIndex(categories: string[], date: string | undefined | null): number {
  if (!date) return -1;
  return categories.indexOf(date);
}

function buildExtremeMarkPoint(
  extreme: ChartExtreme | null | undefined,
  categories: string[],
  name: string,
  color: string,
  symbolRotate: number,
) {
  if (!extreme || !Number.isFinite(extreme.price)) {
    return null;
  }
  const index = findCategoryIndex(categories, extreme.date);
  if (index < 0) {
    return null;
  }
  return {
    name,
    coord: [index, extreme.price] as [number, number],
    value: extreme.price,
    itemStyle: { color },
    label: {
      formatter: `${name}\n${extreme.price.toFixed(2)}\n${extreme.date}`,
      color,
      fontSize: 10,
    },
    symbol: 'pin',
    symbolSize: 42,
    symbolRotate,
  };
}

function buildCategoryAxis(
  categories: string[],
  gridIndex: number,
  colors: TechnicalChartThemeColors,
  showLabel: boolean,
) {
  return {
    type: 'category' as const,
    gridIndex,
    data: categories,
    boundaryGap: true,
    axisLine: { lineStyle: { color: colors.border } },
    axisLabel: showLabel
      ? { color: colors.muted, fontSize: 10, hideOverlap: true }
      : { show: false, color: colors.muted },
    axisTick: { show: false },
    splitLine: { show: false },
    min: 'dataMin' as const,
    max: 'dataMax' as const,
    axisPointer: showLabel ? undefined : { label: { show: false } },
  };
}

export function buildTechnicalChartOption(input: BuildTechnicalChartOptionInput): EChartsOption {
  const { response, colors } = input;
  const compact = Boolean(input.layout?.compact);
  const priceH = compact ? PRICE_GRID_HEIGHT_COMPACT : PRICE_GRID_HEIGHT;
  const subH = compact ? SUB_GRID_HEIGHT_COMPACT : SUB_GRID_HEIGHT;
  const gap = compact ? GRID_GAP_COMPACT : GRID_GAP;
  const top = compact ? GRID_TOP_COMPACT : GRID_TOP;
  const visible: TechnicalChartVisiblePanels = {
    ...TECHNICAL_CHART_PC_DEFAULT_PANELS,
    ...input.visible,
  };
  const labels = {
    candle: 'K',
    volume: 'Vol',
    ma5: 'MA5',
    ma10: 'MA10',
    ma20: 'MA20',
    bollUpper: 'BOLL.U',
    bollMid: 'BOLL.M',
    bollLower: 'BOLL.L',
    support: 'S',
    resistance: 'R',
    recentHigh: 'High',
    recentLow: 'Low',
    macdDif: 'DIF',
    macdDea: 'DEA',
    macdBar: 'MACD',
    rsi6: 'RSI6',
    rsi12: 'RSI12',
    rsi24: 'RSI24',
    kdjK: 'KDJ.K',
    kdjD: 'KDJ.D',
    kdjJ: 'KDJ.J',
    cci: 'CCI',
    bias5: 'BIAS5',
    bias10: 'BIAS10',
    bias20: 'BIAS20',
    open: 'O',
    high: 'H',
    low: 'L',
    close: 'C',
    bandwidth: 'BW',
    position: 'Pos',
    ratio: 'ratio',
    ...input.labels,
  };

  const items = response.items || [];
  const categories = items.map((item) => item.date);
  const panelIndex = buildPanelIndexMap(visible);
  const activeSubs = resolveActiveSubPanels(visible);
  const axisCount = 1 + activeSubs.length;
  const xAxisIndexes = Array.from({ length: axisCount }, (_, index) => index);

  const supportLevels = dedupeLevels(response.summary?.supportLevels || []);
  const resistanceLevels = dedupeLevels(response.summary?.resistanceLevels || []);
  const markLineData: Array<Record<string, unknown>> = [];
  if (visible.supportResistance) {
    supportLevels.forEach((level, index) => {
      markLineData.push({
        name: formatLevelLabel(level, labels.support),
        yAxis: level.price,
        lineStyle: { color: colors.support, type: 'dashed', width: 1 },
        label: {
          formatter: formatLevelLabel(level, labels.support),
          position: index % 2 === 0 ? 'insideStartTop' : 'insideEndTop',
          color: colors.support,
          fontSize: 10,
        },
      });
    });
    resistanceLevels.forEach((level, index) => {
      markLineData.push({
        name: formatLevelLabel(level, labels.resistance),
        yAxis: level.price,
        lineStyle: { color: colors.resistance, type: 'dashed', width: 1 },
        label: {
          formatter: formatLevelLabel(level, labels.resistance),
          position: index % 2 === 0 ? 'insideEndBottom' : 'insideStartBottom',
          color: colors.resistance,
          fontSize: 10,
        },
      });
    });
  }

  const markPoints = (visible.supportResistance
    ? [
        buildExtremeMarkPoint(response.summary?.recentHigh, categories, labels.recentHigh, colors.markHigh, 0),
        buildExtremeMarkPoint(response.summary?.recentLow, categories, labels.recentLow, colors.markLow, 180),
      ]
    : []).filter((point): point is NonNullable<typeof point> => point != null);

  const series: SeriesOption[] = [
    {
      id: `candle-${response.stockCode}`,
      name: labels.candle,
      type: 'candlestick',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: items.map((item) => toCandlestickValue(item)),
      itemStyle: {
        color: colors.up,
        color0: colors.down,
        borderColor: colors.up,
        borderColor0: colors.down,
      },
      markLine: markLineData.length
        ? { symbol: 'none', silent: true, data: markLineData as never, animation: false }
        : undefined,
      markPoint: markPoints.length
        ? { data: markPoints as never, animation: false }
        : undefined,
    },
  ];

  if (visible.ma) {
    series.push(
      {
        id: `ma5-${response.stockCode}`,
        name: labels.ma5,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: items.map((item) => nullableSeriesValue(item.ma5)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.5, color: colors.ma5 },
        itemStyle: { color: colors.ma5 },
      },
      {
        id: `ma10-${response.stockCode}`,
        name: labels.ma10,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: items.map((item) => nullableSeriesValue(item.ma10)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.5, color: colors.ma10 },
        itemStyle: { color: colors.ma10 },
      },
      {
        id: `ma20-${response.stockCode}`,
        name: labels.ma20,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: items.map((item) => nullableSeriesValue(item.ma20)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.5, color: colors.ma20 },
        itemStyle: { color: colors.ma20 },
      },
    );
  }

  if (visible.boll) {
    series.push(
      {
        id: `boll-upper-${response.stockCode}`,
        name: labels.bollUpper,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: items.map((item) => nullableSeriesValue(item.bollUpper)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1, color: colors.bollUpper, type: 'dotted' },
        itemStyle: { color: colors.bollUpper },
      },
      {
        id: `boll-mid-${response.stockCode}`,
        name: labels.bollMid,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: items.map((item) => nullableSeriesValue(item.bollMid)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1, color: colors.bollMid, type: 'dotted' },
        itemStyle: { color: colors.bollMid },
      },
      {
        id: `boll-lower-${response.stockCode}`,
        name: labels.bollLower,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: items.map((item) => nullableSeriesValue(item.bollLower)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1, color: colors.bollLower, type: 'dotted' },
        itemStyle: { color: colors.bollLower },
      },
    );
  }

  if (panelIndex.volume != null) {
    const axis = panelIndex.volume;
    series.push({
      id: `volume-${response.stockCode}`,
      name: labels.volume,
      type: 'bar',
      xAxisIndex: axis,
      yAxisIndex: axis,
      data: items.map((item) => ({
        value: nullableSeriesValue(item.volume),
        itemStyle: { color: isUpBar(item) ? colors.up : colors.down },
      })),
    });
  }

  if (panelIndex.macd != null) {
    const axis = panelIndex.macd;
    series.push(
      {
        id: `macd-bar-${response.stockCode}`,
        name: labels.macdBar,
        type: 'bar',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => {
          const value = nullableSeriesValue(item.macdBar);
          return {
            value,
            itemStyle: {
              color: value == null ? colors.muted : value >= 0 ? colors.up : colors.down,
            },
          };
        }),
        markLine: {
          symbol: 'none',
          silent: true,
          data: [{ yAxis: 0, lineStyle: { color: colors.border, type: 'solid', width: 1 } }],
        },
      },
      {
        id: `macd-dif-${response.stockCode}`,
        name: labels.macdDif,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.macdDif)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.4, color: colors.ma5 },
        itemStyle: { color: colors.ma5 },
      },
      {
        id: `macd-dea-${response.stockCode}`,
        name: labels.macdDea,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.macdDea)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.4, color: colors.ma20 },
        itemStyle: { color: colors.ma20 },
      },
    );
  }

  if (panelIndex.rsi != null) {
    const axis = panelIndex.rsi;
    const refLine = (yAxis: number) => ({
      yAxis,
      lineStyle: { color: colors.border, type: 'dashed' as const, width: 1 },
      label: { show: false },
    });
    series.push(
      {
        id: `rsi6-${response.stockCode}`,
        name: labels.rsi6,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.rsi6)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.3, color: colors.ma5 },
        itemStyle: { color: colors.ma5 },
        markLine: {
          symbol: 'none',
          silent: true,
          data: [refLine(30), refLine(70)] as never,
        },
      },
      {
        id: `rsi12-${response.stockCode}`,
        name: labels.rsi12,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.rsi12)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.3, color: colors.ma10 },
        itemStyle: { color: colors.ma10 },
      },
      {
        id: `rsi24-${response.stockCode}`,
        name: labels.rsi24,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.rsi24)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.3, color: colors.ma20 },
        itemStyle: { color: colors.ma20 },
      },
    );
  }

  if (panelIndex.kdj != null) {
    const axis = panelIndex.kdj;
    const refLine = (yAxis: number) => ({
      yAxis,
      lineStyle: { color: colors.border, type: 'dashed' as const, width: 1 },
      label: { show: false },
    });
    series.push(
      {
        id: `kdj-k-${response.stockCode}`,
        name: labels.kdjK,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.kdjK)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.3, color: colors.ma5 },
        itemStyle: { color: colors.ma5 },
        markLine: {
          symbol: 'none',
          silent: true,
          data: [refLine(20), refLine(80)] as never,
        },
      },
      {
        id: `kdj-d-${response.stockCode}`,
        name: labels.kdjD,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.kdjD)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.3, color: colors.ma10 },
        itemStyle: { color: colors.ma10 },
      },
      {
        id: `kdj-j-${response.stockCode}`,
        name: labels.kdjJ,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.kdjJ)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.3, color: colors.ma20 },
        itemStyle: { color: colors.ma20 },
      },
    );
  }

  if (panelIndex.cci != null) {
    const axis = panelIndex.cci;
    const refLine = (yAxis: number, type: 'solid' | 'dashed' = 'dashed') => ({
      yAxis,
      lineStyle: { color: colors.border, type, width: 1 },
      label: { show: false },
    });
    series.push({
      id: `cci-${response.stockCode}`,
      name: labels.cci,
      type: 'line',
      xAxisIndex: axis,
      yAxisIndex: axis,
      data: items.map((item) => nullableSeriesValue(item.cci)),
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 1.4, color: colors.ma5 },
      itemStyle: { color: colors.ma5 },
      markLine: {
        symbol: 'none',
        silent: true,
        data: [refLine(0, 'solid'), refLine(100), refLine(-100)] as never,
      },
    });
  }

  if (panelIndex.bias != null) {
    const axis = panelIndex.bias;
    series.push(
      {
        id: `bias5-${response.stockCode}`,
        name: labels.bias5,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.bias5)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.3, color: colors.ma5 },
        itemStyle: { color: colors.ma5 },
        markLine: {
          symbol: 'none',
          silent: true,
          data: [{ yAxis: 0, lineStyle: { color: colors.border, type: 'solid', width: 1 }, label: { show: false } }],
        },
      },
      {
        id: `bias10-${response.stockCode}`,
        name: labels.bias10,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.bias10)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.3, color: colors.ma10 },
        itemStyle: { color: colors.ma10 },
      },
      {
        id: `bias20-${response.stockCode}`,
        name: labels.bias20,
        type: 'line',
        xAxisIndex: axis,
        yAxisIndex: axis,
        data: items.map((item) => nullableSeriesValue(item.bias20)),
        showSymbol: false,
        connectNulls: false,
        lineStyle: { width: 1.3, color: colors.ma20 },
        itemStyle: { color: colors.ma20 },
      },
    );
  }

  const grids = [
    {
      id: 'price',
      left: compact ? 44 : 52,
      right: 12,
      top,
      height: priceH,
    },
    ...activeSubs.map((id, offset) => ({
      id,
      left: compact ? 44 : 52,
      right: 12,
      top: top + priceH + gap + offset * (subH + gap),
      height: subH,
    })),
  ];

  const xAxis = [
    buildCategoryAxis(categories, 0, colors, activeSubs.length === 0),
    ...activeSubs.map((_id, offset) => buildCategoryAxis(
      categories,
      offset + 1,
      colors,
      offset === activeSubs.length - 1,
    )),
  ];

  const yAxis: Array<Record<string, unknown>> = [
    {
      gridIndex: 0,
      scale: true,
      axisLine: { show: false },
      axisLabel: { color: colors.muted, fontSize: 10 },
      splitLine: { lineStyle: { color: colors.border, opacity: 0.35 } },
    },
  ];

  for (const id of activeSubs) {
    const gridIndex = panelIndex[id];
    if (gridIndex == null) continue;
    if (id === 'rsi') {
      yAxis.push({
        gridIndex,
        min: 0,
        max: 100,
        scale: false,
        axisLine: { show: false },
        axisLabel: { color: colors.muted, fontSize: 10 },
        splitLine: { show: false },
      });
    } else if (id === 'kdj') {
      // Do not clip J outliers; keep scale free while reference lines remain visible.
      yAxis.push({
        gridIndex,
        scale: true,
        axisLine: { show: false },
        axisLabel: { color: colors.muted, fontSize: 10 },
        splitLine: { show: false },
      });
    } else {
      yAxis.push({
        gridIndex,
        scale: true,
        axisLine: { show: false },
        axisLabel: { color: colors.muted, fontSize: 10, showMaxLabel: false },
        splitLine: { show: false },
      });
    }
  }

  const legendData = [
    labels.candle,
    ...(visible.ma ? [labels.ma5, labels.ma10, labels.ma20] : []),
    ...(visible.boll ? [labels.bollUpper, labels.bollMid, labels.bollLower] : []),
    ...(visible.volume ? [labels.volume] : []),
    ...(visible.macd ? [labels.macdBar, labels.macdDif, labels.macdDea] : []),
    ...(visible.rsi ? [labels.rsi6, labels.rsi12, labels.rsi24] : []),
    ...(visible.kdj ? [labels.kdjK, labels.kdjD, labels.kdjJ] : []),
    ...(visible.cci ? [labels.cci] : []),
    ...(visible.bias ? [labels.bias5, labels.bias10, labels.bias20] : []),
  ];

  const zoomStart = items.length > 120 ? Math.max(0, 100 - (120 / items.length) * 100) : 0;

  return {
    animation: false,
    backgroundColor: colors.background,
    textStyle: { color: colors.text },
    legend: {
      top: 0,
      left: 0,
      type: 'scroll',
      textStyle: { color: colors.muted, fontSize: 11 },
      data: legendData,
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
      label: { backgroundColor: colors.border },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: colors.tooltipBg,
      borderColor: colors.border,
      textStyle: { color: colors.text, fontSize: compact ? 11 : 12 },
      confine: true,
      // Keep the bubble near the bottom on compact screens so candlesticks stay readable.
      position: compact
        ? (
          _point: number[],
          _params: unknown,
          _dom: unknown,
          _rect: unknown,
          size: { contentSize: number[]; viewSize: number[] },
        ) => {
          const [contentW, contentH] = size.contentSize;
          const [viewW, viewH] = size.viewSize;
          return [
            Math.max(8, (viewW - contentW) / 2),
            Math.max(8, viewH - contentH - 8),
          ];
        }
        : undefined,
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        if (!list.length) return '';
        const first = list[0] as { dataIndex?: number; axisValue?: string | number };
        const index = typeof first.dataIndex === 'number' ? first.dataIndex : -1;
        const item = index >= 0 ? items[index] : undefined;
        if (!item) return String(first.axisValue ?? '');

        const rows: string[] = [`<div><strong>${item.date}</strong></div>`];
        rows.push(
          `<div>${labels.open} ${formatTooltipValue(item.open)} / ${labels.close} ${formatTooltipValue(item.close)} / ${labels.low} ${formatTooltipValue(item.low)} / ${labels.high} ${formatTooltipValue(item.high)}</div>`,
        );
        if (visible.ma) {
          rows.push(
            `<div>${labels.ma5} ${formatTooltipValue(item.ma5)} · ${labels.ma10} ${formatTooltipValue(item.ma10)} · ${labels.ma20} ${formatTooltipValue(item.ma20)}</div>`,
          );
        }
        if (visible.boll && !compact) {
          rows.push(
            `<div>${labels.bollUpper} ${formatTooltipValue(item.bollUpper)} · ${labels.bollMid} ${formatTooltipValue(item.bollMid)} · ${labels.bollLower} ${formatTooltipValue(item.bollLower)}</div>`,
          );
          rows.push(
            `<div>${labels.bandwidth} ${formatTooltipValue(item.bollBandwidth, 4)} · ${labels.position} ${formatTooltipValue(item.bollPosition)}</div>`,
          );
        } else if (visible.boll) {
          rows.push(
            `<div>${labels.bollMid} ${formatTooltipValue(item.bollMid)} · ${labels.bandwidth} ${formatTooltipValue(item.bollBandwidth, 4)}</div>`,
          );
        }
        if (visible.volume) {
          rows.push(
            `<div>${labels.volume} ${formatTooltipValue(item.volume, 0)} · ${labels.ratio} ${formatTooltipValue(item.volumeRatio)} · ${item.volumeStatus ?? '--'}</div>`,
          );
        }
        if (visible.macd) {
          rows.push(
            `<div>${labels.macdDif} ${formatTooltipValue(item.macdDif)} · ${labels.macdDea} ${formatTooltipValue(item.macdDea)} · ${labels.macdBar} ${formatTooltipValue(item.macdBar)}</div>`,
          );
        }
        if (visible.rsi) {
          rows.push(
            `<div>${labels.rsi6} ${formatTooltipValue(item.rsi6)} · ${labels.rsi12} ${formatTooltipValue(item.rsi12)} · ${labels.rsi24} ${formatTooltipValue(item.rsi24)}</div>`,
          );
        }
        if (visible.kdj) {
          rows.push(
            `<div>${labels.kdjK} ${formatTooltipValue(item.kdjK)} · ${labels.kdjD} ${formatTooltipValue(item.kdjD)} · ${labels.kdjJ} ${formatTooltipValue(item.kdjJ)}</div>`,
          );
        }
        if (visible.cci) {
          rows.push(`<div>${labels.cci} ${formatTooltipValue(item.cci)}</div>`);
        }
        if (visible.bias) {
          rows.push(
            `<div>${labels.bias5} ${formatTooltipValue(item.bias5)} · ${labels.bias10} ${formatTooltipValue(item.bias10)} · ${labels.bias20} ${formatTooltipValue(item.bias20)}</div>`,
          );
        }
        return rows.join('');
      },
    },
    grid: grids,
    xAxis,
    yAxis: yAxis as never,
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: xAxisIndexes,
        start: zoomStart,
        end: 100,
      },
      {
        type: 'slider',
        xAxisIndex: xAxisIndexes,
        start: zoomStart,
        end: 100,
        height: 22,
        bottom: 8,
        borderColor: colors.border,
        textStyle: { color: colors.muted },
        fillerColor: 'rgba(56, 189, 248, 0.18)',
        handleStyle: { color: colors.ma5 },
      },
    ],
    series,
  };
}
