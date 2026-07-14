import type { ComponentProps } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { TechnicalChartResponse } from '../../../api/technicalChart';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../../utils/uiLanguage';
import { TechnicalPriceVolumeChart } from '../TechnicalPriceVolumeChart';

const chartHostErrorHandler = vi.fn<(error: { phase: 'init' | 'setOption' | 'resize' | 'dispose'; message: string }) => void>();

vi.mock('next-themes', () => ({
  useTheme: () => ({ resolvedTheme: 'dark' }),
}));

vi.mock('../EChartsHost', () => ({
  EChartsHost: ({
    onError,
  }: {
    onError?: (error: { phase: 'init' | 'setOption' | 'resize' | 'dispose'; message: string }) => void;
  }) => {
    chartHostErrorHandler.mockImplementation((error) => {
      onError?.(error);
    });
    return <div data-testid="technical-chart-echarts-host">chart-host</div>;
  },
}));

function makeResponse(): TechnicalChartResponse {
  return {
    stockCode: '000988.SZ',
    stockName: '华工科技',
    period: 'daily',
    rangeDays: 120,
    calculationVersion: 'technical-v1',
    dataStatus: 'available',
    dataSource: 'mock',
    updatedAt: '2026-07-14T00:00:00Z',
    items: [
      {
        date: '2026-07-10',
        open: 10,
        high: 11,
        low: 9,
        close: 10.5,
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
        volumeRatio: 1,
        volumeStatus: 'normal',
      },
    ],
    summary: {
      latestClose: 10.5,
      latestChangePercent: 1.2,
      latestVolumeStatus: 'normal',
      volumeRatio: 1,
      supportLevels: [],
      resistanceLevels: [],
      recentHigh: { price: 11, date: '2026-07-10' },
      recentLow: { price: 9, date: '2026-07-10' },
    },
    warnings: [],
  };
}

function renderChart(props?: Partial<ComponentProps<typeof TechnicalPriceVolumeChart>>) {
  return render(
    <UiLanguageProvider>
      <TechnicalPriceVolumeChart
        response={makeResponse()}
        indicators="ma,boll,volume,macd,support_resistance"
        compact={false}
        {...props}
      />
    </UiLanguageProvider>,
  );
}

describe('TechnicalPriceVolumeChart', () => {
  beforeEach(() => {
    localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
  });

  it('renders chart host by default', () => {
    renderChart();
    expect(screen.getByTestId('technical-chart-echarts-host')).toBeInTheDocument();
  });

  it('shows local fallback when chart host reports an error', async () => {
    renderChart();
    await act(async () => {
      chartHostErrorHandler({ phase: 'setOption', message: 'setOption failed' });
    });

    expect(await screen.findByTestId('technical-chart-render-error')).toBeInTheDocument();
    expect(screen.getByText('图表渲染失败')).toBeInTheDocument();
    expect(screen.getByText(/阶段：setOption/)).toBeInTheDocument();
  });

  it('remounts chart host when retry is clicked', async () => {
    renderChart();
    await act(async () => {
      chartHostErrorHandler({ phase: 'init', message: 'init failed' });
    });

    expect(await screen.findByTestId('technical-chart-render-error')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重新渲染图表' }));

    await waitFor(() => {
      expect(screen.getByTestId('technical-chart-echarts-host')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('technical-chart-render-error')).not.toBeInTheDocument();
  });

  it('marks compact mode on wrapper', () => {
    renderChart({ compact: true });
    expect(screen.getByTestId('technical-price-volume-chart')).toHaveAttribute('data-compact', 'true');
  });

  it('keeps the first error when setOption is followed by dispose', async () => {
    renderChart();
    await act(async () => {
      chartHostErrorHandler({ phase: 'setOption', message: 'setOption failed' });
      chartHostErrorHandler({ phase: 'dispose', message: 'dispose failed' });
    });

    expect(await screen.findByTestId('technical-chart-render-error')).toBeInTheDocument();
    expect(screen.getByText(/阶段：setOption/)).toBeInTheDocument();
    expect(screen.queryByText(/阶段：dispose/)).not.toBeInTheDocument();
  });

  it('does not show render failure when only dispose errors', async () => {
    renderChart();
    await act(async () => {
      chartHostErrorHandler({ phase: 'dispose', message: 'dispose failed' });
    });

    expect(screen.getByTestId('technical-chart-echarts-host')).toBeInTheDocument();
    expect(screen.queryByTestId('technical-chart-render-error')).not.toBeInTheDocument();
  });
});
