$ErrorActionPreference = "Stop"

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Native command failed with exit code $LASTEXITCODE"
    }
}

Write-Host "================================================================"
Write-Host "        Standalone Chromium Rust Readiness Suite                "
Write-Host "================================================================"
Write-Host "This suite is intentionally lightweight. It does not replace"
Write-Host "tools/run_all_gates.ps1 for release-quality C++/Rust validation."
Write-Host ""

Write-Host ">>> Python unit tests"
Invoke-NativeChecked { python -m unittest discover -s tests }

Write-Host ">>> P0 registry and corpus contracts"
Invoke-NativeChecked { python tools/check_p0_hot_leaf_registry.py }
Invoke-NativeChecked { python tools/check_fuzz_corpus_manifest.py }

Write-Host ">>> Chromium import and integration contracts"
Invoke-NativeChecked { python tools/check_chromium_import_consistency.py }
Invoke-NativeChecked { python tools/check_chromium_integration_checklist.py }
Invoke-NativeChecked { python tools/check_chromium_checkout_preflight.py }
Invoke-NativeChecked { python tools/check_chromium_next_tasks.py }

Write-Host ">>> Performance stability settings"
Invoke-NativeChecked { python tools/check_perf_stability.py }

Write-Host ">>> Reports"
Invoke-NativeChecked { python tools/emit_fuzz_corpus_report.py }
Invoke-NativeChecked { python tools/emit_p0_artifact_summary.py }
Invoke-NativeChecked { python tools/emit_chromium_import_report.py }
Invoke-NativeChecked { python tools/emit_chromium_cl_handoff.py }
Invoke-NativeChecked { python tools/emit_standalone_readiness_report.py }
Invoke-NativeChecked { python tools/emit_reports_manifest.py }

Write-Host ""
Write-Host "================================================================"
Write-Host " Standalone readiness suite completed successfully.             "
Write-Host " Reports are under target/reports/.                             "
Write-Host "================================================================" -ForegroundColor Green
