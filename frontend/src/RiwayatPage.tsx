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

const islandShares = [
  { island: 'Kalimantan', share: 37.1 },
  { island: 'Sumatera', share: 31.8 },
  { island: 'Maluku & Papua', share: 10.6 },
  { island: 'Bali & Nusa Tenggara', share: 9.0 },
  { island: 'Sulawesi', share: 6.9 },
  { island: 'Jawa', share: 4.6 },
]

const totalDetections = 3941038
const daytimeShare = 66
const nighttimeShare = 34
const highConfidenceShare = 3.16
const formatPercent = (value: number) => `${value.toLocaleString('id-ID', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`
const formatPercent2 = (value: number) => `${value.toLocaleString('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`
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
          <a className="nav-tab" href="/peringatan">Peringatan</a>
          <a className="nav-tab nav-active" href="/riwayat" aria-current="page">Riwayat</a>
        </nav>
          <span className="sample-label method-sample">EDA NASA FIRMS</span>
      </header>

      <section className="method-content" aria-labelledby="riwayat-title">
        <div className="method-intro">
          <span className="eyebrow">RIWAYAT DAN TREN</span>
          <h1 id="riwayat-title">Apa yang terlihat dari data hotspot?</h1>
          <p>Eksplorasi 3.941.038 deteksi NASA FIRMS VIIRS di Indonesia, 20 Jan 2012 sampai 30 Sep 2026. Angka menggambarkan deteksi satelit, bukan jumlah kebakaran terkonfirmasi.</p>
        </div>

        <section className="method-warning" aria-label="Batasan analisis">
          <span className="method-warning-mark" aria-hidden="true">i</span>
          <div>
            <strong>TREN JANGKA PANJANG BELUM SIGNIFIKAN</strong>
            <p>Uji pada data historis belum membedakan tren jangka panjang dari variasi antar musim. Riwayat memberi konteks, bukan jaminan kejadian.</p>
          </div>
        </section>

        <section className="method-block" aria-labelledby="musiman-title">
          <div className="method-block-heading">
            <span className="eyebrow">POLA MUSIMAN</span>
            <h2 id="musiman-title">Deteksi paling sering pada Agustus sampai Oktober</h2>
            <p>Tiga bulan ini menyumbang 70,7% dari seluruh deteksi pada dataset. September menjadi puncak; ini pola historis, bukan kepastian untuk tahun berikutnya.</p>
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
            <h2 id="tahunan-title">Jumlah deteksi berubah tajam antar tahun</h2>
            <p>2015 menjadi tahun tertinggi pada rentang yang dianalisis. 2026 hanya mencakup Januari sampai September.</p>
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

        <section className="method-block" aria-labelledby="pulau-title">
          <div className="method-block-heading">
            <span className="eyebrow">SEBARAN PER PULAU</span>
            <h2 id="pulau-title">Kalimantan dan Sumatera menyumbang porsi terbesar</h2>
            <p>Persentase dari 3.941.038 deteksi di seluruh rentang dataset.</p>
          </div>
          <ul className="riwayat-year-list">{islandShares.map((item) => <li className="riwayat-year-row" key={item.island}><span className="riwayat-year-label"><strong>{item.island}</strong></span><span className="riwayat-year-track" aria-hidden="true"><i style={{ width: `${item.share}%` }} /></span><span className="riwayat-year-value">{formatPercent(item.share)}</span></li>)}</ul>
        </section>

        <section className="method-block" aria-labelledby="waktu-title">
          <div className="method-block-heading">
            <span className="eyebrow">WAKTU DETEKSI</span>
            <h2 id="waktu-title">Satelit mendeteksi hotspot siang dan malam</h2>
            <p>Kolom siang/malam memberi konteks waktu pengamatan, bukan waktu pasti api mulai muncul.</p>
          </div>
          <ul className="riwayat-conc-list">
            <li className="riwayat-conc-row"><strong>Siang · {daytimeShare}%</strong><span>{Math.round(totalDetections * daytimeShare / 100).toLocaleString('id-ID')} deteksi pada lintasan siang.</span></li>
            <li className="riwayat-conc-row"><strong>Malam · {nighttimeShare}%</strong><span>{Math.round(totalDetections * nighttimeShare / 100).toLocaleString('id-ID')} deteksi pada lintasan malam.</span></li>
            <li className="riwayat-conc-row"><strong>Confidence tinggi · {formatPercent2(highConfidenceShare)}</strong><span>Sebagian besar deteksi tercatat dengan confidence nominal; confidence bukan ukuran luas kebakaran.</span></li>
          </ul>
        </section>

        <section className="method-block data-block" aria-labelledby="catatan-title">
          <div className="method-block-heading">
            <span className="eyebrow">SUMBER DAN BATASAN</span>
            <h2 id="catatan-title">Cara membaca angka ini</h2>
          </div>
          <ul className="source-list">
            <li><strong>Sumber</strong><span>NASA FIRMS VIIRS (SNPP dan NOAA-20), 20 Jan 2012 sampai 30 Sep 2026, hanya titik dalam Indonesia.</span></li>
            <li><strong>Waktu</strong><span>Waktu akuisisi di sumber memakai UTC. Tanggal lokal berdasarkan bujur dapat berbeda pada 34% catatan, terutama deteksi malam.</span></li>
            <li><strong>Confidence</strong><span>Confidence menggambarkan keyakinan deteksi satelit, bukan ukuran luas atau tingkat bahaya kebakaran.</span></li>
            <li><strong>Batasan</strong><span>Hotspot adalah deteksi satelit, bukan konfirmasi kebakaran. Statistik historis memberi konteks, bukan prediksi.</span></li>
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
