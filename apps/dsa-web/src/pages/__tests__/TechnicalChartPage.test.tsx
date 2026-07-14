import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiError, createParsedApiError } from '../../api/error';
import { historyApi } from '../../api/history';
import { systemConfigApi } from '../../api/systemConfig';
import { technicalChartApi } from '../../api/technicalChart';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../utils/uiLanguage';
import TechnicalChartPage from '../TechnicalChartPage';

vi.mock('../../api/technicalChart', async () => {
  const actual = await vi.importActual<typeof import('../../api/technicalChart')>('../../api/technicalChart');
  return {
    ...actual,
    technicalChartApi: {
      get: vi.fn(),
    },
  };
});

vi.mock('../../api/history', () => ({
  historyApi: {
    getStockBarList: vi.fn(),
  },
}));

vi.mock('../../api/systemConfig', () => ({
  systemConfigApi: {
    getWatchlist: vi.fn(),
  },
}));

vi.mock('../../components/StockAutocomplete', () => ({
  StockAutocomplete: ({
    value,
    onChange,
    onSubmit,
    placeholder,
    ariaLabel,
  }: {
    value: string;
    onChange: (value: string) => void;
    onSubmit: (code: string, name?: string, source?: string) => void;
    placeholder?: string;
    ariaLabel?: string;
  }) => (
    <div>
      <input
        aria-label={ariaLabel}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        data-testid="stock-autocomplete-input"
      />
      <button
        type="button"
        data-testid="stock-autocomplete-submit-canonical"
        onClick={() => onSubmit('600519', '贵州茅台', 'autocomplete')}
      >
        submit-canonical
      </button>
      <button
        type="button"
        data-testid="stock-autocomplete-submit-value"
        onClick={() => onSubmit(value.trim(), undefined, 'manual')}
      >
        submit-value
      </button>
    </div>
  ),
}));

vi.mock('../../components/technical-chart', async () => {
  const actual = await vi.importActual<typeof import('../../components/technical-chart')>('../../components/technical-chart');
  return {
    ...actual,
    TechnicalPriceVolumeChart: () => <div data-testid="technical-price-volume-chart">chart</div>,
  };
});

const compactState = { value: false };

vi.mock('../../hooks/useMediaQuery', () => ({
  TECHNICAL_CHART_COMPACT_QUERY: '(max-width: 1023px)',
  useMediaQuery: () => compactState.value,
  useIsCompactViewport: () => compactState.value,
}));

function LocationProbe() {
  const [searchParams] = useSearchParams();
  return <div data-testid="location-probe">{searchParams.toString()}</div>;
}

function renderPage(path = '/technical-chart') {
  return render(
    <UiLanguageProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/technical-chart"
            element={(
              <>
                <LocationProbe />
                <TechnicalChartPage />
              </>
            )}
          />
        </Routes>
      </MemoryRouter>
    </UiLanguageProvider>,
  );
}

function makeChartResponse(overrides: Record<string, unknown> = {}) {
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
        date: '2026-07-14',
        open: 1800,
        high: 1820,
        low: 1790,
        close: 1810,
        volume: 1000,
      },
    ],
    summary: {
      latestClose: 1810,
      latestChangePercent: 1.25,
      latestVolumeStatus: 'normal',
      volumeRatio: 1.1,
      supportLevels: [],
      resistanceLevels: [],
      recentHigh: { price: 1820, date: '2026-07-14' },
      recentLow: { price: 1790, date: '2026-07-14' },
    },
    warnings: [],
    ...overrides,
  };
}

