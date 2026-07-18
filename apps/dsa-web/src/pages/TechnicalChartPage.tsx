import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import {
  parseTechnicalChartDays,
  parseTechnicalChartIndicators,
  parseTechnicalChartPeriod,
  TECHNICAL_CHART_ALLOWED_DAYS,
  TECHNICAL_CHART_ALLOWED_PERIODS,
  TECHNICAL_CHART_DEFAULT_INDICATORS,
  TECHNICAL_CHART_MOBILE_DEFAULT_INDICATORS,
  technicalChartApi,
  type TechnicalChartDays,
  type TechnicalChartPeriod,
  type TechnicalChartResponse,
} from '../api/technicalChart';
import { historyApi } from '../api/history';
import { systemConfigApi } from '../api/systemConfig';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import {
  ApiErrorAlert,
  AppPage,
  Button,
  Card,
  EmptyState,
  InlineAlert,
  Loading,
  PageHeader,
} from '../components/common';
import { StockAutocomplete } from '../components/StockAutocomplete';
import {
  TechnicalPriceVolumeChart,
  TECHNICAL_CHART_MOBILE_DEFAULT_PANELS,
  TECHNICAL_CHART_PC_DEFAULT_PANELS,
  parseVisiblePanels,
  panelsToIndicatorsCsv,
  togglePanel,
  type TechnicalChartVisiblePanels,
} from '../components/technical-chart';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import { useIsCompactViewport } from '../hooks/useMediaQuery';
import type { StockBarItem } from '../types/analysis';
import type { UiTextKey } from '../i18n/uiText';

const CORE_TOGGLE_KEYS: Array<{ key: keyof TechnicalChartVisiblePanels; labelKey: UiTextKey }> = [
  { key: 'ma', labelKey: 'technicalChart.toggle.ma' },
  { key: 'volume', labelKey: 'technicalChart.toggle.volume' },
  { key: 'supportResistance', labelKey: 'technicalChart.toggle.supportResistance' },
];

const SUBPLOT_TOGGLE_ITEMS: Array<{ key: keyof TechnicalChartVisiblePanels; labelKey: UiTextKey }> = [
  { key: 'boll', labelKey: 'technicalChart.toggle.boll' },
  { key: 'macd', labelKey: 'technicalChart.toggle.macd' },
  { key: 'rsi', labelKey: 'technicalChart.toggle.rsi' },
  { key: 'kdj', labelKey: 'technicalChart.toggle.kdj' },
  { key: 'cci', labelKey: 'technicalChart.toggle.cci' },
  { key: 'bias', labelKey: 'technicalChart.toggle.bias' },
];

function isRequestCanceled(error: unknown): boolean {
  return axios.isCancel(error)
    || (axios.isAxiosError(error) && error.code === 'ERR_CANCELED');
}

function formatOptionalNumber(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) {
    return '—';
  }
  return value.toFixed(digits);
}

function formatSignedPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return '—';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

