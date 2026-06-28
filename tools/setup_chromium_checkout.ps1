param(
    [string]$CheckoutParent = "C:\src\chromium",
    [string]$DepotToolsPath = "C:\src\depot_tools",
    [switch]$SkipFetch,
    [switch]$NoHistory
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host ">>> $Message"
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found on PATH: $Name"
    }
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$chromiumRoot = Join-Path $CheckoutParent "src"
$configPath = Join-Path $repoRoot "chromium_checkout.local.json"
$logPath = Join-Path $repoRoot "target\logs\chromium_checkout_setup.log"

Write-Host "================================================================"
Write-Host "        Chromium Checkout Setup for RUST Chromium               "
Write-Host "================================================================"
Write-Host "Repo:            $repoRoot"
Write-Host "Checkout parent: $CheckoutParent"
Write-Host "Chromium root:   $chromiumRoot"
Write-Host "depot_tools:     $DepotToolsPath"

Write-Step "Checking prerequisites"
Require-Command git

$drive = (Get-Item $CheckoutParent -ErrorAction SilentlyContinue).PSDrive.Name
if ($drive -eq $null) {
    $drive = (Get-PSDrive -Name C).Name
}
$freeBytes = (Get-PSDrive $drive).Free
$minimumFreeBytes = 120 * 1024 * 1024 * 1024
if ($freeBytes -lt $minimumFreeBytes) {
    throw "Need at least 120 GB free on drive $drive. Found $([math]::Round($freeBytes / 1GB, 1)) GB."
}

$vs2022 = "C:\Program Files\Microsoft Visual Studio\2022\Community"
if (-not (Test-Path $vs2022)) {
    Write-Warning "Visual Studio 2022 Community not found at default path. Chromium build may fail until VS is installed."
} else {
    Write-Host "Found Visual Studio 2022 Community."
}

Ensure-Directory (Split-Path $DepotToolsPath -Parent)
Ensure-Directory $CheckoutParent
Ensure-Directory (Join-Path $repoRoot "target\logs")

Write-Step "Configuring git for Chromium"
git config --global core.autocrlf false | Out-Null
git config --global core.filemode false | Out-Null
git config --global core.longpaths true | Out-Null
git config --global branch.autosetuprebase always | Out-Null

Write-Step "Installing depot_tools"
if (-not (Test-Path (Join-Path $DepotToolsPath "gclient.py"))) {
    git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git $DepotToolsPath
} else {
    Write-Host "depot_tools already present."
}

$env:DEPOT_TOOLS_WIN_TOOLCHAIN = "0"
if (Test-Path $vs2022) {
    $env:vs2022_install = $vs2022
}
$env:Path = "$DepotToolsPath;$env:Path"

Write-Step "Bootstrapping depot_tools (first gclient run)"
$bootstrapLog = Join-Path $repoRoot "target\logs\depot_tools_bootstrap.log"
cmd /c "gclient > `"$bootstrapLog`" 2>&1"

$config = @{
    schema_version = 1
    chromium_root = $chromiumRoot
    depot_tools = $DepotToolsPath
    checkout_parent = $CheckoutParent
}
$config | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 $configPath
Write-Host "Wrote local config: $configPath"

if ($SkipFetch) {
    Write-Host "SkipFetch set. Local config written; run fetch manually later."
    exit 0
}

if (Test-Path (Join-Path $chromiumRoot "build\config\rust.gni")) {
    Write-Host "Chromium checkout already looks present at $chromiumRoot"
    Write-Step "Running preflight"
    Push-Location $repoRoot
    try {
        python tools/check_chromium_checkout_preflight.py --chromium-root $chromiumRoot
        python tools/select_chromium_next_task.py --chromium-root $chromiumRoot
    } finally {
        Pop-Location
    }
    exit 0
}

Write-Step "Fetching Chromium source (this can take 1-3+ hours)"
$fetchArgs = "fetch chromium"
if ($NoHistory) {
    $fetchArgs = "fetch --no-history chromium"
}
$fetchLog = Join-Path $repoRoot "target\logs\chromium_fetch.log"
Push-Location $CheckoutParent
try {
    cmd /c "$fetchArgs > `"$fetchLog`" 2>&1"
    if ($LASTEXITCODE -ne 0) {
        throw "fetch failed with exit code $LASTEXITCODE. See $fetchLog"
    }
} finally {
    Pop-Location
}

Write-Step "Running gclient sync"
Push-Location $chromiumRoot
try {
    cmd /c "gclient sync -D > `"$logPath`" 2>&1"
    if ($LASTEXITCODE -ne 0) {
        throw "gclient sync failed with exit code $LASTEXITCODE. See $logPath"
    }
} finally {
    Pop-Location
}

Write-Step "Validating checkout from this repo"
Push-Location $repoRoot
try {
    python tools/check_chromium_checkout_preflight.py --chromium-root $chromiumRoot
    python tools/select_chromium_next_task.py --chromium-root $chromiumRoot
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host " Chromium checkout setup completed.                             "
Write-Host " Next:"
Write-Host "   . tools/activate_chromium_env.ps1"
Write-Host "   powershell -File tools/prepare_chromium_import.ps1 -ChromiumRoot $chromiumRoot -DryRun"
Write-Host "================================================================" -ForegroundColor Green