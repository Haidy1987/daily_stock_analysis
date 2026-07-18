import apiClient from './index';
import { toCamelCase } from './utils';

export const TECHNICAL_CHART_INDICATOR_GROUPS = [
  'ma',
  'volume',
  'macd',
  'rsi',
  'boll',
  'kdj',
  'cci',
  'bias',
  'support_resistance',
] as const;

export type TechnicalChartIndicatorGroup = (typeof TECHNICAL_CHART_INDICATOR_GROUPS)[number];

/** Default to the complete technical-chart workspace on every viewport. */
export const TECHNICAL_CHART_DEFAULT_INDICATORS = [
  'ma',
  'boll',
  'volume',
  'macd',
  'rsi',
  'kdj',
  'cci',
  'bias',
  'support_resistance',
].join(',');

export const TECHNICAL_CHART_MOBILE_DEFAULT_INDICATORS = TECHNICAL_CHART_DEFAULT_INDICATORS;

export const TECHNICAL_CHART_ALLOWED_DAYS = [60, 120, 250] as const;
export type TechnicalChartDays = (typeof TECHNICAL_CHART_ALLOWED_DAYS)[number];
export const TECHNICAL_CHART_DEFAULT_DAYS: TechnicalChartDays = 60;

export const TECHNICAL_CHART_ALLOWED_PERIODS = ['daily', 'weekly', 'monthly'] as const;
export type TechnicalChartPeriod = (typeof TECHNICAL_CHART_ALLOWED_PERIODS)[number];
export const TECHNICAL_CHART_DEFAULT_PERIOD: TechnicalChartPeriod = 'daily';

export interface ChartLevel {
  price: number;
  label: string;
  source: string;
  date?: string | null;
}

export interface ChartExtreme {
  price: number;
  date: string;
}

export interface TechnicalChartItem {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
  amount?: number | null;
  changePercent?: number | null;
  ma5?: number | null;
  ma10?: number | null;
  ma20?: number | null;
  ma30?: number | null;
  ma60?: number | null;
  ma90?: number | null;
  ma120?: number | null;
  ma250?: number | null;
  volumeRatio?: number | null;
  volumeStatus?: string | null;
  macdDif?: number | null;
  macdDea?: number | null;
  macdBar?: number | null;
  rsi6?: number | null;
  rsi12?: number | null;
  rsi24?: number | null;
  bollUpper?: number | null;
  bollMid?: number | null;
  bollLower?: number | null;
  bollBandwidth?: number | null;
  bollPosition?: number | null;
  kdjK?: number | null;
  kdjD?: number | null;
  kdjJ?: number | null;
  cci?: number | null;
  bias5?: number | null;
  bias10?: number | null;
  bias20?: number | null;
}

export interface TechnicalChartSummary {
  latestClose?: number | null;
  latestChangePercent?: number | null;
  latestVolumeStatus?: string | null;
  volumeRatio?: number | null;
  supportLevels: ChartLevel[];
  resistanceLevels: ChartLevel[];
  recentHigh?: ChartExtreme | null;
  recentLow?: ChartExtreme | null;
}

export type TechnicalChartDataStatus = 'available' | 'partial' | 'empty' | 'source_unavailable';

export interface TechnicalChartResponse {
  stockCode: string;
  stockName?: string | null;
  period: string;
  rangeDays: number;
  calculationVersion: string;
  dataStatus: TechnicalChartDataStatus | string;
  dataSource?: string | null;
  updatedAt?: string | null;
  items: TechnicalChartItem[];
  summary: TechnicalChartSummary;
  warnings: string[];
}

export interface GetTechnicalChartParams {
  stockCode: string;
  period?: TechnicalChartPeriod;
  days?: TechnicalChartDays | number;
  indicators?: string;
  signal?: AbortSignal;
}

export function parseTechnicalChartDays(raw: string | null | undefined): TechnicalChartDays {
  const value = Number(raw);
  if (TECHNICAL_CHART_ALLOWED_DAYS.includes(value as TechnicalChartDays)) {
    return value as TechnicalChartDays;
  }
  return TECHNICAL_CHART_DEFAULT_DAYS;
}

export function parseTechnicalChartIndicators(raw: string | null | undefined): string {
  if (!raw || !raw.trim()) {
    return TECHNICAL_CHART_DEFAULT_INDICATORS;
  }
  const allowed = new Set<string>(TECHNICAL_CHART_INDICATOR_GROUPS);
  const parts = raw
    .split(',')
    .map((part) => part.trim().toLowerCase())
    .filter((part) => allowed.has(part));
  if (parts.length === 0) {
    return TECHNICAL_CHART_DEFAULT_INDICATORS;
  }
  // Deduplicate while preserving order.
  return Array.from(new Set(parts)).join(',');
}

export function parseTechnicalChartPeriod(raw?: string | null): TechnicalChartPeriod {
  const value = (raw || '').trim().toLowerCase();
  if (TECHNICAL_CHART_ALLOWED_PERIODS.includes(value as TechnicalChartPeriod)) {
    return value as TechnicalChartPeriod;
  }
  return TECHNICAL_CHART_DEFAULT_PERIOD;
}

/** Build an in-app href; only pass canonical stock code for cross-page entry. */
export function buildTechnicalChartHref(options: {
  stock: string;
  period?: TechnicalChartPeriod;
  days?: TechnicalChartDays | number;
  indicators?: string;
}): string {
  const params = new URLSearchParams();
  const stock = options.stock.trim();
  if (stock) {
    params.set('stock', stock);
  }
  if (options.period) {
    params.set('period', parseTechnicalChartPeriod(options.period));
  }
  if (options.days != null) {
    params.set('days', String(parseTechnicalChartDays(String(options.days))));
  }
  if (options.indicators) {
    params.set('indicators', parseTechnicalChartIndicators(options.indicators));
  }
  const query = params.toString();
  return query ? `/technical-chart?${query}` : '/technical-chart';
}

export const technicalChartApi = {
  get: async (params: GetTechnicalChartParams): Promise<TechnicalChartResponse> => {
    const {
      stockCode,
      period = TECHNICAL_CHART_DEFAULT_PERIOD,
      days = TECHNICAL_CHART_DEFAULT_DAYS,
      indicators,
      signal,
    } = params;
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/stocks/${encodeURIComponent(stockCode)}/technical-chart`,
      {
        params: {
          period: parseTechnicalChartPeriod(period),
          days,
          indicators: indicators || TECHNICAL_CHART_DEFAULT_INDICATORS,
        },
        signal,
      },
    );
    return toCamelCase<TechnicalChartResponse>(response.data);
  },
};
