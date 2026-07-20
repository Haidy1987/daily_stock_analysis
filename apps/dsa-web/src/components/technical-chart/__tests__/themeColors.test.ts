import { describe, expect, it } from 'vitest';
import { normalizeColorForCanvas, readTechnicalChartThemeColors } from '../themeColors';

describe('normalizeColorForCanvas', () => {
  it('converts CSS Color 4 space HSL syntax to legacy comma syntax', () => {
    expect(normalizeColorForCanvas('hsl(0 88% 62%)')).toBe('hsl(0, 88%, 62%)');
    expect(normalizeColorForCanvas('hsla(222 47% 11% / 0.92)')).toBe('hsla(222, 47%, 11%, 0.92)');
  });

  it('converts channel-only tokens to hsl()', () => {
    expect(normalizeColorForCanvas('210 40% 96%')).toBe('hsl(210, 40%, 96%)');
  });

  it('preserves hex and rgb values', () => {
    expect(normalizeColorForCanvas('#ff0000')).toBe('#ff0000');
    expect(normalizeColorForCanvas('rgb(1, 2, 3)')).toBe('rgb(1, 2, 3)');
  });
});

describe('readTechnicalChartThemeColors', () => {
  it('returns fallback colors when document is unavailable', () => {
    const colors = readTechnicalChartThemeColors(null);
    expect(colors.up).toContain('hsl');
    expect(colors.down).toContain('hsl');
    expect(colors.ma5).toBeTruthy();
  });

  it('reads theme variables from a style owner', () => {
    const host = document.createElement('div');
    host.style.setProperty('--home-price-up', 'hsl(0 90% 50%)');
    host.style.setProperty('--home-price-down', 'hsl(140 90% 40%)');
    host.style.setProperty('--foreground', '210 40% 96%');
    host.style.setProperty('--secondary-text', '215 20% 65%');
    host.style.setProperty('--border', '217 19% 27%');
    host.style.setProperty('--card', '222 47% 11%');
    host.style.setProperty('--color-cyan', 'hsl(199 89% 48%)');
    host.style.setProperty('--muted-foreground', '215 20% 65%');
    document.body.appendChild(host);

    const colors = readTechnicalChartThemeColors(host);
    expect(colors.up).toBe('hsl(0, 90%, 50%)');
    expect(colors.down).toBe('hsl(140, 90%, 40%)');
    expect(colors.text).toBe('hsl(210, 40%, 96%)');
    host.remove();
  });
});
