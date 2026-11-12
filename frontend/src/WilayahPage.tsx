import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadMapData, type ProvinceFeature } from './lib/map-data'
import { RISK_LEVELS } from './lib/risk'
import type { KabupatenProperties } from './types/geojson'

type ProvinceSortKey = 'level' | 'score' | 'very_high_count' | 'high_count' | 'risk_area_ha'
type KabupatenSortKey = 'level' | 'score' | 'cakupan_pct' | 'luas_terdampak_ha_max' | 'hotspot_72h'

const PROVINCE_SORT_OPTIONS: { key: ProvinceSortKey; label: string }[] = [
  { key: 'level', label: 'LEVEL RISIKO' },
  { key: 'score', label: 'SKOR' },
  { key: 'very_high_count', label: 'SANGAT TINGGI' },
  { key: 'high_count', label: 'TINGGI' },
  { key: 'risk_area_ha', label: 'LUAS AREA' },
]

const KABUPATEN_SORT_OPTIONS: { key: KabupatenSortKey; label: string }[] = [
  { key: 'level', label: 'LEVEL RISIKO' },
  { key: 'score', label: 'SKOR' },
  { key: 'cakupan_pct', label: 'CAKUPAN' },
  { key: 'luas_terdampak_ha_max', label: 'LUAS TERDAMPAK' },
  { key: 'hotspot_72h', label: 'HOTSPOT 72 JAM' },
]

function provinceSortValue(province: ProvinceFeature, key: ProvinceSortKey): number {
  const p = province.properties
  if (key === 'level') return p.level ?? 0
  if (key === 'score') return p.score ?? 0
  if (key === 'very_high_count') return p.very_high_count ?? 0
  if (key === 'high_count') return p.high_count ?? 0
  return p.risk_area_ha ?? 0
}

function kabupatenSortValue(row: KabupatenProperties, key: KabupatenSortKey): number {
  if (key === 'level') return row.level ?? 0
  if (key === 'score') return row.score ?? 0
  if (key === 'cakupan_pct') return row.cakupan_pct ?? 0
  if (key === 'luas_terdampak_ha_max') return row.luas_terdampak_ha_max ?? 0
  return row.hotspot_72h ?? 0
}

