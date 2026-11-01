# CLAUDE.md

Panduan singkat untuk agen yang bekerja di repositori ini. Aturan proyek selengkapnya ada di `AGENTS.md`.

## Tema

**Tema tunggal terang; tema gelap dihapus.**

- Satu-satunya nilai token ada di `:root` pada `frontend/src/styles/tokens.css`.
- Tidak ada tombol/switch tema, tidak ada penyimpanan pilihan tema di `localStorage`,
  tidak ada pembacaan `prefers-color-scheme`, dan tidak ada blok `[data-theme]`.
- Hitam hanya dipakai sebagai aksen lewat `--accent` (#141414) dan `--on-accent` (#FFFFFF):
  tombol utama, label wilayah di peta, blok Ajakan, dan footer beranda.

## Perintah

```powershell
cd .\frontend
npm run dev
npm run typecheck
npm run lint
npm run build
```
