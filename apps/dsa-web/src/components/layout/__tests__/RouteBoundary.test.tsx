import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { lazy } from 'react';
import type React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { RouteOutletBoundary } from '../RouteBoundary';
import { Shell } from '../Shell';

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    authEnabled: false,
    currentUser: null,
    logout: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock('../../../stores/agentChatStore', () => {
  const state = { completionBadge: false };

  return {
    useAgentChatStore: (selector?: (value: typeof state) => unknown) => (
      selector ? selector(state) : state
    ),
  };
});

describe('RouteOutletBoundary', () => {
  it('catches rejected lazy route imports inside the shell and resets on navigation', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const BrokenLazyRoute = lazy(() => (
      Promise.reject(new Error('Loading chunk 42 failed')) as Promise<{ default: React.ComponentType }>
    ));

    try {
      render(
        <MemoryRouter initialEntries={['/chat']}>
          <Routes>
            <Route
              element={(
                <Shell>
                  <RouteOutletBoundary />
                </Shell>
              )}
            >
              <Route path="/chat" element={<BrokenLazyRoute />} />
              <Route path="/portfolio" element={<div data-testid="portfolio-page">Portfolio</div>} />
            </Route>
          </Routes>
        </MemoryRouter>,
      );

      expect(screen.getByRole('navigation', { name: '主导航' })).toBeInTheDocument();
      expect(await screen.findByRole('heading', { name: '页面加载失败' })).toBeInTheDocument();
      expect(screen.getByText('页面资源版本已更新，请重新加载。若仍失败，请返回首页后再试。')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '重新加载页面' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '返回首页' })).toBeInTheDocument();

      fireEvent.click(screen.getByRole('link', { name: '持仓' }));

      expect(await screen.findByTestId('portfolio-page')).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: '页面加载失败' })).not.toBeInTheDocument();
    } finally {
      consoleError.mockRestore();
    }
  });

  it('shows render error description for component failures', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    function BrokenComponent(): never {
      throw new Error('Cannot read properties of undefined (reading map)');
    }

    try {
      render(
        <MemoryRouter initialEntries={['/chat']}>
          <Routes>
            <Route
              element={(
                <Shell>
                  <RouteOutletBoundary />
                </Shell>
              )}
            >
              <Route path="/chat" element={<BrokenComponent />} />
            </Route>
          </Routes>
        </MemoryRouter>,
      );

      expect(await screen.findByText('页面组件渲染失败。请重新加载页面，或返回首页后再试。')).toBeInTheDocument();
    } finally {
      consoleError.mockRestore();
    }
  });

  it('copies sanitized error details without query params', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const writeText = vi.fn().mockResolvedValue(undefined);
    const alertMock = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    function BrokenComponent(): never {
      throw new Error('Loading chunk 7 failed');
    }

    try {
      render(
        <MemoryRouter initialEntries={['/technical-chart?stock=000988.SZ&token=secret']}>
          <Routes>
            <Route
              element={(
                <Shell>
                  <RouteOutletBoundary />
                </Shell>
              )}
            >
              <Route path="/technical-chart" element={<BrokenComponent />} />
            </Route>
          </Routes>
        </MemoryRouter>,
      );

      await screen.findByRole('heading', { name: '页面加载失败' });
      fireEvent.click(screen.getByTestId('route-error-copy-details'));

      await waitFor(() => {
        expect(writeText).toHaveBeenCalled();
      });

      const payload = writeText.mock.calls[0]?.[0] as string;
      expect(payload).toContain('"pathname": "/technical-chart"');
      expect(payload).not.toContain('secret');
      expect(payload).not.toContain('token');
      expect(payload).not.toContain('000988');
    } finally {
      alertMock.mockRestore();
      consoleError.mockRestore();
    }
  });
});