export function WilayahPage() {
  const [provinces, setProvinces] = useState<ProvinceFeature[] | null>(null)
  const [kabupaten, setKabupaten] = useState<KabupatenProperties[] | null>(null)
  const [kabupatenIsMock, setKabupatenIsMock] = useState(false)
  const [error, setError] = useState(false)

  const [provinceSortKey, setProvinceSortKey] = useState<ProvinceSortKey>('level')
  const [kabupatenSortKey, setKabupatenSortKey] = useState<KabupatenSortKey>('level')
  // null = tampilkan peringkat provinsi (tampilan awal).
  const [activeProvince, setActiveProvince] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    loadMapData('d1')
      .then((data) => {
        if (cancelled) return
        setProvinces(data.provinces.features)
        setKabupaten(data.kabupaten.features.map((feature) => feature.properties))
        setKabupatenIsMock(data.kabupatenMeta.isMock)
      })
      .catch(() => { if (!cancelled) setError(true) })
    return () => { cancelled = true }
  }, [])

  const rankedProvinces = useMemo(() => {
    if (!provinces) return []
    return [...provinces]
      .filter((province) => province.properties.has_data)
      .sort((a, b) => provinceSortValue(b, provinceSortKey) - provinceSortValue(a, provinceSortKey))
  }, [provinces, provinceSortKey])

  const maxProvinceArea = useMemo(
    () => rankedProvinces.reduce((max, p) => Math.max(max, p.properties.risk_area_ha ?? 0), 0),
    [rankedProvinces],
  )

  const rankedKabupaten = useMemo(() => {
    if (!kabupaten || !activeProvince) return []
    return kabupaten
      .filter((row) => row.provinsi === activeProvince && row.has_data)
      .sort((a, b) => kabupatenSortValue(b, kabupatenSortKey) - kabupatenSortValue(a, kabupatenSortKey))
  }, [kabupaten, activeProvince, kabupatenSortKey])

  const maxKabupatenArea = useMemo(
    () => rankedKabupaten.reduce((max, row) => Math.max(max, row.luas_terdampak_ha_max ?? 0), 0),
    [rankedKabupaten],
  )

  const kabupatenCountByProvince = useMemo(() => {
    const map = new Map<string, number>()
    if (!kabupaten) return map
    for (const row of kabupaten) {
      if (!row.has_data) continue
      map.set(row.provinsi, (map.get(row.provinsi) ?? 0) + 1)
    }
    return map
  }, [kabupaten])

  const openProvince = useCallback((province: string) => setActiveProvince(province), [])
  const backToProvinces = useCallback(() => setActiveProvince(null), [])

  const showingKabupaten = activeProvince !== null
  const sortOptions = showingKabupaten ? KABUPATEN_SORT_OPTIONS : PROVINCE_SORT_OPTIONS
  const sortValue = showingKabupaten ? kabupatenSortKey : provinceSortKey
  const onSortChange = (value: string) => {
    if (showingKabupaten) setKabupatenSortKey(value as KabupatenSortKey)
    else setProvinceSortKey(value as ProvinceSortKey)
  }

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
            <h1>
              {showingKabupaten
                ? <>Kabupaten/kota prioritas — {activeProvince}</>
                : 'Prioritas wilayah 24 jam ke depan'}
            </h1>
            <p className="wilayah-sub">
              {showingKabupaten
                ? 'Daftar peringkat kabupaten/kota di provinsi ini. Risiko tingkat kabupaten adalah agregasi sel 0,25°, bukan prediksi resolusi lebih halus.'
                : 'Daftar alternatif peta (F8). Diurutkan dari risiko tertinggi untuk membantu penentuan prioritas koordinasi.'}
            </p>
          </div>
          <label className="wilayah-sort">
            <span className="eyebrow">URUTKAN</span>
            <select value={String(sortValue)} onChange={(event) => onSortChange(event.target.value)}>
              {sortOptions.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
            </select>
          </label>
        </div>

        {showingKabupaten && (
          <div className="wilayah-breadcrumb">
            <button type="button" className="wilayah-back" onClick={backToProvinces}>← Semua provinsi</button>
            {kabupatenIsMock && (
              <span className="wilayah-mock-note">
                ANGKA KABUPATEN MASIH DATA CONTOH — belum hasil model, dipakai untuk menguji tampilan.
              </span>
            )}
          </div>
        )}

        {error && <p className="wilayah-empty">Data wilayah gagal dimuat. Coba muat ulang halaman.</p>}
        {!error && !provinces && <p className="wilayah-empty">Memuat data wilayah…</p>}

        {/* Mode kabupaten */}
        {!error && showingKabupaten && (
          <>
            {rankedKabupaten.length === 0 ? (
              <p className="wilayah-empty">Belum ada data kabupaten untuk provinsi ini.</p>
            ) : (
              <ol className="wilayah-list">
                {rankedKabupaten.map((row, index) => {
                  const level = (row.level ?? 1) as 1 | 2 | 3 | 4
                  const area = row.luas_terdampak_ha_max ?? 0
                  const barWidth = maxKabupatenArea > 0 ? Math.max(3, Math.round((area / maxKabupatenArea) * 100)) : 0
                  return (
                    <li className="wilayah-row" key={row.kode}>
                      <span className="wilayah-rank" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                      <div className="wilayah-name">
                        <strong>{row.kabupaten}</strong>
                        <span className="wilayah-island">{row.hotspot_72h ?? 0} hotspot 72 jam</span>
                      </div>
                      <div className="wilayah-metrics">
                        <div className="wilayah-metric">
                          <span className="eyebrow">SKOR</span>
                          <strong>{Math.round((row.score ?? 0) * 100)}%</strong>
                        </div>
                        <div className="wilayah-metric">
                          <span className="eyebrow">CAKUPAN</span>
                          <strong>{(row.cakupan_pct ?? 0).toFixed(1)}%</strong>
                        </div>
                        <div className="wilayah-metric">
                          <span className="eyebrow">SEL</span>
                          <strong>{row.n_sel ?? 0}</strong>
                        </div>
                        <div className="wilayah-metric wilayah-area">
                          <span className="eyebrow">LUAS TERDAMPAK</span>
                          <strong>
                            {(row.luas_terdampak_ha_min ?? 0).toLocaleString('id-ID')}–{area.toLocaleString('id-ID')} ha
                          </strong>
                          <span className="wilayah-area-track" aria-hidden="true"><i style={{ width: `${barWidth}%` }} /></span>
                        </div>
                      </div>
                      <span className={`level-chip risk-level-${level} wilayah-level`}>
                        <span className="level-bars" aria-hidden="true">{[1, 2, 3, 4].map((bar) => <i key={bar} className={bar <= level ? 'filled' : ''} />)}</span>
                        {RISK_LEVELS[level].label}
                      </span>
                      <a
                        className="wilayah-cta"
                        href={`/peta?kabupaten=${encodeURIComponent(row.kabupaten)}`}
                        aria-label={`Lihat ${row.kabupaten} di peta`}
                      >LIHAT PETA</a>
                    </li>
                  )
                })}
              </ol>
            )}
          </>
        )}

        {/* Mode provinsi (tampilan awal) */}
        {!error && !showingKabupaten && provinces && rankedProvinces.length === 0 && (
          <p className="wilayah-empty">Belum ada data risiko untuk periode ini.</p>
        )}
        {!error && !showingKabupaten && rankedProvinces.length > 0 && (
          <ol className="wilayah-list">
            {rankedProvinces.map((province, index) => {
              const p = province.properties
              const level = (p.level ?? 1) as 1 | 2 | 3 | 4
              const riskAreaHa = p.risk_area_ha ?? 0
              const barWidth = maxProvinceArea > 0 ? Math.max(3, Math.round((riskAreaHa / maxProvinceArea) * 100)) : 0
              const kabCount = kabupatenCountByProvince.get(p.province) ?? 0
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
                  <div className="wilayah-actions">
                    <button
                      type="button"
                      className="wilayah-drill"
                      onClick={() => openProvince(p.province)}
                      aria-label={`Lihat kabupaten di ${p.province}`}
                      disabled={kabCount === 0}
                    >
                      KABUPATEN{kabCount > 0 ? ` (${kabCount})` : ''}
                    </button>
                    <a className="wilayah-cta" href={`/peta?provinsi=${encodeURIComponent(p.province)}`} aria-label={`Lihat ${p.province} di peta`}>LIHAT PETA</a>
                  </div>
                </li>
              )
            })}
          </ol>
        )}
      </section>
    </main>
  )
}