const TechnicalChartPage: React.FC = () => {
  const { t } = useUiLanguage();
  const isCompact = useIsCompactViewport();
  const [searchParams, setSearchParams] = useSearchParams();

  const stock = (searchParams.get('stock') || '').trim();
  const period = parseTechnicalChartPeriod(searchParams.get('period'));
  const days = parseTechnicalChartDays(searchParams.get('days'));
  const indicatorsRaw = searchParams.get('indicators');
  const defaultPanels = isCompact
    ? TECHNICAL_CHART_MOBILE_DEFAULT_PANELS
    : TECHNICAL_CHART_PC_DEFAULT_PANELS;
  const defaultIndicatorsCsv = isCompact
    ? TECHNICAL_CHART_MOBILE_DEFAULT_INDICATORS
    : TECHNICAL_CHART_DEFAULT_INDICATORS;
  const indicators = indicatorsRaw == null
    ? defaultIndicatorsCsv
    : parseTechnicalChartIndicators(indicatorsRaw);

  const [searchInput, setSearchInput] = useState(stock);
  const [chart, setChart] = useState<TechnicalChartResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const [recentStocks, setRecentStocks] = useState<StockBarItem[]>([]);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const requestIdRef = useRef(0);

  useEffect(() => {
    document.title = t('technicalChart.pageTitleDocument');
  }, [t]);

  // Normalize illegal URL params; when indicators are missing, seed compact/PC defaults once.
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    let changed = false;

    if (searchParams.get('period') !== period) {
      next.set('period', period);
      changed = true;
    }
    if (searchParams.get('days') !== String(days)) {
      next.set('days', String(days));
      changed = true;
    }
    if (indicatorsRaw === null) {
      next.set('indicators', defaultIndicatorsCsv);
      changed = true;
    } else {
      const normalized = parseTechnicalChartIndicators(indicatorsRaw);
      if (normalized !== indicatorsRaw) {
        next.set('indicators', normalized);
        changed = true;
      }
    }

    if (changed) {
      setSearchParams(next, { replace: true });
    }
  }, [
    days,
    defaultIndicatorsCsv,
    indicatorsRaw,
    period,
    searchParams,
    setSearchParams,
  ]);

  useEffect(() => {
    setSearchInput(stock);
  }, [stock]);

  useEffect(() => {
    let active = true;
    const loadShortcuts = async () => {
      try {
        const [stockBar, codes] = await Promise.all([
          historyApi.getStockBarList({ limit: 8 }),
          systemConfigApi.getWatchlist().catch(() => [] as string[]),
        ]);
        if (!active) return;
        setRecentStocks(stockBar.items || []);
        setWatchlist(codes.slice(0, 12));
      } catch {
        if (!active) return;
        setRecentStocks([]);
      }
    };
    void loadShortcuts();
    return () => {
      active = false;
    };
  }, []);

  const syncUrl = useCallback(
    (overrides: {
      stock?: string;
      period?: TechnicalChartPeriod;
      days?: TechnicalChartDays;
      indicators?: string;
    }) => {
      const next = new URLSearchParams();
      const nextStock = overrides.stock !== undefined ? overrides.stock : stock;
      const nextPeriod = overrides.period ?? period;
      const nextDays = overrides.days ?? days;
      const nextIndicators = overrides.indicators ?? indicators;
      if (nextStock) next.set('stock', nextStock);
      next.set('period', nextPeriod);
      next.set('days', String(nextDays));
      next.set('indicators', nextIndicators || defaultIndicatorsCsv);
      setSearchParams(next, { replace: false });
    },
    [days, defaultIndicatorsCsv, indicators, period, setSearchParams, stock],
  );

  useEffect(() => {
    if (!stock) {
      setChart(null);
      setError(null);
      setLoading(false);
      return;
    }

    const requestId = ++requestIdRef.current;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setChart(null);

    void (async () => {
      try {
        const data = await technicalChartApi.get({
          stockCode: stock,
          period,
          days,
          indicators,
          signal: controller.signal,
        });
        if (requestId !== requestIdRef.current) {
          return;
        }
        setChart(data);
      } catch (err) {
        if (
          isRequestCanceled(err)
          || controller.signal.aborted
          || requestId !== requestIdRef.current
        ) {
          return;
        }
        setChart(null);
        setError(getParsedApiError(err));
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false);
        }
      }
    })();

    return () => {
      controller.abort();
    };
  }, [days, indicators, period, retryToken, stock]);

  const handleStockSubmit = useCallback(
    (code: string) => {
      const canonical = code.trim();
      if (!canonical) return;
      setSearchInput(canonical);
      syncUrl({ stock: canonical });
    },
    [syncUrl],
  );

  const summary = chart?.summary;
  const lastItem = chart?.items?.length ? chart.items[chart.items.length - 1] : null;
  const status = chart?.dataStatus;
  const daysOptions = useMemo(() => TECHNICAL_CHART_ALLOWED_DAYS, []);
  const periodOptions = useMemo(() => TECHNICAL_CHART_ALLOWED_PERIODS, []);
  const periodLabelKey = (value: TechnicalChartPeriod): UiTextKey => {
    if (value === 'weekly') return 'technicalChart.periodWeekly';
    if (value === 'monthly') return 'technicalChart.periodMonthly';
    return 'technicalChart.periodDaily';
  };
  const visiblePanels = useMemo(
    () => parseVisiblePanels(indicators, defaultPanels),
    [defaultPanels, indicators],
  );

  const handleTogglePanel = useCallback(
    (key: keyof TechnicalChartVisiblePanels) => {
      const next = togglePanel(visiblePanels, key);
      const nextIndicators = panelsToIndicatorsCsv(next) || defaultIndicatorsCsv;
      syncUrl({ indicators: nextIndicators });
    },
    [defaultIndicatorsCsv, syncUrl, visiblePanels],
  );

  const formatWarning = useCallback((code: string) => {
    const known: Record<string, UiTextKey> = {
      history_shorter_than_display_days: 'technicalChart.warning.historyShorterThanDisplay',
      history_shorter_than_requested_warmup: 'technicalChart.warning.historyShorterThanWarmup',
      daily_history_fetch_capped: 'technicalChart.warning.dailyFetchCapped',
      no_aggregated_bars: 'technicalChart.warning.noAggregatedBars',
      partial_indicators: 'technicalChart.warning.partialIndicators',
      indicators_unavailable_on_latest_bar: 'technicalChart.warning.indicatorsUnavailable',
    };
    const key = known[code];
    return key ? t(key) : code;
  }, [t]);

  const accessibleSummary = chart
    ? t('technicalChart.accessibleSummary', {
      stock: chart.stockName ? `${chart.stockName} (${chart.stockCode})` : chart.stockCode,
      period: t(periodLabelKey(period)),
      days,
      points: chart.items.length,
    })
    : '';
  const changePercent = summary?.latestChangePercent;
  const marketValueTone = changePercent != null && changePercent > 0
    ? 'text-danger'
    : changePercent != null && changePercent < 0
      ? 'text-success'
      : 'text-foreground';

  return (
    <AppPage>
      <PageHeader
        title={t('technicalChart.pageTitle')}
        description={t('technicalChart.pageDescription')}
      />

      <Card className="mb-4 space-y-4" padding="md">
        <div className="max-w-xl">
          <label className="mb-2 block text-sm text-secondary-text" htmlFor="technical-chart-stock">
            {t('technicalChart.searchLabel')}
          </label>
          <StockAutocomplete
            value={searchInput}
            onChange={setSearchInput}
            onSubmit={handleStockSubmit}
            placeholder={t('technicalChart.searchPlaceholder')}
            ariaLabel={t('technicalChart.searchLabel')}
          />
        </div>

        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible">
          <span className="shrink-0 self-center text-xs text-secondary-text">
            {t('technicalChart.periodLabel')}
          </span>
          {periodOptions.map((option) => (
            <Button
              key={option}
              type="button"
              size="sm"
              className="shrink-0"
              variant={period === option ? 'primary' : 'secondary'}
              aria-pressed={period === option}
              onClick={() => syncUrl({ period: option })}
            >
              {t(periodLabelKey(option))}
            </Button>
          ))}
          {daysOptions.map((option) => (
            <Button
              key={option}
              type="button"
              size="sm"
              className="shrink-0"
              variant={days === option ? 'primary' : 'secondary'}
              aria-pressed={days === option}
              onClick={() => syncUrl({ days: option })}
            >
              {t('technicalChart.daysOption', { days: option })}
            </Button>
          ))}
        </div>

        <div className="space-y-2" data-testid="technical-chart-indicator-toggles">
          <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible">
            <span className="shrink-0 self-center text-xs text-secondary-text">
              {t('technicalChart.indicatorsLabel')}
            </span>
            {CORE_TOGGLE_KEYS.map(({ key, labelKey }) => (
              <Button
                key={key}
                type="button"
                size="sm"
                className="shrink-0"
                variant={visiblePanels[key] ? 'primary' : 'secondary'}
                aria-pressed={visiblePanels[key]}
                onClick={() => handleTogglePanel(key)}
              >
                {t(labelKey)}
              </Button>
            ))}
          </div>
          <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible">
            <span className="shrink-0 self-center text-xs text-secondary-text">
              {t('technicalChart.subplotLabel')}
            </span>
            {SUBPLOT_TOGGLE_ITEMS.map(({ key, labelKey }) => (
              <Button
                key={key}
                type="button"
                size="sm"
                className="shrink-0"
                variant={visiblePanels[key] ? 'primary' : 'secondary'}
                aria-pressed={visiblePanels[key]}
                onClick={() => handleTogglePanel(key)}
              >
                {t(labelKey)}
              </Button>
            ))}
          </div>
        </div>

        {!stock ? (
          <div className="space-y-4">
            <InlineAlert
              variant="info"
              title={t('technicalChart.noStockTitle')}
              message={t('technicalChart.noStockDescription')}
            />
            {recentStocks.length > 0 ? (
              <div>
                <div className="mb-2 text-sm font-medium text-primary-text">
                  {t('technicalChart.recentAnalyses')}
                </div>
                <div className="flex flex-wrap gap-2">
                  {recentStocks.map((item) => (
                    <Button
                      key={`${item.stockCode}-${item.id}`}
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => handleStockSubmit(item.stockCode)}
                    >
                      {item.stockCode}
                      {item.stockName ? ` · ${item.stockName}` : ''}
                    </Button>
                  ))}
                </div>
              </div>
            ) : null}
            {watchlist.length > 0 ? (
              <div>
                <div className="mb-2 text-sm font-medium text-primary-text">
                  {t('technicalChart.watchlist')}
                </div>
                <div className="flex flex-wrap gap-2">
                  {watchlist.map((code) => (
                    <Button
                      key={code}
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => handleStockSubmit(code)}
                    >
                      {code}
                    </Button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </Card>

      {stock ? (
        <Card className="space-y-4" padding="md">
          {loading ? <Loading label={t('technicalChart.loading')} /> : null}

          {error ? (
            <div className="space-y-3">
              <ApiErrorAlert error={error} />
              <Button type="button" onClick={() => setRetryToken((value) => value + 1)}>
                {t('technicalChart.retry')}
              </Button>
            </div>
          ) : null}

          {!loading && !error && status === 'empty' ? (
            <EmptyState
              title={t('technicalChart.emptyTitle')}
              description={t('technicalChart.emptyDescription')}
            />
          ) : null}

          {!loading && !error && chart && (status === 'available' || status === 'partial') ? (
            <div className="space-y-3">
              {status === 'partial' ? (
                <InlineAlert
                  variant="warning"
                  title={t('technicalChart.partialTitle')}
                  message={
                    (chart.warnings || []).map(formatWarning).join(' · ')
                    || t('technicalChart.partialDescription')
                  }
                />
              ) : null}

              <div
                className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
                data-testid="technical-chart-summary-grid"
              >
                <div className="rounded-xl border border-border/80 bg-background/45 px-4 py-3 shadow-sm">
                  <div className="text-xs font-medium text-secondary-text">{t('technicalChart.summary.stock')}</div>
                  <div className="mt-1 text-base font-semibold text-foreground">
                    {chart.stockName || '—'} ({chart.stockCode})
                  </div>
                </div>
                <div className="rounded-xl border border-border/80 bg-background/45 px-4 py-3 shadow-sm">
                  <div className="text-xs font-medium text-secondary-text">{t('technicalChart.summary.latestClose')}</div>
                  <div className={`mt-1 text-lg font-bold tabular-nums ${marketValueTone}`}>
                    {formatOptionalNumber(summary?.latestClose)}
                  </div>
                </div>
                <div className="rounded-xl border border-border/80 bg-background/45 px-4 py-3 shadow-sm">
                  <div className="text-xs font-medium text-secondary-text">{t('technicalChart.summary.changePercent')}</div>
                  <div className={`mt-1 text-lg font-bold tabular-nums ${marketValueTone}`}>
                    {formatSignedPercent(summary?.latestChangePercent)}
                  </div>
                </div>
                <div className="rounded-xl border border-border/80 bg-background/45 px-4 py-3 shadow-sm">
                  <div className="text-xs font-medium text-secondary-text">{t('technicalChart.summary.dataPoints')}</div>
                  <div className="mt-1 text-lg font-bold tabular-nums text-foreground">
                    {chart.items.length}
                  </div>
                  {lastItem?.date ? (
                    <div className="mt-0.5 text-xs text-secondary-text">{lastItem.date}</div>
                  ) : null}
                </div>
              </div>

              <p className="text-sm text-secondary-text" data-testid="technical-chart-accessible-summary">
                {accessibleSummary}
              </p>

              {chart.items.length > 0 ? (
                <TechnicalPriceVolumeChart
                  key={`${chart.stockCode}-${chart.period}-${chart.rangeDays}-${indicators}`}
                  response={chart}
                  indicators={indicators}
                  compact={isCompact}
                  ariaLabel={accessibleSummary}
                />
              ) : (
                <div
                  className="flex min-h-[240px] items-center justify-center rounded-xl border border-dashed border-border bg-hover/40 px-4 text-center text-sm text-secondary-text"
                  data-testid="technical-chart-placeholder"
                >
                  {t('technicalChart.chartPlaceholder')}
                </div>
              )}

              <div
                className="space-y-1 rounded-xl border border-border/70 bg-card/40 px-4 py-3 text-xs text-secondary-text"
                data-testid="technical-chart-data-notes"
              >
                <div className="font-medium text-primary-text">{t('technicalChart.dataNotes.title')}</div>
                <div>
                  {t('technicalChart.dataNotes.source')}: {chart.dataSource || '—'}
                </div>
                <div>
                  {t('technicalChart.dataNotes.updatedAt')}: {chart.updatedAt || '—'}
                </div>
                <div>
                  {t('technicalChart.dataNotes.version')}: {chart.calculationVersion || '—'}
                </div>
                <div>
                  {t('technicalChart.dataNotes.points')}: {chart.items.length}
                </div>
                <div>{t('technicalChart.dataNotes.params')}</div>
                <div className="pt-1 text-secondary-text/90">{t('technicalChart.disclaimer')}</div>
              </div>
            </div>
          ) : null}
        </Card>
      ) : null}
    </AppPage>
  );
};

export default TechnicalChartPage;
