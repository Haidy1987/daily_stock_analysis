import type React from 'react';
import { Component, Suspense } from 'react';
import type { ErrorInfo } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import { WEB_BUILD_INFO } from '../../utils/constants';
import {
  classifyRouteError,
  createRouteErrorReport,
  createShortErrorId,
  getRouteErrorDescriptionKey,
  summarizeBrowser,
  type RouteErrorCategory,
} from '../../utils/routeErrorDiagnostics';

type PageLoadingFallbackProps = {
  fullPage?: boolean;
};

export const PageLoadingFallback: React.FC<PageLoadingFallbackProps> = ({ fullPage = true }) => (
  <div
    className={
      fullPage
        ? 'flex min-h-screen items-center justify-center bg-base'
        : 'flex min-h-[60vh] items-center justify-center'
    }
  >
    <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
  </div>
);

type RouteErrorBoundaryProps = {
  children: React.ReactNode;
  resetKey: string;
  fullPage: boolean;
  pathname: string;
  text: {
    title: string;
    descriptions: Record<RouteErrorCategory, string>;
    reload: string;
    backHome: string;
    copyDetails: string;
    copySuccess: string;
    errorId: string;
  };
};

type RouteErrorBoundaryState = {
  hasError: boolean;
  category?: RouteErrorCategory;
  errorId?: string;
};

class RouteErrorBoundary extends Component<RouteErrorBoundaryProps, RouteErrorBoundaryState> {
  override state: RouteErrorBoundaryState = {
    hasError: false,
  };

  static getDerivedStateFromError(error: unknown): RouteErrorBoundaryState {
    return {
      hasError: true,
      category: classifyRouteError(error),
      errorId: createShortErrorId(),
    };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Route page failed to render or load', error, errorInfo);
  }

  override componentDidUpdate(prevProps: RouteErrorBoundaryProps) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, category: undefined, errorId: undefined });
    }
  }

  private handleCopyDetails = async () => {
    const { category, errorId } = this.state;
    if (!category || !errorId) {
      return;
    }

    const report = createRouteErrorReport({
      errorId,
      category,
      pathname: this.props.pathname,
      buildInfo: WEB_BUILD_INFO,
      browserSummary: summarizeBrowser(),
    });

    try {
      await navigator.clipboard.writeText(report);
      window.alert(this.props.text.copySuccess);
    } catch {
      window.prompt(this.props.text.copyDetails, report);
    }
  };

  override render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    const category = this.state.category ?? 'unknown_error';
    const description = this.props.text.descriptions[category];

    return (
      <div
        className={
          this.props.fullPage
            ? 'flex min-h-screen items-center justify-center bg-base px-4'
            : 'flex min-h-[60vh] items-center justify-center px-2 py-8'
        }
      >
        <div className="w-full max-w-md rounded-2xl border border-border bg-card/94 p-6 text-center shadow-soft-card">
          <h1 className="text-xl font-semibold text-foreground">{this.props.text.title}</h1>
          <p
            className="mt-3 text-sm leading-6 text-secondary-text"
            data-route-error-category={category}
          >
            {description}
          </p>
          {this.state.errorId ? (
            <p className="mt-2 text-xs text-secondary-text">
              {this.props.text.errorId.replace('{id}', this.state.errorId)}
            </p>
          ) : null}
          <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:justify-center">
            <button
              type="button"
              className="btn-primary"
              onClick={() => window.location.reload()}
            >
              {this.props.text.reload}
            </button>
            <button
              type="button"
              className="rounded-xl border border-border/70 bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-hover"
              onClick={() => window.location.assign('/')}
            >
              {this.props.text.backHome}
            </button>
            <button
              type="button"
              className="rounded-xl border border-border/70 bg-card px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-hover"
              data-testid="route-error-copy-details"
              onClick={() => void this.handleCopyDetails()}
            >
              {this.props.text.copyDetails}
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export const RouteBoundary: React.FC<{ children: React.ReactNode; fullPage?: boolean }> = ({
  children,
  fullPage = true,
}) => {
  const location = useLocation();
  const { t } = useUiLanguage();
  const resetKey = `${location.pathname}${location.search}`;

  return (
    <RouteErrorBoundary
      resetKey={resetKey}
      fullPage={fullPage}
      pathname={location.pathname}
      text={{
        title: t('routeError.title'),
        descriptions: {
          chunk_load_error: t(getRouteErrorDescriptionKey('chunk_load_error')),
          render_error: t(getRouteErrorDescriptionKey('render_error')),
          unknown_error: t(getRouteErrorDescriptionKey('unknown_error')),
        },
        reload: t('routeError.reload'),
        backHome: t('routeError.backHome'),
        copyDetails: t('routeError.copyDetails'),
        copySuccess: t('routeError.copySuccess'),
        errorId: t('routeError.errorId'),
      }}
    >
      <Suspense fallback={<PageLoadingFallback fullPage={fullPage} />}>{children}</Suspense>
    </RouteErrorBoundary>
  );
};

export const RouteOutletBoundary: React.FC = () => (
  <RouteBoundary fullPage={false}>
    <Outlet />
  </RouteBoundary>
);

export const StandaloneRouteBoundary: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <RouteBoundary fullPage>
    {children}
  </RouteBoundary>
);
