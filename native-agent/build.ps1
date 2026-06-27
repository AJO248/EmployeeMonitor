<#
Simple PowerShell helper to configure and build the native-agent using CMake.
Run this from an elevated or developer PowerShell on Windows.
#>
param(
    [string]$Generator = "",
    [string]$BuildDir = "build",
    [string]$Config = "Release"
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $root
if (-Not (Test-Path $BuildDir)) { New-Item -ItemType Directory -Path $BuildDir | Out-Null }

Write-Host "Configuring with CMake..."
if ($Generator) {
    cmake -S . -B $BuildDir -G $Generator
} else {
    cmake -S . -B $BuildDir
}
if ($LASTEXITCODE -ne 0) { Write-Error "CMake configure failed"; Exit 1 }

Write-Host "Building ($Config)..."
cmake --build $BuildDir --config $Config
if ($LASTEXITCODE -ne 0) { Write-Error "Build failed"; Exit 1 }

Write-Host "Build finished. Executable located under $BuildDir\$Config (or $BuildDir for single-config generators)."
Pop-Location
