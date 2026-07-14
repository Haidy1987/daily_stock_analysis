export type TechnicalChartThemeColors = {
  up: string;
  down: string;
  text: string;
  muted: string;
  border: string;
  background: string;
  tooltipBg: string;
  ma5: string;
  ma10: string;
  ma20: string;
  bollUpper: string;
  bollMid: string;
  bollLower: string;
  support: string;
  resistance: string;
  markHigh: string;
  markLow: string;
};

const FALLBACK: TechnicalChartThemeColors = {
  up: 'hsl(0 88% 62%)',
  down: 'hsl(149 100% 42%)',
  text: 'hsl(210 40% 96%)',
  muted: 'hsl(215 20% 65%)',
  border: 'hsl(217 19% 27%)',
  background: 'transparent',
  tooltipBg: 'hsla(222 47% 11% / 0.92)',
  ma5: 'hsl(199 89% 48%)',
  ma10: 'hsl(271 81% 66%)',
  ma20: 'hsl(38 92% 50%)',
  bollUpper: 'hsl(215 20% 65%)',
  bollMid: 'hsl(210 40% 78%)',
  bollLower: 'hsl(215 20% 65%)',
  support: 'hsl(149 100% 42%)',
  resistance: 'hsl(0 88% 62%)',
  markHigh: 'hsl(0 88% 62%)',
  markLow: 'hsl(149 100% 42%)',
};

function toCssColor(raw: string, fallback: string): string {
  const value = raw.trim();
  if (!value) return fallback;
  if (
    value.startsWith('#')
    || value.startsWith('rgb')
    || value.startsWith('hsl')
    || value.startsWith('var(')
  ) {
    return value;
  }
  // Tailwind token channels are stored as "H S% L%".
  return `hsl(${value})`;
}

function readCssColor(styles: CSSStyleDeclaration, name: string, fallback: string): string {
  return toCssColor(styles.getPropertyValue(name), fallback);
}

/** Resolve ECharts palette from current document theme tokens. */
export function readTechnicalChartThemeColors(
  root: Element | null | undefined = typeof document !== 'undefined' ? document.documentElement : null,
): TechnicalChartThemeColors {
  if (!root || typeof getComputedStyle !== 'function') {
    return { ...FALLBACK };
  }
  const styles = getComputedStyle(root);
  return {
    up: readCssColor(styles, '--home-price-up', FALLBACK.up),
    down: readCssColor(styles, '--home-price-down', FALLBACK.down),
    text: readCssColor(styles, '--foreground', FALLBACK.text),
    muted: readCssColor(styles, '--secondary-text', FALLBACK.muted),
    border: readCssColor(styles, '--border', FALLBACK.border),
    background: 'transparent',
    tooltipBg: readCssColor(styles, '--card', FALLBACK.tooltipBg),
    ma5: readCssColor(styles, '--color-cyan', FALLBACK.ma5),
    ma10: FALLBACK.ma10,
    ma20: FALLBACK.ma20,
    bollUpper: readCssColor(styles, '--muted-foreground', FALLBACK.bollUpper),
    bollMid: readCssColor(styles, '--foreground', FALLBACK.bollMid),
    bollLower: readCssColor(styles, '--muted-foreground', FALLBACK.bollLower),
    support: readCssColor(styles, '--home-price-down', FALLBACK.support),
    resistance: readCssColor(styles, '--home-price-up', FALLBACK.resistance),
    markHigh: readCssColor(styles, '--home-price-up', FALLBACK.markHigh),
    markLow: readCssColor(styles, '--home-price-down', FALLBACK.markLow),
  };
}
