import type { RiskLevel } from '../types/geojson'

export const RISK_LEVELS = {
  1: { label: 'Rendah', bars: 1, colorToken: '--risk-low', inkToken: '--risk-low-ink', opacity: 0.3, threshold: '< 10%' },
  2: { label: 'Sedang', bars: 2, colorToken: '--risk-medium', inkToken: '--risk-medium-ink', opacity: 0.5, threshold: '10-25%' },
  3: { label: 'Tinggi', bars: 3, colorToken: '--risk-high', inkToken: '--risk-high-ink', opacity: 0.75, threshold: '25-50%' },
  4: { label: 'Sangat tinggi', bars: 4, colorToken: '--risk-very-high', inkToken: '--risk-very-high-ink', opacity: 0.95, threshold: '50%+' },
} as const

export function levelFromScore(score: number): RiskLevel {
  if (score < 0.1) return 1
  if (score < 0.25) return 2
  if (score < 0.5) return 3
  return 4
}

export function riskColor(level: RiskLevel, ink = false): string {
  const token = ink ? RISK_LEVELS[level].inkToken : RISK_LEVELS[level].colorToken
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim()
}
