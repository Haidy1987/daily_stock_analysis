import { lazy, type ComponentType, type LazyExoticComponent } from 'react';

const CHUNK_RETRY_PREFIX = 'dsa:chunk-retry:';

const CHUNK_ERROR_PATTERNS = [
  /ChunkLoadError/i,
  /Loading chunk [\d]+ failed/i,
  /Loading CSS chunk [\d]+ failed/i,
  /Failed to fetch dynamically imported module/i,
  /Importing a module script failed/i,
  /error loading dynamically imported module/i,
  /Unable to preload CSS/i,
];

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  return String(error);
}

/** Detect dynamic import / chunk load failures across common browsers. */
export function isChunkLoadError(error: unknown): boolean {
  const message = getErrorMessage(error);
  const name = error instanceof Error ? error.name : '';
  if (name === 'ChunkLoadError') {
    return true;
  }
  return CHUNK_ERROR_PATTERNS.some((pattern) => pattern.test(message));
}

function buildChunkRetryKey(moduleId: string, pathname: string): string {
  return `${CHUNK_RETRY_PREFIX}${moduleId}:${pathname}`;
}

function readSessionStorage(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeSessionStorage(key: string, value: string): void {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    // Ignore quota / privacy mode failures.
  }
}

function removeSessionStorage(key: string): void {
  try {
    sessionStorage.removeItem(key);
  } catch {
    // Ignore storage failures.
  }
}

function getCurrentPathname(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  return window.location.pathname;
}

function reloadPage(): void {
  if (typeof window !== 'undefined') {
    window.location.reload();
  }
}

function handleChunkLoadFailure(moduleId: string): never {
  const pathname = getCurrentPathname();
  const retryKey = buildChunkRetryKey(moduleId, pathname);
  const alreadyRetried = readSessionStorage(retryKey) === '1';

  if (!alreadyRetried) {
    writeSessionStorage(retryKey, '1');
    reloadPage();
    // Return a never-resolving promise while the page reloads.
    return new Promise<{ default: ComponentType<Record<string, unknown>> }>(() => undefined) as never;
  }

  removeSessionStorage(retryKey);
  throw new Error(`Chunk load failed after retry for ${moduleId}`);
}

/**
 * React.lazy wrapper that reloads once per session when a stale chunk fails to load.
 */
export function lazyWithRetry<T extends ComponentType<Record<string, unknown>>>(
  factory: () => Promise<{ default: T }>,
  moduleId: string,
): LazyExoticComponent<T> {
  return lazy(async () => {
    const pathname = getCurrentPathname();
    const retryKey = buildChunkRetryKey(moduleId, pathname);

    try {
      const module = await factory();
      removeSessionStorage(retryKey);
      return module;
    } catch (error) {
      if (isChunkLoadError(error)) {
        return handleChunkLoadFailure(moduleId);
      }
      throw error;
    }
  });
}
