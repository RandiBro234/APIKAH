import { useEffect, useState } from 'react'
import { loadMapData, type ProvinceFeature } from './lib/map-data'
import { MapPreview } from './MapPreview'
import { RISK_LEVELS } from './lib/risk'
import { RiskLegend } from './Legend'
import type { RiskLevel } from './types/geojson'
import './styles/landing.css'

const HORIZONS = [
  { key: 'd0', label: 'Aktual' },
  { key: 'd1', label: 'Besok' },
  { key: 'd2', label: 'Lusa' },
]

const STATS = [
  { value: '3,94 juta', label: 'deteksi hotspot satelit yang dianalisis, 2012 sampai 2026' },
  { value: '1-3 hari', label: 'jangka waktu perkiraan ke depan' },
  { value: '4 level', label: 'tingkat risiko dengan arti yang jelas' },
  { value: '25 km', label: 'ukuran tiap area perkiraan' },
]

const LEVELS: RiskLevel[] = [1, 2, 3, 4]

type Featured = { name: string; level: RiskLevel; drivers: string[] }

function useRevealOnScroll() {
  useEffect(() => {
    const nodes = Array.from(document.querySelectorAll<HTMLElement>('.lp-reveal'))
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      nodes.forEach((node) => node.classList.add('is-visible'))
      return
    }
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        entry.target.classList.add('is-visible')
        observer.unobserve(entry.target)
      }
    }, { threshold: 0.12 })
    nodes.forEach((node) => observer.observe(node))
    return () => observer.disconnect()
  }, [])
}

const STEP_ICONS = [
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true" key="kumpulkan"><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" /><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></svg>,
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true" key="hitung"><rect x="4" y="3" width="16" height="18" rx="3" /><path d="M8 8h8M8 12h2m3 0h3M8 16h2m3 0h3" /></svg>,
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true" key="level"><path d="M4 19h16" /><path d="M7 19v-5M12 19v-9M17 19v-13" /></svg>,
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true" key="tampilkan"><path d="M18 15a6 6 0 1 0-12 0" /><path d="M12 3v2M4.9 5.9l1.4 1.4M19.1 5.9l-1.4 1.4" /><path d="M3 15h18l-2 3H5z" /></svg>,
]

const STEPS = [
  { num: '01', title: 'Kumpulkan data', text: 'Hotspot satelit, cuaca, dan kondisi lahan dikumpulkan setiap hari.' },
  { num: '02', title: 'Hitung risiko', text: 'Model belajar dari riwayat 2012-2026 untuk memperkirakan peluang hotspot muncul.' },
  { num: '03', title: 'Tentukan level', text: 'Skor diterjemahkan menjadi empat level yang mudah dibaca.' },
  { num: '04', title: 'Tampilkan dan beri tahu', text: 'Peta, daftar wilayah, dan notifikasi Telegram sesuai lokasi.' },
]

