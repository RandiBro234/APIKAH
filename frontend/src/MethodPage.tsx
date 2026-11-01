const methodology = [
  {
    index: '01',
    title: 'Satuan analisis',
    text: 'Sistem membagi Indonesia ke sel grid berukuran 0,25 derajat. Setiap catatan mewakili satu sel pada satu tanggal lokal.',
    detail: 'ID sel dihitung dari indeks lintang dan bujur. Rumus grid mengikuti kontrak data proyek.',
  },
  {
    index: '02',
    title: 'Label dan horizon',
    text: 'Label kejadian berasal dari deteksi hotspot VIIRS yang teramati pada tanggal target. Horizon risiko mencakup besok, lusa, dan tulat.',
    detail: 'Aktual menunjukkan observasi 24 jam terakhir, bukan hasil prediksi.',
  },
  {
    index: '03',
    title: 'Fitur dan penjelasan',
    text: 'Rencana fitur mencakup riwayat hotspot, cuaca dan kekeringan, indeks iklim, gambut, tutupan lahan, tipologi wilayah, serta musim.',
    detail: 'Faktor pendorong per sel direncanakan diterjemahkan menjadi kalimat awam. Model operasional dan evaluasinya belum terhubung ke antarmuka contoh ini.',
  },
]

const levels = [
  { name: 'RENDAH', threshold: 'Di bawah 10%', color: 'var(--risk-low)' },
  { name: 'SEDANG', threshold: '10% sampai di bawah 25%', color: 'var(--risk-medium)' },
  { name: 'TINGGI', threshold: '25% sampai di bawah 50%', color: 'var(--risk-high)' },
  { name: 'SANGAT TINGGI', threshold: '50% ke atas', color: 'var(--risk-very-high)' },
]

export function MethodPage() {
  return (
    <main className="dashboard method-page">
      <header className="topbar">
        <a className="wordmark" href="/peta" aria-label="HOTSPOT.ID, kembali ke peta">
          <span className="wordmark-mark" aria-hidden="true" />
          <span>HOTSPOT.ID</span>
        </a>
        <nav className="main-nav" aria-label="Navigasi utama">
          <a className="nav-tab" href="/">Beranda</a>
          <a className="nav-tab" href="/peta">Peta</a>
          <a className="nav-tab" href="/wilayah">Wilayah</a>
          <a className="nav-tab" href="/riwayat">Riwayat</a>
          <a className="nav-tab nav-active" href="/metode" aria-current="page">Metode</a>
        </nav>
        <span className="sample-label method-sample">Data contoh</span>
      </header>

      <section className="method-content" aria-labelledby="method-title">
        <div className="method-intro">
          <span className="eyebrow">METODE DAN DATA</span>
          <h1 id="method-title">Cara membaca risiko munculnya hotspot</h1>
          <p>Halaman ini menjelaskan rancangan metode. Peta dan nilai yang tampil saat ini memakai data contoh, bukan keluaran model operasional.</p>
        </div>

        <section className="method-warning" aria-label="Status implementasi metode">
          <span className="method-warning-mark" aria-hidden="true">i</span>
          <div>
            <strong>MODEL DAN METRIK BELUM TERSEDIA</strong>
            <p>Jangan gunakan angka pada tampilan contoh sebagai informasi kejadian atau sebagai dasar keputusan lapangan.</p>
          </div>
        </section>

        <section className="method-block" aria-labelledby="workflow-title">
          <div className="method-block-heading">
            <span className="eyebrow">RANCANGAN ANALISIS</span>
            <h2 id="workflow-title">Dari observasi ke tingkat risiko</h2>
          </div>
          <div className="method-steps">
            {methodology.map((step) => (
              <article className="method-step" key={step.index}>
                <span className="method-index">{step.index}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                  <p className="method-detail">{step.detail}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="method-block levels-block" aria-labelledby="levels-title">
          <div className="method-block-heading">
            <span className="eyebrow">AMBANG USULAN</span>
            <h2 id="levels-title">Empat tingkat risiko</h2>
            <p>Ambang mengikuti usulan awal dan perlu ditinjau setelah validasi model.</p>
          </div>
          <div className="method-level-list">
            {levels.map((level, index) => (
              <div className="method-level-row" key={level.name}>
                <span className="legend-swatch" style={{ backgroundColor: level.color }} aria-hidden="true">
                  <span className="legend-bars">{[0, 1, 2, 3].map((bar) => <i key={bar} className={bar <= index ? 'filled' : ''} />)}</span>
                </span>
                <strong>{level.name}</strong>
                <span>{level.threshold}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="method-block evaluation-block" aria-labelledby="evaluation-title">
          <div className="method-block-heading">
            <span className="eyebrow">EVALUASI</span>
            <h2 id="evaluation-title">Metrik belum ditampilkan</h2>
          </div>
          <p>Rancangan evaluasi memakai pembagian berdasarkan waktu dan rolling-origin per tahun. Precision, recall, PR-AUC, serta kalibrasi harus dihitung dari hasil backtest sebelum diterbitkan.</p>
          <p>Perbandingan direncanakan untuk persistensi, klimatologi, dan regresi logistik, lalu dilaporkan menurut tahun, musim, dan pulau.</p>
        </section>

        <section className="method-block data-block" aria-labelledby="sources-title">
          <div className="method-block-heading">
            <span className="eyebrow">SUMBER DAN BATASAN</span>
            <h2 id="sources-title">Data yang direncanakan</h2>
          </div>
          <ul className="source-list">
            <li><strong>Hotspot</strong><span>NASA FIRMS VIIRS untuk label, riwayat, dan observasi hotspot.</span></li>
            <li><strong>Cuaca</strong><span>ERA5 untuk pelatihan; sumber prakiraan operasional belum diputuskan.</span></li>
            <li><strong>Konteks lahan</strong><span>Gambut, tutupan lahan, dan batas wilayah menunggu verifikasi sumber serta lisensi.</span></li>
            <li><strong>Area terdampak</strong><span>Rentang dampak perlu data area terbakar historis dan backtest yang layak.</span></li>
          </ul>
        </section>

        <footer className="method-footer">
          <p>Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran.</p>
          <a href="/peta">KEMBALI KE PETA</a>
        </footer>
      </section>
    </main>
  )
}
