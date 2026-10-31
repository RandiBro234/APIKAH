# status.ps1 -- ringkasan progres crawler APIKAH.
# Bisa dijalankan dari folder mana pun:
#     powershell -ExecutionPolicy Bypass -File "C:\...\hotspot_crawler\status.ps1"
# atau, kalau sudah di folder crawler:
#     .\status.ps1

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Selalu bekerja di folder skrip ini, supaya path relatif (data/...) benar.
Set-Location $PSScriptRoot

Write-Output ("========== STATUS " + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " ==========")

Write-Output ""
Write-Output "--- 1. PROSES YANG JALAN ---"
$proses = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
          Where-Object { $_.CommandLine -match 'crawl_' }
if ($proses) {
    foreach ($p in $proses) {
        $cmd = $p.CommandLine -replace '.*python\.exe"?\s*', ''
        "  PID {0,-6} {1}" -f $p.ProcessId, $cmd
    }
} else {
    "  TIDAK ADA proses crawler yang jalan"
}

Write-Output ""
Write-Output "--- 2. DATA DINAMIS (data/raw) ---"
$raw = Get-ChildItem "data\raw" -Recurse -File -ErrorAction SilentlyContinue
"  total: {0} berkas | {1:N1} MB" -f $raw.Count, (($raw | Measure-Object -Sum Length).Sum/1MB)
foreach ($g in @(@("era5land\instant", "ERA5 instant"), @("era5land\accum", "ERA5 accum"), @("cems_fire", "CEMS Fire"))) {
    $d = Get-ChildItem ("data\raw\" + $g[0]) -File -ErrorAction SilentlyContinue
    if ($d) {
        $b = @($d | ForEach-Object { $_.BaseName } | Sort-Object)
        "  {0,-13}: {1,3} berkas | {2} .. {3}" -f $g[1], $d.Count, $b[0], $b[-1]
    }
}

Write-Output ""
Write-Output "--- 3. DATA STATIS (data/static) ---"
$st = Get-ChildItem "data\static" -Recurse -File -ErrorAction SilentlyContinue
if ($st) {
    $st | Group-Object { $_.Directory.Name } | Sort-Object Name | ForEach-Object {
        "  {0,-14}: {1,4} berkas {2,9:N1} MB" -f $_.Name, $_.Count, (($_.Group | Measure-Object -Sum Length).Sum/1MB)
    }
} else {
    "  kosong"
}

Write-Output ""
Write-Output "--- 4. MANIFEST (catatan resmi crawler) ---"
if (Test-Path "report_manifest.py") {
    python report_manifest.py --quiet 2>&1 |
        Select-String "diharapkan|status |PERLU|BELUM LENGKAP|LENGKAP|tidak ada daftar"
}

Write-Output ""
Write-Output "--- 5. LAJU UNDUHAN 20 MENIT TERAKHIR ---"
$cut = (Get-Date).AddMinutes(-20)
$baru = @($raw | Where-Object { $_.LastWriteTime -gt $cut })
"  {0} berkas selesai -> ~{1:N0} berkas/jam (1 bulan ERA5 = 2 berkas)" -f $baru.Count, ($baru.Count * 3)

Write-Output ""
Write-Output "--- 6. LOG TERBARU ---"
foreach ($lg in @("copernicus.log", "copernicus_b.log", "static.log")) {
    $path = "data\logs\$lg"
    if (Test-Path $path) {
        "  [$lg]"
        Get-Content $path -Tail 2 | ForEach-Object { "    " + $_.Substring(0, [Math]::Min(120, $_.Length)) }
    }
}

Write-Output ""
Write-Output "--- 7. DISK ---"
Get-PSDrive C | ForEach-Object { "  bebas: {0:N1} GB" -f ($_.Free / 1GB) }
