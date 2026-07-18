import { useCallback, useMemo, useState } from 'react';
import { useTheme } from 'next-themes';
import type { TechnicalChartResponse } from '../../api/technicalChart';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import {
  buildTechnicalChartOption,
  estimateTechnicalChartHeight,
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
        />
      )}
    </div>
  );
}

export default TechnicalPriceVolumeChart;