describe('TechnicalChartPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    compactState.value = false;
    localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, 'zh');
    vi.mocked(historyApi.getStockBarList).mockResolvedValue({
      total: 1,
      items: [{ id: 1, stockCode: '000001', stockName: '平安银行', analysisCount: 1 }],
    });
    vi.mocked(systemConfigApi.getWatchlist).mockResolvedValue(['300750']);
    vi.mocked(technicalChartApi.get).mockResolvedValue(makeChartResponse());
  });

  it('does not request the chart API when stock is missing', async () => {
    renderPage('/technical-chart');

    expect(await screen.findByText('请先选择股票')).toBeInTheDocument();
    expect(technicalChartApi.get).not.toHaveBeenCalled();
    expect(await screen.findByRole('button', { name: /000001/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '300750' })).toBeInTheDocument();
  });

  it('loads chart summary from the URL stock parameter', async () => {
    renderPage('/technical-chart?stock=600519&days=120');

    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalledTimes(1));
    expect(technicalChartApi.get).toHaveBeenCalledWith(
      expect.objectContaining({
        stockCode: '600519',
        period: 'daily',
        days: 120,
        signal: expect.any(AbortSignal),
      }),
    );
    expect(await screen.findByText('贵州茅台 (600519)')).toBeInTheDocument();
    expect(screen.getByText('1810.00')).toBeInTheDocument();
    expect(screen.getByText('+1.25%')).toBeInTheDocument();
    expect(screen.getByTestId('technical-price-volume-chart')).toBeInTheDocument();
  });

  it('shows partial warnings and available summary', async () => {
    vi.mocked(technicalChartApi.get).mockResolvedValue(
      makeChartResponse({
        dataStatus: 'partial',
        warnings: ['macd_warmup'],
      }),
    );

    renderPage('/technical-chart?stock=600519');

    expect(await screen.findByText('数据不完整')).toBeInTheDocument();
    expect(screen.getByText('macd_warmup')).toBeInTheDocument();
    expect(screen.getByText('贵州茅台 (600519)')).toBeInTheDocument();
  });

  it('shows empty state without crashing the page', async () => {
    vi.mocked(technicalChartApi.get).mockResolvedValue(
      makeChartResponse({
        dataStatus: 'empty',
        items: [],
        summary: {
          latestClose: null,
          latestChangePercent: null,
          latestVolumeStatus: null,
          volumeRatio: null,
          supportLevels: [],
          resistanceLevels: [],
          recentHigh: null,
          recentLow: null,
        },
      }),
    );

    renderPage('/technical-chart?stock=600519');

    expect(await screen.findByText('暂无行情数据')).toBeInTheDocument();
    expect(screen.queryByTestId('technical-price-volume-chart')).not.toBeInTheDocument();
  });

  it('shows error alert and retries the request', async () => {
    vi.mocked(technicalChartApi.get)
      .mockRejectedValueOnce(
        createApiError(
          createParsedApiError({
            title: '行情源不可用',
            message: 'source_unavailable',
            status: 503,
            category: 'http_error',
          }),
          { response: { status: 503 } },
        ),
      )
      .mockResolvedValueOnce(makeChartResponse());

    renderPage('/technical-chart?stock=600519');

    expect(await screen.findByText('行情源不可用')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));

    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('贵州茅台 (600519)')).toBeInTheDocument();
  });

  it('uses StockAutocomplete canonical code instead of display name', async () => {
    renderPage('/technical-chart');

    fireEvent.change(await screen.findByTestId('stock-autocomplete-input'), {
      target: { value: '贵州茅台' },
    });
    fireEvent.click(screen.getByTestId('stock-autocomplete-submit-canonical'));

    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalled());
    expect(technicalChartApi.get).toHaveBeenCalledWith(
      expect.objectContaining({ stockCode: '600519' }),
    );
    expect(screen.getByTestId('location-probe')).toHaveTextContent('stock=600519');
  });

  it('keeps the latest request when stock switches quickly', async () => {
    let resolveFirst: (value: ReturnType<typeof makeChartResponse>) => void = () => undefined;
    const firstPromise = new Promise<ReturnType<typeof makeChartResponse>>((resolve) => {
      resolveFirst = resolve;
    });

    vi.mocked(technicalChartApi.get)
      .mockImplementationOnce(() => firstPromise)
      .mockResolvedValueOnce(
        makeChartResponse({
          stockCode: '300750',
          stockName: '宁德时代',
          summary: {
            latestClose: 200,
            latestChangePercent: -0.5,
            latestVolumeStatus: 'normal',
            volumeRatio: 0.9,
            supportLevels: [],
            resistanceLevels: [],
            recentHigh: null,
            recentLow: null,
          },
        }),
      );

    renderPage('/technical-chart?stock=600519');
    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByTestId('stock-autocomplete-input'), {
      target: { value: '300750' },
    });
    fireEvent.click(screen.getByTestId('stock-autocomplete-submit-value'));

    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalledTimes(2));
    resolveFirst(makeChartResponse({ stockCode: '600519', stockName: '旧响应' }));

    expect(await screen.findByText('宁德时代 (300750)')).toBeInTheDocument();
    expect(screen.queryByText('旧响应 (600519)')).not.toBeInTheDocument();
  });

  it('normalizes illegal days and indicators in the URL while keeping weekly period', async () => {
    renderPage('/technical-chart?stock=600519&period=weekly&days=90&indicators=foo,ma');

    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalled());
    expect(technicalChartApi.get).toHaveBeenCalledWith(
      expect.objectContaining({
        period: 'weekly',
        days: 120,
        indicators: 'ma',
      }),
    );

    await waitFor(() => {
      const query = screen.getByTestId('location-probe').textContent || '';
      expect(query).toContain('period=weekly');
      expect(query).toContain('days=120');
      expect(query).toContain('indicators=ma');
    });
  });

  it('falls back to daily for illegal period values', async () => {
    renderPage('/technical-chart?stock=600519&period=quarterly');

    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalled());
    expect(technicalChartApi.get).toHaveBeenCalledWith(
      expect.objectContaining({ period: 'daily' }),
    );
    await waitFor(() => {
      const query = screen.getByTestId('location-probe').textContent || '';
      expect(query).toContain('period=daily');
    });
  });

  it('switches period and refetches with the new value', async () => {
    renderPage('/technical-chart?stock=600519&period=daily');
    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: '周线' }));

    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalledTimes(2));
    expect(technicalChartApi.get).toHaveBeenLastCalledWith(
      expect.objectContaining({ period: 'weekly' }),
    );
  });

  it('cancels stale requests when period changes quickly', async () => {
    let resolveFirst: ((value: ReturnType<typeof makeChartResponse>) => void) | undefined;
    vi.mocked(technicalChartApi.get)
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolveFirst = resolve;
      }))
      .mockImplementationOnce(() => Promise.resolve(
        makeChartResponse({ stockName: '周线响应', period: 'weekly' }),
      ));

    renderPage('/technical-chart?stock=600519&period=daily');
    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: '周线' }));
    await waitFor(() => expect(technicalChartApi.get).toHaveBeenCalledTimes(2));
    resolveFirst?.(makeChartResponse({ stockName: '旧日线响应', period: 'daily' }));

    expect(await screen.findByText('周线响应 (600519)')).toBeInTheDocument();
    expect(screen.queryByText('旧日线响应 (600519)')).not.toBeInTheDocument();
  });

  it('toggles indicator panels and syncs the indicators URL', async () => {
    renderPage('/technical-chart?stock=600519&indicators=ma,boll,volume,macd,rsi,support_resistance');

    expect(await screen.findByTestId('technical-chart-indicator-toggles')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'KDJ' })).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(screen.getByRole('button', { name: 'KDJ' }));

    await waitFor(() => {
      const query = screen.getByTestId('location-probe').textContent || '';
      expect(query).toContain('kdj');
    });
    expect(screen.getByRole('button', { name: 'KDJ' })).toHaveAttribute('aria-pressed', 'true');

    await waitFor(() => {
      expect(technicalChartApi.get).toHaveBeenCalledWith(
        expect.objectContaining({
          indicators: expect.stringContaining('kdj'),
        }),
      );
    });
  });

  it('restores indicator toggles from the URL', async () => {
    renderPage('/technical-chart?stock=600519&indicators=ma,volume,kdj');

    expect(await screen.findByRole('button', { name: 'KDJ' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'MACD' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'BOLL' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: '支撑压力' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('keeps a single subplot on compact viewports when enabling another', async () => {
    compactState.value = true;
    renderPage('/technical-chart?stock=600519&indicators=ma,boll,volume,macd,support_resistance');

    expect(await screen.findByText('副图（单选）')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'RSI' }));

    await waitFor(() => {
      const query = screen.getByTestId('location-probe').textContent || '';
      expect(query).toContain('rsi');
      expect(query).not.toContain('macd');
    });
    expect(screen.getByRole('button', { name: 'RSI' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'MACD' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('renders accessible summary and data notes', async () => {
    renderPage('/technical-chart?stock=600519&days=120');

    expect(await screen.findByTestId('technical-chart-accessible-summary')).toHaveTextContent('贵州茅台');
    expect(screen.getByTestId('technical-chart-data-notes')).toHaveTextContent('技术指标仅供信息参考');
    expect(screen.getByTestId('technical-chart-data-notes')).toHaveTextContent('technical-v1');
  });
});
