import { useEffect, useMemo, useState } from 'react'
import { loadMapData } from './lib/map-data'
import type { DataMeta, KabupatenRiskRecord } from './types/geojson'
import { riskColor, RISK_LEVELS } from './lib/risk'
import './PeringatanPage.css'

type WatchThreshold = 2 | 3 | 4

function formatProvinceName(name: string) {
  return name.replace(/([a-z])([A-Z])/g, '$1 $2')
}

function levelLabel(level: number) {
  return RISK_LEVELS[level as keyof typeof RISK_LEVELS]?.label ?? 'Belum tersedia'
}

function levelColor(level: number) {
  return riskColor(Math.max(1, Math.min(4, level)) as 1 | 2 | 3 | 4)
}

function formatUpdated(meta: DataMeta | null) {
  if (!meta) return 'Belum tersedia'
  return new Date(meta.generated_at).toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Jakarta' }) + ' WIB'
}

export function PeringatanPage() {
  const [threshold, setThreshold] = useState<WatchThreshold>(3)
  const [selectedProvince, setSelectedProvince] = useState('')
  const [selectedKabupaten, setSelectedKabupaten] = useState('')
  const [kabupatenRows, setKabupatenRows] = useState<KabupatenRiskRecord[]>([])
  const [riskFeatures, setRiskFeatures] = useState<import('./lib/map-data').RiskMapFeature[]>([])
  const [isMock, setIsMock] = useState(true)
  const [meta, setMeta] = useState<DataMeta | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    let active = true
    void loadMapData('d1').then((data) => {
      if (!active) return
      setKabupatenRows(data.kabupaten.features.map((feature) => ({
        kode: feature.properties.kode,
        kabupaten: feature.properties.kabupaten,
        provinsi: feature.properties.provinsi,
        has_data: feature.properties.has_data,
        level: feature.properties.level,
        score: feature.properties.score,
        hotspot_72h: feature.properties.hotspot_72h,
        unmatched: feature.properties.unmatched,
      })))
      setRiskFeatures(data.risk.features)
      setIsMock(data.kabupatenMeta.isMock || data.meta.is_sample)
      setMeta(data.meta)
      setState('ready')
    }).catch(() => {
      if (active) setState('error')
    })
    return () => { active = false }
  }, [])

  const provinceOptions = useMemo(() => [...new Set(kabupatenRows.map((row) => row.provinsi))].sort((a, b) => a.localeCompare(b, 'id')), [kabupatenRows])
  const kabupatenOptions = useMemo(() => kabupatenRows
    .filter((row) => row.provinsi === selectedProvince)
    .sort((a, b) => a.kabupaten.localeCompare(b.kabupaten, 'id')), [kabupatenRows, selectedProvince])
  const selectedRow = kabupatenRows.find((row) => row.kode === selectedKabupaten && row.provinsi === selectedProvince)
  const localRisk = useMemo(() => {
    if (!selectedRow) return null
    const provinceFeatures = riskFeatures.filter((feature) => feature.properties.province === selectedRow.provinsi)
    if (!provinceFeatures.length) return null
    const highest = provinceFeatures.reduce((best, feature) => feature.properties.level > best.properties.level ? feature : best)
    return { level: selectedRow.level ?? highest.properties.level, score: selectedRow.score ?? highest.properties.score, province: selectedRow.provinsi, drivers: highest.properties.drivers }
  }, [riskFeatures, selectedRow])
  const watched = selectedRow && (selectedRow.level ?? 0) >= threshold ? [selectedRow] : []

  return (
    <main className="dashboard alert-page">
      <header className="topbar">
        <a className="wordmark" href="/peta" aria-label="HOTSPOT.ID, kembali ke peta"><span className="wordmark-mark" aria-hidden="true" /><span>HOTSPOT.ID</span></a>
        <nav className="main-nav" aria-label="Navigasi utama">
          <a className="nav-tab" href="/">Beranda</a><a className="nav-tab" href="/peta">Peta</a><a className="nav-tab" href="/wilayah">Wilayah</a><a className="nav-tab nav-active" href="/peringatan" aria-current="page">Peringatan</a><a className="nav-tab" href="/riwayat">Riwayat</a>
        </nav>
        <span className="sample-label method-sample">Data contoh</span>
      </header>

      <section className="alert-content" aria-labelledby="alert-title">
        <div className="alert-intro">
          <span className="eyebrow">PEMANTAUAN WILAYAH</span>
          <h1 id="alert-title">Peringatan risiko munculnya hotspot</h1>
          <p>Pilih kabupaten/kota yang ingin dipantau dan batas level risikonya. Data kabupaten/kota saat ini masih contoh, bukan peringatan resmi.</p>
        </div>

        <section className="alert-status" aria-label="Status pemantauan">
          <div><span className="eyebrow">STATUS DATA</span><strong>{isMock ? 'DATA CONTOH KABUPATEN' : 'DATA OPERASIONAL'}</strong><span>Diperbarui {formatUpdated(meta)}</span></div>
          <div><span className="eyebrow">TELEGRAM</span><strong>Belum ditautkan</strong><span>Pengiriman otomatis belum aktif.</span></div>
        </section>

        <section className="alert-controls" aria-label="Filter pantauan">
          <div className="alert-horizon-note"><span className="eyebrow">PERIODE PERINGATAN</span><strong>Besok</strong></div>
          <label><span className="eyebrow">PROVINSI</span><select value={selectedProvince} onChange={(event) => { setSelectedProvince(event.target.value); setSelectedKabupaten('') }}><option value="">Pilih provinsi</option>{provinceOptions.map((province) => <option key={province} value={province}>{formatProvinceName(province)}</option>)}</select></label>
          <label><span className="eyebrow">KABUPATEN/KOTA</span><select value={selectedKabupaten} disabled={!selectedProvince} onChange={(event) => setSelectedKabupaten(event.target.value)}><option value="">{selectedProvince ? 'Pilih kabupaten/kota' : 'Pilih provinsi dulu'}</option>{kabupatenOptions.map((row) => <option key={row.kode} value={row.kode}>{formatProvinceName(row.kabupaten)}</option>)}</select></label>
          <label><span className="eyebrow">AMBANG PANTAU</span><select value={threshold} onChange={(event) => setThreshold(Number(event.target.value) as WatchThreshold)}><option value={2}>Sedang ke atas</option><option value={3}>Tinggi ke atas</option><option value={4}>Sangat tinggi</option></select></label>
        </section>

        <section className="alert-list-section" aria-labelledby="alert-list-title">
          <div className="alert-section-heading"><div><span className="eyebrow">DAFTAR PRIORITAS</span><h2 id="alert-list-title">Risiko besok di wilayah pilihan</h2></div><span className="alert-count">{state === 'ready' ? `${selectedRow ? 1 : 0} wilayah` : 'Memuat'}</span></div>
          {state === 'loading' && <p className="alert-empty">Memuat data risiko besok.</p>}
          {state === 'error' && <p className="alert-empty">Data risiko gagal dimuat. Muat ulang halaman untuk mencoba lagi.</p>}
          {state === 'ready' && !selectedRow && <p className="alert-empty">Pilih kabupaten/kota untuk melihat ringkasan pantauannya.</p>}
          {state === 'ready' && selectedRow && watched.length === 0 && <p className="alert-empty">{formatProvinceName(selectedRow.kabupaten)} berada di bawah ambang {levelLabel(threshold)}. Turunkan ambang untuk menampilkannya.</p>}
          {state === 'ready' && selectedRow && watched.length > 0 && <ol className="alert-list"><li className="alert-row" key={selectedRow.kode}><span className="alert-rank">01</span><div className="alert-name"><strong>{formatProvinceName(selectedRow.kabupaten)}, {formatProvinceName(selectedRow.provinsi)}</strong><span>{selectedRow.hotspot_72h ?? 0} hotspot 72 jam</span></div><span className="alert-level" style={{ background: levelColor(selectedRow.level ?? 1) }}>{levelLabel(selectedRow.level ?? 1)}</span><div className="alert-score"><span className="eyebrow">SKOR</span><strong>{Math.round((selectedRow.score ?? 0) * 100)}%</strong></div><a className="alert-link" href={`/peta#${selectedRow.provinsi.toLowerCase().replaceAll(' ', '-')}`}>Lihat provinsi</a></li></ol>}
          {state === 'ready' && selectedRow && isMock && <p className="alert-mock-note">Angka kabupaten/kota masih data contoh. Ringkasan ini belum merupakan prediksi operasional.</p>}
          {state === 'ready' && selectedRow && localRisk?.drivers.length ? <div className="alert-reason"><span className="eyebrow">FAKTOR RISIKO PROVINSI</span><p>{localRisk.drivers.join(' ')}</p><span>Faktor tersedia pada tingkat provinsi, belum tingkat kabupaten/kota.</span></div> : null}
        </section>

        <section className="alert-subscription" aria-labelledby="subscription-title">
          <div><span className="eyebrow">PENGATURAN NOTIFIKASI</span><h2 id="subscription-title">Pantau perubahan, bukan setiap polling</h2><p>{selectedRow ? `Wilayah dipilih: ${formatProvinceName(selectedRow.kabupaten)}, ${formatProvinceName(selectedRow.provinsi)}.` : 'Pilih kabupaten/kota di atas untuk menyiapkan wilayah pantauan.'} Notifikasi Telegram belum aktif.</p></div>
          <button type="button" className="alert-disabled-button" disabled>Telegram belum tersedia</button>
        </section>
        <p className="alert-disclaimer">Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran. Data contoh tidak mewakili peringatan nyata.</p>
      </section>
    </main>
  )
}
