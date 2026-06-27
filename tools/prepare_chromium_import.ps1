param(
    [Parameter(Mandatory = $true)]
    [string]$ChromiumRoot,
    [string]$Destination = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Fail($Message) {
    throw "Chromium import preparation failed: $Message"
}

function Is-Excluded {
    param(
        [string]$RelativePath,
        [string[]]$Patterns
    )

    $normalized = $RelativePath.Replace("\", "/")
    foreach ($pattern in $Patterns) {
        if ($normalized -eq $pattern -or $normalized -like $pattern) {
            return $true
        }
        if ($normalized.StartsWith("$pattern/")) {
            return $true
        }
    }
    return $false
}

$repoRoot = (Resolve-Path ".").Path
$repoRootWithSeparator = $repoRoot.TrimEnd("\") + "\"
$manifestPath = Join-Path $repoRoot "chromium_import_manifest.json"
if (-not (Test-Path $manifestPath)) {
    Fail "missing chromium_import_manifest.json"
}

$manifest = Get-Content -Raw $manifestPath | ConvertFrom-Json
$chromiumPath = Resolve-Path $ChromiumRoot -ErrorAction SilentlyContinue
if ($null -eq $chromiumPath) {
    Fail "ChromiumRoot does not exist: $ChromiumRoot"
}

$chromiumRootPath = $chromiumPath.Path
foreach ($required in $manifest.required_chromium_paths) {
    $requiredPath = Join-Path $chromiumRootPath $required
    if (-not (Test-Path $requiredPath)) {
        Fail "ChromiumRoot is missing required path: $required"
    }
}

if ($Destination -eq "") {
    $Destination = $manifest.default_destination
}

$destinationPath = Join-Path $chromiumRootPath $Destination
$filesToCopy = New-Object System.Collections.Generic.List[object]

foreach ($entry in $manifest.files) {
    $source = Join-Path $repoRoot $entry
    if (-not (Test-Path $source)) {
        Fail "manifest entry does not exist in repo: $entry"
    }

    if ((Get-Item $source).PSIsContainer) {
        Get-ChildItem -LiteralPath $source -Recurse -File | ForEach-Object {
            $relative = $_.FullName.Substring($repoRootWithSeparator.Length)
            if (-not (Is-Excluded $relative $manifest.exclude)) {
                $filesToCopy.Add([pscustomobject]@{
                    Source = $_.FullName
                    Relative = $relative
                })
            }
        }
    } else {
        if (-not (Is-Excluded $entry $manifest.exclude)) {
            $filesToCopy.Add([pscustomobject]@{
                Source = $source
                Relative = $entry
            })
        }
    }
}

Write-Host "================================================================"
Write-Host "        Chromium Rust Import Preparation                        "
Write-Host "================================================================"
Write-Host "Chromium root: $chromiumRootPath"
Write-Host "Destination:   $destinationPath"
Write-Host "Files:         $($filesToCopy.Count)"

if ($DryRun) {
    Write-Host "Mode:          dry-run"
    $filesToCopy | Select-Object -First 25 | ForEach-Object {
        Write-Host "  $($_.Relative)"
    }
    if ($filesToCopy.Count -gt 25) {
        Write-Host "  ... $($filesToCopy.Count - 25) more"
    }
    Write-Host "No files were copied."
    exit 0
}

if (-not (Test-Path $destinationPath)) {
    New-Item -ItemType Directory -Force -Path $destinationPath | Out-Null
}

foreach ($file in $filesToCopy) {
    $target = Join-Path $destinationPath $file.Relative
    $targetDir = Split-Path $target -Parent
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    }
    Copy-Item -LiteralPath $file.Source -Destination $target -Force
}

Write-Host "Import scaffold copied successfully."
Write-Host "Next Chromium-side checks:"
Write-Host "  gn gen out/rust-perf"
Write-Host "  autoninja -C out/rust-perf <target that depends on //$Destination:rust_perf_adapters>"
Write-Host "  tools/binary_size/supersize.py archive ..."