export function LandingPage() {
  const [horizon, setHorizon] = useState('d0')
  const [provinces, setProvinces] = useState<ProvinceFeature[] | null>(null)
  const [featured, setFeatured] = useState<Featured | null>(null)
  const [failed, setFailed] = useState(false)

  useRevealOnScroll()

  useEffect(() => {
    let cancelled = false
    loadMapData(horizon)
      .then((data) => {
        if (cancelled) return
        setProvinces(data.provinces.features)
        const top = [...data.risk.features].sort((a, b) => b.properties.score - a.properties.score)[0]
        if (top) {
          setFeatured({
            name: top.properties.province,
            level: top.properties.level,
            drivers: (top.properties.drivers ?? []).slice(0, 3),
          })
        }
        setFailed(false)
      })
      .catch(() => { if (!cancelled) setFailed(true) })
    return () => { cancelled = true }
  }, [horizon])

  return (
    <main className="dashboard landing-page">
      <header className="topbar lp-topbar">
        <a className="wordmark" href="/" aria-label="HOTSPOT.ID, beranda"><span className="wordmark-mark" aria-hidden="true" /><span>HOTSPOT.ID</span></a>
        <nav className="lp-links" aria-label="Bagian halaman">
          <a className="lp-link" href="#ringkasan">Ringkasan</a>
          <a className="lp-link" href="#cara-kerja">Cara kerja</a>
          <a className="lp-link" href="#fitur">Fitur</a>
          <a className="lp-link" href="/metode">Metode</a>
        </nav>
        <div className="topbar-right">
          <a className="top-pill" href="/peta">Buka dashboard</a>
        </div>
      </header>

      <section className="lp-hero" aria-labelledby="judul-utama">
          <div className="lp-hero-copy">
            <h1 className="lp-h1" id="judul-utama">Tahu lebih dulu di mana risiko munculnya hotspot</h1>
            <p className="lp-sub">Peringatan dini karhutla untuk seluruh Indonesia, 1 sampai 3 hari ke depan, dihitung dari data satelit dan cuaca.</p>
            <div className="lp-actions">
              <a className="lp-btn lp-btn-primary" href="/peta">Buka dashboard</a>
              <a className="lp-btn lp-btn-secondary" href="#cara-kerja">Lihat cara kerja</a>
            </div>
            <p className="lp-hero-note">Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran.</p>
          </div>

          <div className="lp-hero-card">
            <div className="lp-card-top">
              <div className="lp-seg" role="group" aria-label="Periode pratinjau">
                {HORIZONS.map((item) => (
                  <button key={item.key} type="button" aria-pressed={horizon === item.key} onClick={() => setHorizon(item.key)}>
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="lp-card-map">
              <MapPreview provinces={provinces} featured={featured} />
            </div>

            <div className="lp-card-foot">
              <RiskLegend />
              <span className="lp-tag">Data contoh</span>
            </div>

            {failed && <p className="lp-card-error">Data contoh gagal dimuat.</p>}
            <p className="sr-only">Peta Indonesia dengan provinsi diwarnai menurut level risiko untuk periode yang dipilih. Legenda memuat arti warna dan rentang tiap level.</p>
          </div>
      </section>

      <div className="lp-main">
        <section className="lp-section lp-summary" id="ringkasan" aria-labelledby="judul-ringkasan">
          <div className="lp-reveal">
            <p className="lp-eyebrow">Ringkasan</p>
            <h2 className="lp-h2" id="judul-ringkasan">Alat bantu keputusan untuk kesiapsiagaan</h2>
            <p className="lp-body">Sistem ini memperkirakan risiko munculnya hotspot untuk area seluas sekitar 25 x 25 km, lalu menampilkannya sebagai empat level yang mudah dibaca. Ini bukan peringatan resmi dan bukan konfirmasi kebakaran.</p>
          </div>
          <div className="lp-reveal">
            <dl className="lp-stats">
              {STATS.map((stat) => (
                <div className="lp-stat" key={stat.value}>
                  <dt className="lp-stat-label">{stat.label}</dt>
                  <dd className="lp-stat-value">{stat.value}</dd>
                </div>
              ))}
            </dl>
            <p className="lp-sources">Sumber data: NASA FIRMS untuk hotspot satelit, ERA5 untuk cuaca, geoBoundaries untuk batas wilayah.</p>
          </div>
        </section>

        <section className="lp-section" id="cara-kerja" aria-labelledby="judul-cara-kerja">
          <div className="lp-section-head lp-reveal">
            <p className="lp-eyebrow">Cara kerja</p>
            <h2 className="lp-h2" id="judul-cara-kerja">Dari data satelit sampai peringatan</h2>
          </div>
          <ol className="lp-steps">
            {STEPS.map((step, index) => (
              <li className="lp-step lp-reveal" key={step.num}>
                <span className="lp-step-icon">{STEP_ICONS[index]}</span>
                <span className="lp-step-num">{step.num}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
                {step.num === '03' && (
                  <div className="lp-levelstrip">
                    {LEVELS.map((level) => (
                      <span className="lp-levelrow" key={level}>
                        <i style={{ background: `var(${RISK_LEVELS[level].colorToken})` }} aria-hidden="true" />
                        <span className="level-bars" aria-hidden="true">
                          {LEVELS.map((bar) => <i key={bar} className={bar <= level ? 'filled' : ''} />)}
                        </span>
                        <span>{RISK_LEVELS[level].label} {RISK_LEVELS[level].threshold}</span>
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </section>

        <section className="lp-section" id="fitur" aria-labelledby="judul-fitur">
          <div className="lp-section-head lp-reveal">
            <p className="lp-eyebrow">Fitur</p>
            <h2 className="lp-h2" id="judul-fitur">Yang bisa kamu lakukan</h2>
          </div>
          <div className="lp-bento">
            <article className="lp-card lp-card-wide lp-reveal">
              <span className="lp-badge lp-badge-live">Tersedia</span>
              <h3>Peta risiko 1-3 hari</h3>
              <p>Lihat level risiko tiap area, dari aktual sampai tiga hari ke depan.</p>
              <div className="lp-mini">
                <div className="lp-mini-strip" aria-hidden="true">
                  {LEVELS.map((level) => <i key={level} style={{ background: `var(${RISK_LEVELS[level].colorToken})` }} />)}
                </div>
                <p>Contoh tampilan level: Rendah sampai Sangat tinggi.</p>
              </div>
            </article>

            <article className="lp-card lp-reveal">
              <span className="lp-badge">Segera</span>
              <h3>Faktor pendorong per wilayah</h3>
              <p>Alasan sebuah area berisiko, ditulis dengan kalimat sehari-hari.</p>
              <div className="lp-mini">
                <div className="lp-mini-quote"><span>Contoh: hujan rendah sepekan terakhir.</span><span>Contoh: lahan gambut kering.</span><span>Contoh: hotspot berulang di sekitar area.</span></div>
              </div>
            </article>

            <article className="lp-card lp-reveal">
              <span className="lp-badge">Segera</span>
              <h3>Peringkat wilayah</h3>
              <p>Daftar prioritas agar koordinasi tidak menebak.</p>
              <div className="lp-mini">
                <div className="lp-mini-row"><span>Contoh provinsi A</span><b>4</b></div>
                <div className="lp-mini-row"><span>Contoh provinsi B</span><b>3</b></div>
                <div className="lp-mini-row"><span>Contoh provinsi C</span><b>2</b></div>
              </div>
            </article>

            <article className="lp-card lp-reveal">
              <span className="lp-badge">Segera</span>
              <h3>Perkiraan area terdampak</h3>
              <p>Selalu berupa rentang, bukan satu angka pasti.</p>
              <div className="lp-mini lp-range">
                <span className="lp-range-flag">Perkiraan</span>
                <span className="lp-range-track" aria-hidden="true"><i /></span>
                <div className="lp-range-labels"><span>Contoh 120 ha</span><span>Contoh 340 ha</span></div>
              </div>
            </article>

            <article className="lp-card lp-reveal">
              <span className="lp-badge">Segera</span>
              <h3>Notifikasi Telegram</h3>
              <p>Peringatan singkat untuk wilayah yang kamu pantau.</p>
              <div className="lp-mini">
                <div className="lp-mini-quote">
                  <span>Contoh pesan: Risiko Tinggi di wilayah pantauanmu untuk besok.</span>
                </div>
              </div>
            </article>

            <article className="lp-card lp-reveal">
              <span className="lp-badge">Tersedia</span>
              <h3>Metode dan transparansi</h3>
              <p>Ambang level, sumber data, dan batasan sistem dijelaskan terbuka.</p>
              <a className="lp-card-link" href="/metode">Buka halaman Metode</a>
            </article>
          </div>
        </section>

        <section className="lp-cta lp-reveal" aria-labelledby="judul-ajakan">
          <h2 id="judul-ajakan">Lihat peta risiko hari ini</h2>
          <p>Buka dashboard untuk melihat level risiko per area dan hotspot yang terdeteksi dalam 72 jam terakhir.</p>
          <a className="lp-btn lp-btn-invert" href="/peta">Buka dashboard</a>
        </section>

        <footer className="lp-footer">
          <p>Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran. Sistem ini alat bantu keputusan, bukan peringatan resmi.</p>
          <p>Sumber data: NASA FIRMS, ERA5, geoBoundaries.</p>
          <div className="lp-footer-links">
            <span className="lp-badge">Data contoh</span>
            <a href="/metode">Metode</a>
            <span>Projek Sistem Cerdas</span>
          </div>
        </footer>
      </div>
    </main>
  )
}
