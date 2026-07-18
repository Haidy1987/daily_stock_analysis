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
  ma30: string;
  ma60: string;
  ma90: string;
  ma120: string;
  ma250: string;
  bollUpper: string;
  bollMid: string;
  bollLower: string;
  support: string;
  resistance: string;
  markHigh: string;
  markLow: string;
};

const FALLBACK: TechnicalChartThemeColors = {
  up: 'hsl(0, 88%, 62%)',
  down: 'hsl(149, 100%, 42%)',
  text: 'hsl(210, 40%, 96%)',
  muted: 'hsl(215, 20%, 65%)',
  border: 'hsl(217, 19%, 27%)',
  background: 'transparent',
  tooltipBg: 'hsla(222, 47%, 11%, 0.92)',
  ma5: 'hsl(199, 89%, 48%)',
  ma10: 'hsl(271, 81%, 66%)',
  ma20: 'hsl(38, 92%, 50%)',
  ma30: 'hsl(48, 96%, 53%)',
  ma60: 'hsl(217, 91%, 60%)',
  ma90: 'hsl(330, 81%, 60%)',
  ma120: 'hsl(172, 66%, 50%)',
  ma250: 'hsl(215, 20%, 65%)',
  bollUpper: 'hsl(38, 92%, 50%)',
  bollMid: 'hsl(271, 81%, 66%)',
  bollLower: 'hsl(199, 89%, 48%)',
  support: 'hsl(149, 100%, 42%)',
  resistance: 'hsl(0, 88%, 62%)',
  markHigh: 'hsl(0, 88%, 62%)',
  markLow: 'hsl(149, 100%, 42%)',
};

const SPACE_HSL_PATTERN = /^hsla?\(\s*([\d.]+)\s+([\d.]+%)\s+([\d.]+%)(?:\s*\/\s*([\d.]+%?))?\s*\)$/i;
const CHANNEL_HSL_PATTERN = /^([\d.]+)\s+([\d.]+%)\s+([\d.]+%)$/;

/** Normalize CSS colors for Canvas renderers that reject CSS Color 4 space syntax. */
export function normalizeColorForCanvas(color: string): string {
  const value = color.trim();
  if (!value || value === 'transparent') {
    return value || 'transparent';
  }
  if (value.startsWith('#') || value.startsWith('rgb')) {
    return value;
  }

  const spaceMatch = value.match(SPACE_HSL_PATTERN);
  if (spaceMatch) {
    const [, h, s, l, alpha] = spaceMatch;
    if (alpha != null) {
      const normalizedAlpha = alpha.endsWith('%')
        ? (Number.parseFloat(alpha) / 100).toString()
        : alpha;
      return `hsla(${h}, ${s}, ${l}, ${normalizedAlpha})`;
    }
    return `hsl(${h}, ${s}, ${l})`;
  }

  const channelMatch = value.match(CHANNEL_HSL_PATTERN);
  if (channelMatch) {
    const [, h, s, l] = channelMatch;
    return `hsl(${h}, ${s}, ${l})`;
  }

  if (value.startsWith('hsl(') || value.startsWith('hsla(')) {
    return value;
  }

  return value;
}

function toCssColor(raw: string, fallback: string): string {
  const value = raw.trim();
  if (!value) {
    return normalizeColorForCanvas(fallback);
  }
  if (
    value.startsWith('#')
    || value.startsWith('rgb')
    || value.startsWith('hsl')
    || value.startsWith('var(')
  ) {
    return normalizeColorForCanvas(value);
  }
  return normalizeColorForCanvas(`hsl(${value})`);
}

function readCssColor(styles: CSSStyleDeclaration, name: string, fallback: string): string {
  return toCssColor(styles.getPropertyValue(name), fallback);
}

function normalizeThemeColors(colors: TechnicalChartThemeColors): TechnicalChartThemeColors {
  return {
    up: normalizeColorForCanvas(colors.up),
    down: normalizeColorForCanvas(colors.down),
    text: normalizeColorForCanvas(colors.text),
    muted: normalizeColorForCanvas(colors.muted),
    border: normalizeColorForCanvas(colors.border),
    background: normalizeColorForCanvas(colors.background),
    tooltipBg: normalizeColorForCanvas(colors.tooltipBg),
    ma5: normalizeColorForCanvas(colors.ma5),
    ma10: normalizeColorForCanvas(colors.ma10),
    ma20: normalizeColorForCanvas(colors.ma20),
    ma30: normalizeColorForCanvas(colors.ma30),
    ma60: normalizeColorForCanvas(colors.ma60),
    ma90: normalizeColorForCanvas(colors.ma90),
    ma120: normalizeColorForCanvas(colors.ma120),
    ma250: normalizeColorForCanvas(colors.ma250),
    bollUpper: normalizeColorForCanvas(colors.bollUpper),
    bollMid: normalizeColorForCanvas(colors.bollMid),
    bollLower: normalizeColorForCanvas(colors.bollLower),
    support: normalizeColorForCanvas(colors.support),
    resistance: normalizeColorForCanvas(colors.resistance),
    markHigh: normalizeColorForCanvas(colors.markHigh),
    markLow: normalizeColorForCanvas(colors.markLow),
  };
}

/** Resolve ECharts palette from current document theme tokens. */
export function readTechnicalChartThemeColors(
  root: Element | null | undefined = typeof document !== 'undefined' ? document.documentElement : null,
): TechnicalChartThemeColors {
  if (!root || typeof getComputedStyle !== 'function') {
    return normalizeThemeColors({ ...FALLBACK });
  }
  const styles = getComputedStyle(root);
  return normalizeThemeColors({
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
    ma30: FALLBACK.ma30,
    ma60: FALLBACK.ma60,
    ma90: FALLBACK.ma90,
    ma120: FALLBACK.ma120,
    ma250: FALLBACK.ma250,
    bollUpper: readCssColor(styles, '--color-warning', FALLBACK.bollUpper),
    bollMid: readCssColor(styles, '--color-purple', FALLBACK.bollMid),
    bollLower: readCssColor(styles, '--color-cyan', FALLBACK.bollLower),
    support: readCssColor(styles, '--home-price-down', FALLBACK.support),
    resistance: readCssColor(styles, '--home-price-up', FALLBACK.resistance),
    markHigh: readCssColor(styles, '--home-price-up', FALLBACK.markHigh),
    markLow: readCssColor(styles, '--home-price-down', FALLBACK.markLow),
  });
}
