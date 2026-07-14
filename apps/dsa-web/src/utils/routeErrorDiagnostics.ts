import { isChunkLoadError } from './lazyWithRetry';
import type { WebBuildInfo } from './constants';

export type RouteErrorCategory = 'chunk_load_error' | 'render_error' | 'unknown_error';

const REACT_RENDER_ERROR_PATTERNS = [
  /Minified React error/i,
  /Invalid hook call/i,
  /Objects are not valid as a React child/i,
  /Cannot read properties of/i,
  /Cannot destructure property/i,
  /Element type is invalid/i,
  /Rendered more hooks than during the previous render/i,
];

export function classifyRouteError(error: unknown): RouteErrorCategory {
  if (isChunkLoadError(error)) {
    return 'chunk_load_error';
  }

  const message = error instanceof Error ? error.message : String(error);
  if (REACT_RENDER_ERROR_PATTERNS.some((pattern) => pattern.test(message))) {
    return 'render_error';
  }

  if (error instanceof Error && error.name && error.name !== 'Error') {
    return 'render_error';
  }

  return 'unknown_error';
}

export function createShortErrorId(now: Date = new Date()): string {
  const datePart = [
    now.getUTCFullYear(),
    String(now.getUTCMonth() + 1).padStart(2, '0'),
    String(now.getUTCDate()).padStart(2, '0'),
  ].join('');
  const randomPart = Math.random().toString(36).slice(2, 6).toUpperCase();
  return `ERR-${datePart}-${randomPart}`;
}

export function summarizeBrowser(): string {
  if (typeof navigator === 'undefined') {
    return 'unknown';
  }

  const platform = navigator.platform || 'unknown-platform';
  const ua = navigator.userAgent || '';
  if (/Safari/i.test(ua) && !/Chrome|Chromium|Edg/i.test(ua)) {
    return `Safari · ${platform}`;
  }
  if (/Edg/i.test(ua)) {
    return `Edge · ${platform}`;
  }
  if (/Chrome/i.test(ua)) {
    return `Chrome · ${platform}`;
  }
  if (/Firefox/i.test(ua)) {
    return `Firefox · ${platform}`;
  }
  return `${platform}`;
}

export type RouteErrorReportInput = {
  errorId: string;
  category: RouteErrorCategory;
  pathname: string;
  buildInfo: Pick<WebBuildInfo, 'version' | 'buildId'>;
  browserSummary?: string;
  timestamp?: string;
};

export function createRouteErrorReport(input: RouteErrorReportInput): string {
  const payload = {
    errorId: input.errorId,
    category: input.category,
    pathname: input.pathname,
    buildVersion: input.buildInfo.version,
    buildId: input.buildInfo.buildId,
    browser: input.browserSummary ?? summarizeBrowser(),
    timestamp: input.timestamp ?? new Date().toISOString(),
  };
  return JSON.stringify(payload, null, 2);
}

export function getRouteErrorDescriptionKey(category: RouteErrorCategory):
  'routeError.chunkDescription' | 'routeError.renderDescription' | 'routeError.unknownDescription' {
  if (category === 'chunk_load_error') {
    return 'routeError.chunkDescription';
  }
  if (category === 'render_error') {
    return 'routeError.renderDescription';
  }
  return 'routeError.unknownDescription';
}
