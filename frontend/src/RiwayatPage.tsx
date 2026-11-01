const monthlyPattern = [
  { month: 'JAN', rate: 5.2 }, { month: 'FEB', rate: 4.6 }, { month: 'MAR', rate: 5.8 },
  { month: 'APR', rate: 6.9 }, { month: 'MEI', rate: 8.4 }, { month: 'JUN', rate: 11.6 },
  { month: 'JUL', rate: 16.8 }, { month: 'AGU', rate: 21.3 }, { month: 'SEP', rate: 23.7 },
  { month: 'OKT', rate: 18.9 }, { month: 'NOV', rate: 9.7 }, { month: 'DES', rate: 3.4 },
]

const yearPeaks = [
  { year: 2015, count: 875000, elNino: true },
  { year: 2014, count: 552000, elNino: false },
  { year: 2026, count: 418000, elNino: false, note: 's.d. Sep' },
  { year: 2019, count: 436000, elNino: true },
  { year: 2023, count: 250000, elNino: true },
]

const concentration = [
  { share: '50%', cells: 290 },
  { share: '80%', cells: 828 },
  { share: '95%', cells: 1541 },
]

const totalCells = 3267
const maxMonthly = Math.max(...monthlyPattern.map((m) => m.rate))
const maxYearCount = Math.max(...yearPeaks.map((y) => y.count))

export function RiwayatPage() {
  return (
    <main className="dashboard method-page riwayat-page">
      <header className="topbar">
        <a className="wordmark" href="/peta" aria-label="HOTSPOT.ID, kembali ke peta">
          <span className="wordmark-mark" aria-hidden="true" />
          <span>HOTSPOT.ID</span>
        </a>
        <nav className="main-nav" aria-label="Navigasi utama">
          <a className="nav-tab" href="/">Beranda</a>
          <a className="nav-tab" href="/peta">Peta</a>
          <a className="nav-tab" href="/wilayah">Wilayah</a>
          <a className="nav-tab nav-active" href="/riwayat" aria-current="page">Riwayat</a>
          <a className="nav-tab" href="/metode">Metode</a>
        </nav>
        <span className="sample-label method-sample">Data contoh</span>
      </header>

      <section className="method-content" aria-labelledby="riwayat-title">
        <div className="method-intro">
          <span className="eyebrow">RIWAYAT DAN TREN</span>
          <h1 id="riwayat-title">Pola musiman dan tahun El Niño</h1>
          <p>Ringkasan analisis data historis hotspot Indonesia, 20 Jan 2012 sampai 30 Sep 2026 (3.941.038 deteksi, NASA FIRMS VIIRS). Konteks waktu untuk membaca risiko saat ini.</p>
        </div>

        <section className="method-warning" aria-label="Catatan pembacaan data">
          <span className="method-warning-mark" aria-hidden="true">i</span>
          <div>
            <strong>TIDAK ADA TREN JANGKA PANJANG YANG SIGNIFIKAN</strong>
            <p>Variasi antar tahun dipengaruhi kondisi iklim. Riwayat memberi konteks musiman, bukan jaminan kejadian.</p>
          </div>
        </section>

        <section className="method-block" aria-labelledby="musiman-title">
          <div className="method-block-heading">
            <span className="eyebrow">POLA MUSIMAN</span>
            <h2 id="musiman-title">Risiko memuncak di musim kemarau</h2>
            <p>Laju dasar kejadian "ada hotspot dalam 1-3 hari" rata-rata 9,9%. Terendah Desember (3,4%), memuncak September (23,7%).</p>
          </div>
          <div className="riwayat-chart" role="img" aria-label="Grafik batang laju hotspot per bulan, puncak September 23,7 persen">
            {monthlyPattern.map((item) => (
              <div className="riwayat-bar" key={item.month}>
                <span className="riwayat-bar-value">{item.rate.toLocaleString('id-ID')}%</span>
                <span className="riwayat-bar-track" aria-hidden="true"><i style={{ height: `${Math.max(3, (item.rate / maxMonthly) * 100)}%` }} /></span>
                <span className="riwayat-bar-label">{item.month}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="method-block" aria-labelledby="tahunan-title">
          <div className="method-block-heading">
            <span className="eyebrow">PERBANDINGAN TAHUNAN</span>
            <h2 id="tahunan-title">Tahun El Niño lebih parah</h2>
            <p>Puncak deteksi tahunan. Tahun El Niño (2015, 2019, 2023) ditandai khusus; 2015 adalah tahun terparah.</p>
          </div>
          <ul className="riwayat-year-list">
            {yearPeaks.map((year) => (
              <li className="riwayat-year-row" key={year.year}>
                <span className="riwayat-year-label">
                  <strong>{year.year}{year.note ? ` ${year.note}` : ''}</strong>
                  {year.elNino && <span className="riwayat-elnino">EL NIÑO</span>}
                </span>
                <span className="riwayat-year-track" aria-hidden="true"><i style={{ width: `${Math.max(3, (year.count / maxYearCount) * 100)}%` }} /></span>
                <span className="riwayat-year-value">{(year.count / 1000).toLocaleString('id-ID', { maximumFractionDigits: 0 })} rb</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="method-block" aria-labelledby="konsentrasi-title">
          <div className="method-block-heading">
            <span className="eyebrow">KONSENTRASI WILAYAH</span>
            <h2 id="konsentrasi-title">Risiko menumpuk di sedikit titik</h2>
            <p>Dari {totalCells.toLocaleString('id-ID')} titik aktif, sebagian besar hotspot terkonsentrasi pada sebagian kecil wilayah — dasar logika prioritas di tab WILAYAH.</p>
          </div>
          <ul className="riwayat-conc-list">
            {concentration.map((item) => (
              <li className="riwayat-conc-row" key={item.share}>
                <strong>{item.share} hotspot</strong>
                <span>berasal dari <b>{item.cells.toLocaleString('id-ID')}</b> titik ({Math.round((item.cells / totalCells) * 100)}% wilayah)</span>
              </li>
            ))}
          </ul>
          <a className="riwayat-link" href="/wilayah">LIHAT PRIORITAS WILAYAH</a>
        </section>

        <section className="method-block data-block" aria-labelledby="catatan-title">
          <div className="method-block-heading">
            <span className="eyebrow">SUMBER DAN BATASAN</span>
            <h2 id="catatan-title">Cara membaca angka ini</h2>
          </div>
          <ul className="source-list">
            <li><strong>Sumber</strong><span>NASA FIRMS VIIRS (SNPP dan NOAA-20), 2012 sampai Sep 2026, hanya di dalam Indonesia.</span></li>
            <li><strong>Waktu</strong><span>Tanggal UTC berbeda dari tanggal lokal pada 34% catatan; label memakai tanggal lokal (waktu surya).</span></li>
            <li><strong>Arti hotspot</strong><span>Deteksi satelit, bukan konfirmasi kebakaran. Angka historis adalah konteks, bukan prediksi.</span></li>
            <li><strong>Model operasional</strong><span>Belum terhubung; metrik evaluasi per tahun dijelaskan di halaman METODE.</span></li>
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
