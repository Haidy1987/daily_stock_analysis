import { useMemo } from 'react';
import { useTheme } from 'next-themes';
import type { TechnicalChartResponse } from '../../api/technicalChart';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import {
  buildTechnicalChartOption,
  estimateTechnicalChartHeight,
  parseVisiblePanels,
} from './buildTechnicalChartOption';
import { EChartsHost } from './EChartsHost';
import { readTechnicalChartThemeColors } from './themeColors';

type TechnicalPriceVolumeChartProps = {
  response: TechnicalChartResponse;
  indicators?: string;
  compact?: boolean;
  ariaLabel?: string;
  className?: string;
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

  return (
    <div
      className={`w-full overflow-hidden rounded-xl border border-border bg-card/40 ${className}`}
      data-testid="technical-price-volume-chart"
      data-compact={compact ? 'true' : 'false'}
    >
      <EChartsHost
        option={option}
        resetKey={resetKey}
        ariaLabel={resolvedAriaLabel}
        className={`w-full ${compact ? 'min-h-[360px]' : 'min-h-[520px]'}`}
        style={{ height: `${chartHeight}px` }}
      />
    </div>
  );
}

export default TechnicalPriceVolumeChart;
