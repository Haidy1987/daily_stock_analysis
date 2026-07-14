import type { ComponentType } from 'react';
import { Suspense } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { isChunkLoadError, lazyWithRetry } from '../lazyWithRetry';

describe('isChunkLoadError', () => {
  it('detects ChunkLoadError by name', () => {
    const error = new Error('failed');
    error.name = 'ChunkLoadError';
    expect(isChunkLoadError(error)).toBe(true);
  });

  it('detects common browser chunk messages', () => {
    expect(isChunkLoadError(new Error('Loading chunk 42 failed'))).toBe(true);
    expect(isChunkLoadError(new Error('Failed to fetch dynamically imported module'))).toBe(true);
    expect(isChunkLoadError(new Error('Importing a module script failed'))).toBe(true);
  });

  it('returns false for unrelated errors', () => {
    expect(isChunkLoadError(new Error('Cannot read properties of undefined'))).toBe(false);
  });
});

describe('lazyWithRetry', () => {
  const moduleId = 'pages/TestPage';
  const retryKey = `dsa:chunk-retry:${moduleId}:/`;

  beforeEach(() => {
    sessionStorage.clear();
    vi.stubGlobal('location', {
      ...window.location,
      pathname: '/',
      reload: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  function TestComponent() {
    return <div data-testid="loaded-page">loaded</div>;
  }

  it('loads a module successfully and clears retry marker', async () => {
    sessionStorage.setItem(retryKey, '1');
    const factory = vi.fn(async () => ({ default: TestComponent as ComponentType<Record<string, unknown>> }));
    const LazyPage = lazyWithRetry(factory, moduleId);

    render(
      <Suspense fallback={<div>loading</div>}>
        <LazyPage />
      </Suspense>,
    );

    expect(await screen.findByTestId('loaded-page')).toBeInTheDocument();
    expect(sessionStorage.getItem(retryKey)).toBeNull();
    expect(factory).toHaveBeenCalledTimes(1);
  });

  it('rethrows non-chunk errors without reloading', async () => {
    const factory = vi.fn(async () => {
      throw new Error('render failed');
    });
    const LazyPage = lazyWithRetry(factory, moduleId);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    try {
      render(
        <Suspense fallback={<div>loading</div>}>
          <LazyPage />
        </Suspense>,
      );

      await waitFor(() => {
        expect(factory).toHaveBeenCalledTimes(1);
      });
      expect(window.location.reload).not.toHaveBeenCalled();
    } finally {
      consoleError.mockRestore();
    }
  });

  it('reloads once on first chunk error', async () => {
    const factory = vi.fn(async () => {
      throw new Error('Loading chunk 9 failed');
    });
    const LazyPage = lazyWithRetry(factory, moduleId);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    try {
      render(
        <Suspense fallback={<div>loading</div>}>
          <LazyPage />
        </Suspense>,
      );

      await waitFor(() => {
        expect(window.location.reload).toHaveBeenCalledTimes(1);
      });
      expect(sessionStorage.getItem(retryKey)).toBe('1');
    } finally {
      consoleError.mockRestore();
    }
  });

  it('does not reload again when retry marker already exists', async () => {
    sessionStorage.setItem(retryKey, '1');
    const factory = vi.fn(async () => {
      throw new Error('Failed to fetch dynamically imported module');
    });
    const LazyPage = lazyWithRetry(factory, moduleId);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    try {
      render(
        <Suspense fallback={<div>loading</div>}>
          <LazyPage />
        </Suspense>,
      );

      await waitFor(() => {
        expect(factory).toHaveBeenCalledTimes(1);
      });
      expect(window.location.reload).not.toHaveBeenCalled();
      expect(sessionStorage.getItem(retryKey)).toBeNull();
    } finally {
      consoleError.mockRestore();
    }
  });

  it('does not throw when sessionStorage is unavailable', async () => {
    const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage blocked');
    });
    const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage blocked');
    });
    const factory = vi.fn(async () => {
      throw new Error('Loading chunk 3 failed');
    });
    const LazyPage = lazyWithRetry(factory, moduleId);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    try {
      render(
        <Suspense fallback={<div>loading</div>}>
          <LazyPage />
        </Suspense>,
      );

      await waitFor(() => {
        expect(window.location.reload).toHaveBeenCalledTimes(1);
      });
    } finally {
      getItem.mockRestore();
      setItem.mockRestore();
      consoleError.mockRestore();
    }
  });
});
