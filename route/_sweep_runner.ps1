param(
    [int]$beam,
    [int]$cap,
    [string]$ctag,
    [double[]]$alphas
)
# α_big 扫描 runner（只扫参·不改产品码）。每个 run 跑完【立即】落盘 floorbest+h5route 到 route/，防中断。
$ErrorActionPreference = 'Continue'
$env:PYTHONPATH = 'C:\Users\pocaf\Source\mota\extract'
$ROOT = 'C:\Users\pocaf\Source\mota'
Set-Location $ROOT
$inv = [System.Globalization.CultureInfo]::InvariantCulture

foreach ($ab in $alphas) {
    $abg = $ab.ToString($inv)                       # 0.5 -> "0.5"（与 probe f"{:g}" 对齐）
    if ($ab -eq 1.0) { $abtag = '' } else { $abtag = "_ab$abg" }
    $src   = "$ROOT\analysis\crossbeam_floorbest_K${beam}_bb25_gd1w${abtag}_lam0.2_stairs.jsonl"
    $dst   = "$ROOT\route\crossbeam_floorbest_K${beam}_bb25_gd1w${abtag}_${ctag}_lam0.2_stairs.jsonl"
    $log   = "$ROOT\route\log_ab${abg}_${ctag}.txt"
    $h5    = "$ROOT\deepest_K${beam}_bb25_gd1w${abtag}_${ctag}_lam0.2_stairs.h5route"
    $h5dst = "$ROOT\route\deepest_K${beam}_bb25_gd1w${abtag}_${ctag}_lam0.2_stairs.h5route"

    Write-Host "=== RUN ab=$abg cap=$cap  START $(Get-Date -Format HH:mm:ss) ==="
    python analysis\probe_crossfloor_beam.py --beam $beam --beta-big 25 --gamma-door 1 --door-win --lam 0.2 --diversity stairs --cap $cap --alpha-big $abg --no-cut 2>&1 | Out-File $log -Encoding utf8

    if (Test-Path $src) {
        Copy-Item $src $dst -Force
        python extract\gen_bosspass_h5route.py $dst 2>&1 | Out-File "$ROOT\route\h5gen_ab${abg}_${ctag}.txt" -Encoding utf8
        if (Test-Path $h5) {
            Move-Item $h5 $h5dst -Force
            Write-Host "ab=$abg cap=$cap  DONE floorbest+h5route landed  $(Get-Date -Format HH:mm:ss)"
        } else {
            Write-Host "ab=$abg cap=$cap  WARN floorbest ok but h5route missing (see h5gen log)"
        }
    } else {
        Write-Host "ab=$abg cap=$cap  ERROR floorbest not produced (see $log)"
    }
}
Write-Host "=== BATCH $ctag ALL DONE $(Get-Date -Format HH:mm:ss) ==="
