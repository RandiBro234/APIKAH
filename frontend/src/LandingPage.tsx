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
  { key: 'd7', label: 'Minggu depan' },
]

const STATS = [
  { value: '3,94 juta', label: 'deteksi hotspot satelit yang dianalisis, 2012 sampai 2026' },
  { value: '1-3 hari', label: 'jangka waktu perkiraan ke depan' },
  { value: '4 level', label: 'tingkat risiko dengan arti yang jelas' },
  { value: '25 km', label: 'ukuran tiap area perkiraan' },
]

const LEVELS: RiskLevel[] = [1, 2, 3, 4]
const NAV_ITEMS = [
  { href: '#ringkasan', label: 'Ringkasan' },
  { href: '#cara-kerja', label: 'Cara kerja' },
  { href: '#fitur', label: 'Fitur' },
] as const

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
    }, { threshold: 0.01, rootMargin: '0px 0px 80px 0px' })
    nodes.forEach((node) => {
      const rect = node.getBoundingClientRect()
      if (rect.top < window.innerHeight && rect.bottom > 0) node.classList.add('is-visible')
      else observer.observe(node)
    })
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
  { num: '04', title: 'Tampilkan di peta', text: 'Lihat level risiko per area pada dashboard. Informasi lain masih dalam pengembangan.' },
]

