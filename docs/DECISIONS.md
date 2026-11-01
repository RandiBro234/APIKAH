# Keputusan Teknis

## Tema tunggal terang; tema gelap dihapus

**Keputusan.** Antarmuka hanya punya satu tema: terang (putih). Tema gelap dihapus seluruhnya.

**Yang dihapus.**

- Tombol/switch tema di bilah atas dashboard.
- Penyimpanan pilihan tema di `localStorage` (`hotspot-theme`).
- Pembacaan `prefers-color-scheme` dan blok `@media (prefers-color-scheme: dark)`.
- Blok token `:root[data-theme="dark"]` dan `:root[data-theme="light"]`, serta mekanisme
  `document.documentElement.dataset.theme`.
- Token permukaan gelap (`--ink-*`) yang dulu dipakai panel gelap di beranda.

**Konsekuensi.**

- `frontend/src/styles/tokens.css` hanya berisi satu set nilai di `:root`.
- Hitam tetap dipakai sebagai aksen lewat `--accent` (#141414) dan `--on-accent` (#FFFFFF):
  tombol utama, label wilayah di peta, blok Ajakan, dan footer beranda. Tidak ada permukaan
  gelap besar di luar itu.
- Peta dashboard memakai kanvas `--map-bg` (#F4F4F2), provinsi tanpa data `--map-land`
  (#E9E9E5) dengan garis putih 1px.
