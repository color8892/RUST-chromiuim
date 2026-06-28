# Ensure script execution fails on error
$ErrorActionPreference = "Stop"

Write-Host "================================================================"
Write-Host "           Building Rust Static Library (Release)               "
Write-Host "================================================================"
cargo build --release -p chromium_rust_perf_ffi_static

# Resolve static library path.
$libPath = "target/release/chromium_rust_perf_ffi_static.lib"
if (-not (Test-Path $libPath)) {
    $libPath = "target/release/libchromium_rust_perf_ffi_static.a"
}

if (-not (Test-Path $libPath)) {
    Write-Error "Could not find compiled Rust static library artifact."
}

Write-Host "Rust static library built successfully: $libPath"
Write-Host ""

Write-Host "================================================================"
Write-Host "           Locating C++ Compiler & Env Setup                     "
Write-Host "================================================================"

$compiler = ""
if (Get-Command clang++ -ErrorAction SilentlyContinue) {
    $compiler = "clang++"
} elseif (Get-Command cl -ErrorAction SilentlyContinue) {
    $compiler = "cl"
} else {
    Write-Host "C++ compiler not found in PATH. Searching for Visual Studio..."
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswhere) {
        $vsPath = & $vswhere -latest -property installationPath
        if ($vsPath) {
            $vsDevCmd = Join-Path $vsPath "Common7\Tools\VsDevCmd.bat"
            if (Test-Path $vsDevCmd) {
                Write-Host "Found Visual Studio Developer Command Prompt: $vsDevCmd"
                Write-Host "Importing environment variables..."
                
                $tempFile = [System.IO.Path]::GetTempFileName()
                cmd.exe /c "`"$vsDevCmd`" -arch=x64 && set > `"$tempFile`""
                Get-Content $tempFile | Foreach-Object {
                    if ($_ -match "^(.*?)=(.*)$") {
                        Set-Content "env:$($Matches[1])" $Matches[2]
                    }
                }
                Remove-Item $tempFile
                
                if (Get-Command cl -ErrorAction SilentlyContinue) {
                    $compiler = "cl"
                }
            }
        }
    }
}

if (-not $compiler) {
    Write-Error "C++ compiler (clang++ or cl.exe) could not be located. Please install Visual Studio or LLVM."
}

Write-Host "Using compiler: $compiler"
Write-Host ""

Write-Host "================================================================"
Write-Host "           Compiling C++ Mutation Fuzzer                        "
Write-Host "================================================================"

$outputExe = "cpp_fuzz/main.exe"
if (Test-Path $outputExe) {
    Remove-Item $outputExe
}

# Link system libraries just in case
$sysLibs = @("ws2_32.lib", "userenv.lib", "bcrypt.lib", "ntdll.lib")

if ($compiler -eq "clang++") {
    $compileCmd = @(
        "clang++",
        "-O3",
        "-std=c++17",
        "-I.",
        "cpp_fuzz/main.cc",
        "cpp/http_header_scanner_adapter.cc",
        "cpp/url_canonicalizer_adapter.cc",
        "cpp/mojo_validator_adapter.cc",
        "cpp/css_tokenizer_adapter.cc",
        "cpp/cookie_canonicalizer_adapter.cc",
        $libPath,
        "-o", $outputExe
    )
    foreach ($lib in $sysLibs) {
        $compileCmd += "-l$($lib.Replace('.lib', ''))"
    }
    
    Write-Host "Running: $($compileCmd -join ' ')"
    & $compileCmd[0] $compileCmd[1..($compileCmd.Length-1)]
} else {
    # MSVC cl.exe
    $compileCmd = @(
        "cl",
        "/O2",
        "/MD",
        "/std:c++17",
        "/EHsc",
        "/I.",
        "cpp_fuzz/main.cc",
        "cpp/http_header_scanner_adapter.cc",
        "cpp/url_canonicalizer_adapter.cc",
        "cpp/mojo_validator_adapter.cc",
        "cpp/css_tokenizer_adapter.cc",
        "cpp/cookie_canonicalizer_adapter.cc",
        $libPath,
        "/Fe$outputExe"
    )
    foreach ($lib in $sysLibs) {
        $compileCmd += $lib
    }
    
    Write-Host "Running: $($compileCmd -join ' ')"
    & $compileCmd[0] $compileCmd[1..($compileCmd.Length-1)]
}

if (-not (Test-Path $outputExe)) {
    Write-Error "C++ compilation failed."
}

Write-Host "C++ fuzzer compiled successfully: $outputExe"
Write-Host ""

Write-Host "================================================================"
Write-Host "           Running C++ Mutation Fuzz (5M Iterations)            "
Write-Host "================================================================"
& $outputExe $args
$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "SUCCESS: Fuzz run completed without any crashes." -ForegroundColor Green
} else {
    Write-Error "FAILURE: Fuzzer reported failure or crash. Exit code: $exitCode"
}
