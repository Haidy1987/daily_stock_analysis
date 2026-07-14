import { useEffect, useState } from 'react';

/** Match shell's `lg` breakpoint (1024px): narrow = mobile/tablet drawer layout. */
export const TECHNICAL_CHART_COMPACT_QUERY = '(max-width: 1023px)';

export function useMediaQuery(query: string, defaultValue = false): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return defaultValue;
    }
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return undefined;
    }
    const media = window.matchMedia(query);
    const onChange = () => setMatches(media.matches);
    onChange();
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

export function useIsCompactViewport(defaultValue = false): boolean {
  return useMediaQuery(TECHNICAL_CHART_COMPACT_QUERY, defaultValue);
}
