param(
    [string]$ChromiumRoot = ""
)

$ErrorActionPreference = "Stop"

function Write-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Detail
    )

    $status = if ($Ok) { "OK" } else { "BLOCKED" }
    $color = if ($Ok) { "Green" } else { "Yellow" }
    Write-Host ("[{0}] {1}: {2}" -f $status, $Name, $Detail) -ForegroundColor $color
}

Write-Host "================================================================"
Write-Host "        Chromium Rust Integration Readiness Check               "
Write-Host "================================================================"

$repoRoot = (Resolve-Path ".").Path
$requiredLocalPaths = @(
    "BUILD.gn",
    "rust/hot_leaf/http_header_scanner/src/lib.rs",
    "rust/hot_leaf/url_canonicalizer/src/lib.rs",
    "rust/hot_leaf/mojo_validator/src/lib.rs",
    "rust/ffi_static/src/lib.rs",
    "tools/run_size_gate.ps1",
    "tools/run_cpp_tests.ps1",
    "tools/run_cpp_bench.ps1",
    "tools/run_local_fuzz.ps1",
    "docs/chromium_integration_roadmap.md"
)

$missing = @()
foreach ($path in $requiredLocalPaths) {
    if (-not (Test-Path (Join-Path $repoRoot $path))) {
        $missing += $path
    }
}

if ($missing.Count -eq 0) {
    $localDetail = "all required local scaffold files are present"
} else {
    $localDetail = "missing: $($missing -join ', ')"
}
Write-Check "Local hot-leaf scaffold" ($missing.Count -eq 0) $localDetail

if ($ChromiumRoot -eq "") {
    Write-Check "Chromium checkout" $false "pass -ChromiumRoot <path> to validate a real Chromium tree"
} else {
    $chromiumPath = Resolve-Path $ChromiumRoot -ErrorAction SilentlyContinue
    if ($null -eq $chromiumPath) {
        Write-Check "Chromium checkout" $false "path does not exist: $ChromiumRoot"
    } else {
        $root = $chromiumPath.Path
        $isChromium = (Test-Path (Join-Path $root "build/config/rust.gni")) -and
            (Test-Path (Join-Path $root "third_party/blink")) -and
            (Test-Path (Join-Path $root "v8")) -and
            (Test-Path (Join-Path $root "mojo"))
        if ($isChromium) {
            $chromiumDetail = "found build/config/rust.gni, Blink, V8, and Mojo directories"
        } else {
            $chromiumDetail = "path is not a complete Chromium checkout: $root"
        }
        Write-Check "Chromium checkout" $isChromium $chromiumDetail

        $hasSupersize = Test-Path (Join-Path $root "tools/binary_size/supersize.py")
        if ($hasSupersize) {
            $supersizeDetail = "tools/binary_size/supersize.py is present"
        } else {
            $supersizeDetail = "supersize tooling not found under Chromium root"
        }
        Write-Check "Android supersize tooling" $hasSupersize $supersizeDetail

        $hasWebTests = Test-Path (Join-Path $root "third_party/blink/web_tests")
        if ($hasWebTests) {
            $webTestsDetail = "third_party/blink/web_tests is present"
        } else {
            $webTestsDetail = "Blink web_tests not found"
        }
        Write-Check "Blink web_tests" $hasWebTests $webTestsDetail
    }
}

Write-Host "================================================================"
Write-Host "Run local gates before any Chromium import:"
Write-Host "  powershell -ExecutionPolicy Bypass -File tools/run_all_gates.ps1"
Write-Host "================================================================"
