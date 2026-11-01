import { useEffect, useMemo, useState } from 'react'
import { loadMapData, type ProvinceFeature } from './lib/map-data'
import { RISK_LEVELS } from './lib/risk'

type SortKey = 'level' | 'score' | 'very_high_count' | 'high_count' | 'risk_area_ha'

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'level', label: 'LEVEL RISIKO' },
  { key: 'score', label: 'SKOR' },
  { key: 'very_high_count', label: 'SANGAT TINGGI' },
  { key: 'high_count', label: 'TINGGI' },
  { key: 'risk_area_ha', label: 'LUAS AREA' },
]

function provinceSortValue(province: ProvinceFeature, key: SortKey): number {
  const p = province.properties
  if (key === 'level') return p.level ?? 0
  if (key === 'score') return p.score ?? 0
  if (key === 'very_high_count') return p.very_high_count ?? 0
  if (key === 'high_count') return p.high_count ?? 0
  return p.risk_area_ha ?? 0
}

export function WilayahPage() {
  const [provinces, setProvinces] = useState<ProvinceFeature[] | null>(null)
  const [error, setError] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('level')

  useEffect(() => {
    let cancelled = false
    loadMapData('d1')
      .then((data) => {
        if (cancelled) return
        setProvinces(data.provinces.features)
      })
      .catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [])

  const ranked = useMemo(() => {
    if (!provinces) return []
    return [...provinces]
      .filter((province) => province.properties.has_data)
      .sort((a, b) => provinceSortValue(b, sortKey) - provinceSortValue(a, sortKey))
  }, [provinces, sortKey])

  const maxArea = useMemo(() => ranked.reduce((max, p) => Math.max(max, p.properties.risk_area_ha ?? 0), 0), [ranked])

  return (
    <main className="dashboard wilayah-page">
      <header className="topbar">
        <a className="wordmark" href="/" aria-label="HOTSPOT.ID, beranda"><span className="wordmark-mark" aria-hidden="true" /><span>HOTSPOT.ID</span></a>
        <nav className="main-nav" aria-label="Navigasi utama">
          <a className="nav-tab" href="/">Beranda</a>
          <a className="nav-tab" href="/peta">Peta</a>
          <a className="nav-tab nav-active" href="/wilayah" aria-current="page">Wilayah</a>
          <a className="nav-tab" href="/riwayat">Riwayat</a>
          <a className="nav-tab" href="/metode">Metode</a>
        </nav>
        <span className="sample-label method-sample">Data contoh</span>
      </header>

      <section className="wilayah-body" aria-label="Peringkat wilayah berisiko karhutla">
        <div className="wilayah-head">
          <div>
            <p className="eyebrow">PERINGKAT WILAYAH</p>
            <h1>Prioritas wilayah 24 jam ke depan</h1>
            <p className="wilayah-sub">Daftar alternatif peta (F8). Diurutkan dari risiko tertinggi untuk membantu penentuan prioritas koordinasi.</p>
          </div>
          <label className="wilayah-sort">
            <span className="eyebrow">URUTKAN</span>
            <select value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
              {SORT_OPTIONS.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
            </select>
          </label>
        </div>

        {error && <p className="wilayah-empty">Data wilayah gagal dimuat. Coba muat ulang halaman.</p>}
        {!error && !provinces && <p className="wilayah-empty">Memuat data wilayah…</p>}
        {!error && provinces && ranked.length === 0 && <p className="wilayah-empty">Belum ada data risiko untuk periode ini.</p>}

        {!error && ranked.length > 0 && (
          <ol className="wilayah-list">
            {ranked.map((province, index) => {
              const p = province.properties
              const level = (p.level ?? 1) as 1 | 2 | 3 | 4
              const riskAreaHa = p.risk_area_ha ?? 0
              const barWidth = maxArea > 0 ? Math.max(3, Math.round((riskAreaHa / maxArea) * 100)) : 0
              return (
                <li className="wilayah-row" key={p.shape_id}>
                  <span className="wilayah-rank" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                  <div className="wilayah-name">
                    <strong>{p.province}</strong>
                    <span className="wilayah-island">{p.island ?? '—'}</span>
                  </div>
                  <div className="wilayah-metrics">
                    <div className="wilayah-metric">
                      <span className="eyebrow">SKOR</span>
                      <strong>{Math.round((p.score ?? 0) * 100)}%</strong>
                    </div>
                    <div className="wilayah-metric">
                      <span className="eyebrow">TINGGI</span>
                      <strong>{p.high_count ?? 0}</strong>
                    </div>
                    <div className="wilayah-metric">
                      <span className="eyebrow">SANGAT TINGGI</span>
                      <strong>{p.very_high_count ?? 0}</strong>
                    </div>
                    <div className="wilayah-metric wilayah-area">
                      <span className="eyebrow">LUAS AREA BERISIKO</span>
                      <strong>{riskAreaHa.toLocaleString('id-ID')} ha</strong>
                      <span className="wilayah-area-track" aria-hidden="true"><i style={{ width: `${barWidth}%` }} /></span>
                    </div>
                  </div>
                  <span className={`level-chip risk-level-${level} wilayah-level`}>
                    <span className="level-bars" aria-hidden="true">{[1, 2, 3, 4].map((bar) => <i key={bar} className={bar <= level ? 'filled' : ''} />)}</span>
                    {RISK_LEVELS[level].label}
                  </span>
                  <a className="wilayah-cta" href={`/peta?provinsi=${encodeURIComponent(p.province)}`} aria-label={`Lihat ${p.province} di peta`}>LIHAT PETA</a>
                </li>
              )
            })}
          </ol>
        )}
      </section>
    </main>
  )
}
