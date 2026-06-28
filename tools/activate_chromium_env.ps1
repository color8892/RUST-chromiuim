$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$configPath = Join-Path $repoRoot "chromium_checkout.local.json"
$examplePath = Join-Path $repoRoot "chromium_checkout.local.json.example"

if (Test-Path $configPath) {
    $config = Get-Content -Raw $configPath | ConvertFrom-Json
} elseif (Test-Path $examplePath) {
    $config = Get-Content -Raw $examplePath | ConvertFrom-Json
} else {
    throw "Missing chromium_checkout.local.json. Run tools/setup_chromium_checkout.ps1 first."
}

$depotTools = $config.depot_tools
$chromiumRoot = $config.chromium_root

if (-not (Test-Path $depotTools)) {
    throw "depot_tools not found at: $depotTools"
}

$env:DEPOT_TOOLS_WIN_TOOLCHAIN = "0"
$env:CHROMIUM_RUST_PERF_ROOT = $repoRoot
$env:CHROMIUM_CHECKOUT_ROOT = $chromiumRoot

if (Test-Path "C:\Program Files\Microsoft Visual Studio\2022\Community") {
    $env:vs2022_install = "C:\Program Files\Microsoft Visual Studio\2022\Community"
}

$env:Path = "$depotTools;$env:Path"

Write-Host "Chromium environment activated."
Write-Host "  depot_tools:   $depotTools"
Write-Host "  chromium_root: $chromiumRoot"
Write-Host "  rust_perf_repo: $repoRoot"