export function LandingPage() {
  const [activeSection, setActiveSection] = useState('ringkasan')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
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

  useEffect(() => {
    const sections = NAV_ITEMS
      .map(({ href }) => document.querySelector<HTMLElement>(href))
      .filter((section): section is HTMLElement => section !== null)
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
      if (visible) setActiveSection(visible.target.id)
    }, { rootMargin: '-72px 0px -35% 0px', threshold: [0, 0.25, 0.6, 1] })
    sections.forEach((section) => observer.observe(section))
    return () => observer.disconnect()
  }, [])

  return (
    <main className="dashboard landing-page">
      <header className="topbar lp-topbar">
        <a className="wordmark" href="/" aria-label="HOTSPOT.ID, beranda"><span className="wordmark-mark" aria-hidden="true" /><span>HOTSPOT.ID</span></a>
        <nav className="lp-links" aria-label="Bagian halaman">
          {NAV_ITEMS.map(({ href, label }) => {
            const sectionId = href.slice(1)
            return (
              <a
                className="lp-link"
                href={href}
                aria-current={activeSection === sectionId ? 'location' : undefined}
                key={href}
              >
                {label}
              </a>
            )
          })}
          <a className="lp-link" href="/metode">Metode</a>
        </nav>
        <div className="topbar-right">
          <a className="top-pill" href="/peta">Buka dashboard</a>
          <button
            className="lp-menu-toggle"
            type="button"
            aria-expanded={mobileNavOpen}
            aria-controls="lp-mobile-nav"
            onClick={() => setMobileNavOpen((open) => !open)}
          >
            Menu
          </button>
        </div>
      </header>
      <nav className="lp-mobile-nav" id="lp-mobile-nav" aria-label="Bagian halaman versi mobile" hidden={!mobileNavOpen}>
          {NAV_ITEMS.map(({ href, label }) => {
            const sectionId = href.slice(1)
            return (
              <a
                className="lp-link"
                href={href}
                aria-current={activeSection === sectionId ? 'location' : undefined}
                key={href}
                onClick={() => setMobileNavOpen(false)}
              >
                {label}
              </a>
            )
          })}
          <a className="lp-link" href="/metode" onClick={() => setMobileNavOpen(false)}>Metode</a>
      </nav>

      <section className="lp-hero" aria-labelledby="judul-utama">
          <div className="lp-hero-copy">
            <p className="lp-eyebrow">Klasifikasi risiko wilayah</p>
            <h1 className="lp-h1" id="judul-utama">Ketahui kabupaten/kota yang perlu diperhatikan lebih dulu</h1>
            <p className="lp-sub">Sistem membaca pola hotspot, cuaca, dan kondisi lahan dari 2012 sampai 2026 untuk mengelompokkan status risiko wilayah pada horizon yang dipilih.</p>
            <div className="lp-actions">
              <a className="lp-btn lp-btn-primary" href="/peta">Buka peta wilayah</a>
              <a className="lp-btn lp-btn-secondary" href="#cara-kerja">Lihat cara kerja</a>
            </div>
            <p className="lp-hero-note">Status 0 sampai 3 menunjukkan tingkat risiko wilayah. Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran.</p>
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
              <span className="lp-horizon-note">Pilih periode untuk melihat klasifikasi wilayah</span>
            </div>

            <div className="lp-card-map" aria-busy={provinces === null && !failed}>
              {provinces === null && !failed && <p className="lp-card-state" role="status">Memuat pratinjau peta...</p>}
              {failed && <p className="lp-card-state" role="alert">Pratinjau peta gagal dimuat. Muat ulang halaman untuk mencoba lagi.</p>}
              {provinces && <MapPreview provinces={provinces} featured={featured} />}
            </div>

            <div className="lp-card-foot">
              <RiskLegend />
              <span className="lp-tag">Data contoh</span>
            </div>

            <p className="sr-only">Peta wilayah Indonesia dengan provinsi diwarnai menurut status risiko untuk periode yang dipilih. Legenda memuat arti warna dan rentang tiap level.</p>
          </div>
      </section>

      <div className="lp-main">
        <section className="lp-section lp-summary" id="ringkasan" aria-labelledby="judul-ringkasan">
          <div className="lp-section-head lp-summary-head lp-reveal">
            <p className="lp-eyebrow">Ringkasan</p>
            <h2 className="lp-h2" id="judul-ringkasan">Alat bantu keputusan untuk kesiapsiagaan</h2>
            <p className="lp-body">Sistem memperkirakan risiko hotspot untuk area sekitar 25 × 25 km dan menampilkannya dalam empat level. Bukan peringatan resmi atau konfirmasi kebakaran.</p>
          </div>
          <div className="lp-summary-action lp-reveal">
            <p>Mulai dari wilayah yang perlu diperhatikan lebih dulu.</p>
            <a className="lp-card-link" href="/peta">Lihat peta risiko</a>
          </div>
          <dl className="lp-stats lp-reveal">
            {STATS.map((stat) => (
              <div className="lp-stat" key={stat.value}>
                <dd className="lp-stat-value">{stat.value}</dd>
                <dt className="lp-stat-label">{stat.label}</dt>
              </div>
            ))}
          </dl>
          <p className="lp-sources lp-reveal">Sumber: NASA FIRMS (hotspot satelit), ERA5 (cuaca), geoBoundaries (batas wilayah).</p>
        </section>

        <section className="lp-section" id="cara-kerja" aria-labelledby="judul-cara-kerja">
          <div className="lp-section-head lp-reveal">
            <p className="lp-eyebrow">Cara kerja</p>
            <h2 className="lp-h2" id="judul-cara-kerja">Dari data satelit sampai peringatan</h2>
          </div>
          <ol className="lp-steps">
            {STEPS.map((step, index) => (
              <li className="lp-step lp-reveal" key={step.num}>
                <div className="lp-step-icon">{STEP_ICONS[index]}</div>
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
          <div className="lp-feature-list">
            <article className="lp-feature-primary lp-reveal">
              <span className="lp-badge lp-badge-live">Bisa dicoba</span>
              <h3>Peta risiko per wilayah</h3>
              <p>Pilih periode aktual, besok, atau lusa untuk melihat perubahan level risiko. Buka dashboard untuk menjelajahi peta lebih lanjut.</p>
              <a className="lp-card-link" href="/peta">Buka peta risiko</a>
            </article>
            <article className="lp-feature-secondary lp-reveal">
              <h3>Yang sedang dikembangkan</h3>
              <ul>
                <li>Faktor pendorong risiko per area</li>
                <li>Peringkat wilayah</li>
                <li>Notifikasi berdasarkan lokasi pantauan</li>
              </ul>
            </article>
            <article className="lp-feature-method lp-reveal">
              <h3>Metode dan batasan</h3>
              <p>Sumber data, cara membaca level, dan keterbatasan sistem tersedia terbuka.</p>
              <a className="lp-card-link" href="/metode">Baca metode</a>
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
