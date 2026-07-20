import { render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { EChartsHost } from '../EChartsHost';

const mockDispose = vi.fn();
const mockResize = vi.fn();
const mockSetOption = vi.fn();
const mockInit = vi.fn();
const mockGetInstanceByDom = vi.fn();

vi.mock('echarts/core', () => ({
  use: vi.fn(),
  init: (...args: unknown[]) => mockInit(...args),
  getInstanceByDom: (...args: unknown[]) => mockGetInstanceByDom(...args),
}));

function createChartInstance(disposed = false) {
  return {
    isDisposed: () => disposed,
    setOption: mockSetOption,
    resize: mockResize,
    dispose: mockDispose,
  };
}

function mockContainerDimensions(width: number, height: number) {
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
    configurable: true,
    get() {
      return width;
    },
  });
  Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
    configurable: true,
    get() {
      return height;
    },
  });
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
    configurable: true,
    get() {
      return width;
    },
  });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
    configurable: true,
    get() {
      return height;
    },
  });
}

describe('EChartsHost', () => {
  beforeEach(() => {
    mockContainerDimensions(400, 300);
    mockGetInstanceByDom.mockReturnValue(undefined);
    mockInit.mockImplementation(() => createChartInstance());
    mockSetOption.mockReset();
    mockResize.mockReset();
    mockDispose.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('calls setOption and resize without bubbling errors', async () => {
    const onError = vi.fn();
    render(
      <EChartsHost
        option={{ series: [] }}
        style={{ width: '400px', height: '300px' }}
        onError={onError}
      />,
    );

    await waitFor(() => {
      expect(mockInit).toHaveBeenCalled();
      expect(mockSetOption).toHaveBeenCalled();
      expect(mockResize).toHaveBeenCalled();
    });
    expect(onError).not.toHaveBeenCalled();
  });

  it('reports init failures locally', async () => {
    mockInit.mockImplementation(() => {
      throw new Error('init failed');
    });
    const onError = vi.fn();

    render(
      <EChartsHost
        option={{ series: [] }}
        style={{ width: '400px', height: '300px' }}
        onError={onError}
      />,
    );

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith({ phase: 'init', message: 'init failed' });
    });
  });

  it('reports setOption failures locally', async () => {
    mockSetOption.mockImplementation(() => {
      throw new Error('setOption failed');
    });
    const onError = vi.fn();

    render(
      <EChartsHost
        option={{ series: [] }}
        style={{ width: '400px', height: '300px' }}
        onError={onError}
      />,
    );

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith({ phase: 'setOption', message: 'setOption failed' });
    });
  });

  it('reports resize failures locally', async () => {
    mockResize.mockImplementation(() => {
      throw new Error('resize failed');
    });
    const onError = vi.fn();

    render(
      <EChartsHost
        option={{ series: [] }}
        style={{ width: '400px', height: '300px' }}
        onError={onError}
      />,
    );

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith({ phase: 'resize', message: 'resize failed' });
    });
  });

  it('retries init when container size is zero and stops after max retries', async () => {
    mockContainerDimensions(0, 0);
    const rafCallbacks: FrameRequestCallback[] = [];
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      rafCallbacks.push(callback);
      return rafCallbacks.length;
    });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => undefined);

    const onError = vi.fn();
    render(
      <EChartsHost
        option={{ series: [] }}
        style={{ width: '0px', height: '0px' }}
        onError={onError}
      />,
    );

    for (let index = 0; index < 5; index += 1) {
      const callback = rafCallbacks.shift();
      callback?.(0);
    }

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith({
        phase: 'init',
        message: 'Chart container has zero size',
      });
    });
    expect(mockInit).not.toHaveBeenCalled();
  });

  it('disposes chart and disconnects observer on unmount', async () => {
    const disconnect = vi.fn();
    class MockResizeObserver {
      observe = vi.fn();
      disconnect = disconnect;
    }
    vi.stubGlobal('ResizeObserver', MockResizeObserver);

    const chart = createChartInstance();
    mockInit.mockReturnValue(chart);
    mockGetInstanceByDom.mockReturnValue(undefined);

    const { unmount } = render(
      <EChartsHost
        option={{ series: [] }}
        style={{ width: '400px', height: '300px' }}
      />,
    );

    await waitFor(() => {
      expect(mockInit).toHaveBeenCalled();
    });

    unmount();
    expect(disconnect).toHaveBeenCalled();
    expect(mockDispose).toHaveBeenCalled();
  });

  it('does not report dispose failures through onError', async () => {
    mockDispose.mockImplementation(() => {
      throw new Error('dispose failed');
    });
    const onError = vi.fn();
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);

    const { unmount } = render(
      <EChartsHost
        option={{ series: [] }}
        style={{ width: '400px', height: '300px' }}
        onError={onError}
      />,
    );

    await waitFor(() => {
      expect(mockInit).toHaveBeenCalled();
    });

    unmount();
    expect(mockDispose).toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalledWith(
      expect.objectContaining({ phase: 'dispose' }),
    );
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});
