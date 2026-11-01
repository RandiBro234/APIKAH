import { RISK_LEVELS } from './lib/risk'
import type { RiskLevel } from './types/geojson'
import './styles/legend.css'

const LEVELS: RiskLevel[] = [1, 2, 3, 4]

// Legenda level risiko dipakai bersama oleh beranda dan dashboard.
export function RiskLegend({ showHotspot = false }: { showHotspot?: boolean }) {
  return (
    <ul className="risk-legend">
      {LEVELS.map((level) => (
        <li className="risk-legend-item" key={level}>
          <span className="risk-legend-swatch" style={{ background: `var(${RISK_LEVELS[level].colorToken})` }}>
            <span className="level-bars" aria-hidden="true">
              {LEVELS.map((bar) => <i key={bar} className={bar <= level ? 'filled' : ''} />)}
            </span>
          </span>
          <span className="risk-legend-text">{RISK_LEVELS[level].label} {RISK_LEVELS[level].threshold.replace('< ', '<')}</span>
        </li>
      ))}
      {showHotspot && (
        <li className="risk-legend-item">
          <span className="risk-legend-swatch risk-legend-hotspot" aria-hidden="true" />
          <span className="risk-legend-text">Hotspot 72 jam</span>
        </li>
      )}
    </ul>
  )
}
