import { useCallback, useMemo, useState } from 'react';
import { useTheme } from 'next-themes';
import type { TechnicalChartResponse } from '../../api/technicalChart';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import {
  buildTechnicalChartOption,
  estimateTechnicalChartHeight,
  formatTooltipValue,
  parseVisiblePanels,
} from './buildTechnicalChartOption';
import { EChartsHost, type EChartsHostError } from './EChartsHost';
import { readTechnicalChartThemeColors } from './themeColors';

type TechnicalPriceVolumeChartProps = {
  response: TechnicalChartResponse;
  indicators?: string;
  compact?: boolean;
  ariaLabel?: string;
  className?: string;
};

type ChartErrorState = {
  code: string;
  phase: EChartsHostError['phase'];
};

export function TechnicalPriceVolumeChart({
  response,
  indicators,
  compact = false,
  ariaLabel,
  className = '',
}: TechnicalPriceVolumeChartProps) {
  const { t } = useUiLanguage();
  const { resolvedTheme } = useTheme();
  const [renderAttempt, setRenderAttempt] = useState(0);
  const [chartError, setChartError] = useState<ChartErrorState | null>(null);

  const colors = useMemo(() => {
    void resolvedTheme;
    return readTechnicalChartThemeColors();
  }, [resolvedTheme]);

  const visible = useMemo(() => parseVisiblePanels(indicators), [indicators]);
  const chartHeight = estimateTechnicalChartHeight(visible, { compact });
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const selectedItem = selectedIndex != null ? response.items[selectedIndex] : undefined;
  const handleDataIndexChange = useCallback((dataIndex: number) => {
    setSelectedIndex(dataIndex >= 0 && dataIndex < response.items.length ? dataIndex : null);
  }, [response.items.length]);

  const selectedDetailRows = selectedItem
    ? [
      `${t('technicalChart.tooltip.open')} ${formatTooltipValue(selectedItem.open)} · ${t('technicalChart.tooltip.close')} ${formatTooltipValue(selectedItem.close)} · ${t('technicalChart.tooltip.low')} ${formatTooltipValue(selectedItem.low)} · ${t('technicalChart.tooltip.high')} ${formatTooltipValue(selectedItem.high)}`,
      visible.ma
        ? [
          ['ma5', selectedItem.ma5],
          ['ma10', selectedItem.ma10],
          ['ma20', selectedItem.ma20],
          ['ma30', selectedItem.ma30],
          ['ma60', selectedItem.ma60],
          ['ma90', selectedItem.ma90],
          ['ma120', selectedItem.ma120],
          ['ma250', selectedItem.ma250],
        ].map(([key, value]) => `${t(
          `technicalChart.chart.${key}` as Parameters<typeof t>[0],
        )} ${formatTooltipValue(value as number | null | undefined)}`).join(' · ')
        : null,
      visible.boll
        ? `${t('technicalChart.chart.bollUpper')} ${formatTooltipValue(selectedItem.bollUpper)} · ${t('technicalChart.chart.bollMid')} ${formatTooltipValue(selectedItem.bollMid)} · ${t('technicalChart.chart.bollLower')} ${formatTooltipValue(selectedItem.bollLower)} · ${t('technicalChart.tooltip.bandwidth')} ${formatTooltipValue(selectedItem.bollBandwidth, 4)} · ${t('technicalChart.tooltip.position')} ${formatTooltipValue(selectedItem.bollPosition)}`
        : null,
      visible.volume
        ? `${t('technicalChart.chart.volume')} ${formatTooltipValue(selectedItem.volume, 0)} · ${t('technicalChart.tooltip.ratio')} ${formatTooltipValue(selectedItem.volumeRatio)} · ${selectedItem.volumeStatus ?? '--'}`
        : null,
      visible.macd
        ? `${t('technicalChart.chart.macdDif')} ${formatTooltipValue(selectedItem.macdDif)} · ${t('technicalChart.chart.macdDea')} ${formatTooltipValue(selectedItem.macdDea)} · ${t('technicalChart.chart.macdBar')} ${formatTooltipValue(selectedItem.macdBar)}`
        : null,
      visible.rsi
        ? `${t('technicalChart.chart.rsi6')} ${formatTooltipValue(selectedItem.rsi6)} · ${t('technicalChart.chart.rsi12')} ${formatTooltipValue(selectedItem.rsi12)} · ${t('technicalChart.chart.rsi24')} ${formatTooltipValue(selectedItem.rsi24)}`
        : null,
      visible.kdj
        ? `${t('technicalChart.chart.kdjK')} ${formatTooltipValue(selectedItem.kdjK)} · ${t('technicalChart.chart.kdjD')} ${formatTooltipValue(selectedItem.kdjD)} · ${t('technicalChart.chart.kdjJ')} ${formatTooltipValue(selectedItem.kdjJ)}`
        : null,
      visible.cci ? `${t('technicalChart.chart.cci')} ${formatTooltipValue(selectedItem.cci)}` : null,
      visible.bias
        ? `${t('technicalChart.chart.bias5')} ${formatTooltipValue(selectedItem.bias5)} · ${t('technicalChart.chart.bias10')} ${formatTooltipValue(selectedItem.bias10)} · ${t('technicalChart.chart.bias20')} ${formatTooltipValue(selectedItem.bias20)}`
        : null,
    ].filter((row): row is string => Boolean(row))
    : [];

  const option = useMemo(
    () => buildTechnicalChartOption({
      response,
      colors,
      visible,
      layout: { compact },
      labels: {
        candle: t('technicalChart.chart.candle'),
        volume: t('technicalChart.chart.volume'),
        ma5: t('technicalChart.chart.ma5'),
        ma10: t('technicalChart.chart.ma10'),
        ma20: t('technicalChart.chart.ma20'),
        ma30: t('technicalChart.chart.ma30'),
        ma60: t('technicalChart.chart.ma60'),
        ma90: t('technicalChart.chart.ma90'),
        ma120: t('technicalChart.chart.ma120'),
        ma250: t('technicalChart.chart.ma250'),
        bollUpper: t('technicalChart.chart.bollUpper'),
        bollMid: t('technicalChart.chart.bollMid'),
        bollLower: t('technicalChart.chart.bollLower'),
        support: t('technicalChart.chart.support'),
        resistance: t('technicalChart.chart.resistance'),
        recentHigh: t('technicalChart.chart.recentHigh'),
        recentLow: t('technicalChart.chart.recentLow'),
        macdDif: t('technicalChart.chart.macdDif'),
        macdDea: t('technicalChart.chart.macdDea'),
        macdBar: t('technicalChart.chart.macdBar'),
        rsi6: t('technicalChart.chart.rsi6'),
        rsi12: t('technicalChart.chart.rsi12'),
        rsi24: t('technicalChart.chart.rsi24'),
        kdjK: t('technicalChart.chart.kdjK'),
        kdjD: t('technicalChart.chart.kdjD'),
        kdjJ: t('technicalChart.chart.kdjJ'),
        cci: t('technicalChart.chart.cci'),
        bias5: t('technicalChart.chart.bias5'),
        bias10: t('technicalChart.chart.bias10'),
        bias20: t('technicalChart.chart.bias20'),
        open: t('technicalChart.tooltip.open'),
        high: t('technicalChart.tooltip.high'),
        low: t('technicalChart.tooltip.low'),
        close: t('technicalChart.tooltip.close'),
        bandwidth: t('technicalChart.tooltip.bandwidth'),
        position: t('technicalChart.tooltip.position'),
        ratio: t('technicalChart.tooltip.ratio'),
      },
    }),
    [colors, compact, response, t, visible],
  );

  const resetKey = `${response.stockCode}|${response.rangeDays}|${response.period}|${response.items.length}|${response.updatedAt ?? ''}`;
  const resolvedAriaLabel = ariaLabel
    || t('technicalChart.chartAriaLabel', {
      stock: response.stockName
        ? `${response.stockName} (${response.stockCode})`
        : response.stockCode,
      period: t('technicalChart.periodDaily'),
      days: response.rangeDays,
      points: response.items.length,
    });

  const handleChartError = useCallback((error: EChartsHostError) => {
    // Cleanup-phase failures must not overwrite the original render error,
    // and alone they should never put the chart into a degraded UI state.
    if (error.phase === 'dispose') {
      return;
    }

    setChartError((current) => {
      if (current) {
        return current;
      }

      return {
        code: `TC-${error.phase}-${renderAttempt + 1}`,
        phase: error.phase,
      };
    });
  }, [renderAttempt]);

  const handleRetryRender = useCallback(() => {
    setChartError(null);
    setRenderAttempt((value) => value + 1);
  }, []);

  return (
    <div
      className={`w-full overflow-hidden rounded-xl border border-border bg-card/40 ${className}`}
      data-testid="technical-price-volume-chart"
      data-compact={compact ? 'true' : 'false'}
    >
      {chartError ? (
        <div
          className="flex min-h-[240px] flex-col items-center justify-center gap-3 px-4 py-8 text-center"
          data-testid="technical-chart-render-error"
        >
          <p className="text-sm font-medium text-primary-text">
            {t('technicalChart.chartRenderFailed')}
          </p>
          <p className="text-xs text-secondary-text">
            {t('technicalChart.chartErrorPhase', { phase: chartError.phase, code: chartError.code })}
          </p>
          <button
            type="button"
            className="btn-primary"
            onClick={handleRetryRender}
          >
            {t('technicalChart.chartRetryRender')}
          </button>
        </div>
      ) : (
        <EChartsHost
          key={`${resetKey}|attempt-${renderAttempt}`}
          option={option}
          resetKey={resetKey}
          ariaLabel={resolvedAriaLabel}
          className={`w-full ${compact ? 'min-h-[360px]' : 'min-h-[520px]'}`}
          style={{ height: `${chartHeight}px` }}
          onError={handleChartError}
          onDataIndexChange={compact ? handleDataIndexChange : undefined}
        />
      )}
      {compact && selectedItem ? (
        <section
          className="border-t border-border bg-card/70 px-2.5 py-2"
          data-testid="technical-chart-mobile-data-inspector"
          aria-live="polite"
        >
          <div className="flex items-center justify-between gap-2 text-xs">
            <div>
              <p className="text-secondary-text">{t('technicalChart.mobile.selectedData')}</p>
              <p className="font-medium text-primary-text">
                {selectedItem.date} · {t('technicalChart.tooltip.close')} {formatTooltipValue(selectedItem.close)}
              </p>
            </div>
          </div>
          <details className="mt-2">
            <summary className="cursor-pointer select-none text-xs font-medium text-primary-text">
              {t('technicalChart.mobile.viewDetails')}
            </summary>
            <div className="mt-2 space-y-1 text-xs leading-5 text-secondary-text">
              {selectedDetailRows.map((row) => <div key={row}>{row}</div>)}
            </div>
          </details>
        </section>
      ) : null}
    </div>
  );
}

export default TechnicalPriceVolumeChart;
