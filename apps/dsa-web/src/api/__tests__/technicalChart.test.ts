import { describe, expect, it } from 'vitest';
import {
  buildTechnicalChartHref,
  parseTechnicalChartDays,
  parseTechnicalChartIndicators,
  parseTechnicalChartPeriod,
  TECHNICAL_CHART_DEFAULT_DAYS,
  TECHNICAL_CHART_DEFAULT_INDICATORS,
  TECHNICAL_CHART_DEFAULT_PERIOD,
} from '../technicalChart';

describe('technicalChart query helpers', () => {
  it('accepts only allowed days values', () => {
    expect(parseTechnicalChartDays('60')).toBe(60);
    expect(parseTechnicalChartDays('120')).toBe(120);
    expect(parseTechnicalChartDays('250')).toBe(250);
    expect(parseTechnicalChartDays('90')).toBe(TECHNICAL_CHART_DEFAULT_DAYS);
    expect(parseTechnicalChartDays(null)).toBe(TECHNICAL_CHART_DEFAULT_DAYS);
  });

  it('accepts daily/weekly/monthly and falls back to daily', () => {
    expect(parseTechnicalChartPeriod('weekly')).toBe('weekly');
    expect(parseTechnicalChartPeriod('monthly')).toBe('monthly');
    expect(parseTechnicalChartPeriod('daily')).toBe('daily');
    expect(parseTechnicalChartPeriod('quarterly')).toBe(TECHNICAL_CHART_DEFAULT_PERIOD);
    expect(parseTechnicalChartPeriod(null)).toBe(TECHNICAL_CHART_DEFAULT_PERIOD);
  });

  it('builds cross-page href with canonical stock only by default', () => {
    expect(buildTechnicalChartHref({ stock: '600519' })).toBe('/technical-chart?stock=600519');
    expect(buildTechnicalChartHref({
      stock: '600519',
      period: 'weekly',
      days: 120,
      indicators: 'ma,volume',
    })).toBe('/technical-chart?stock=600519&period=weekly&days=120&indicators=ma%2Cvolume');
  });

  it('filters unknown indicators and falls back to the PC default set', () => {
    expect(parseTechnicalChartIndicators('ma,foo,rsi')).toBe('ma,rsi');
    expect(parseTechnicalChartIndicators('foo,bar')).toBe(TECHNICAL_CHART_DEFAULT_INDICATORS);
    expect(parseTechnicalChartIndicators(null)).toBe(TECHNICAL_CHART_DEFAULT_INDICATORS);
    expect(TECHNICAL_CHART_DEFAULT_INDICATORS).toContain('macd');
    expect(TECHNICAL_CHART_DEFAULT_INDICATORS).not.toContain('kdj');
  });
});
