<#
Fixes the reachy_mini / gstreamer_libs libexpat.dll shadowing bug on Windows.

See SETUP.md for the full explanation. gstreamer_libs bundles its own libexpat.dll
and injects its bin/ dir onto PATH via a .pth hook, which shadows the interpreter's
own libexpat.dll and crashes pyexpat imports. Renaming the shadowing DLL to .bak
fixes it; safe to re-run (idempotent).

Usage:
  .\fix_libexpat.ps1 -PythonEnvRoot "C:\Users\<you>\miniconda3\envs\reachy"
  .\fix_libexpat.ps1 -PythonEnvRoot "..\reachy-mini-mcp\.venv"
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$PythonEnvRoot
)

$dllPath = Join-Path $PythonEnvRoot "Lib\site-packages\gstreamer_libs\bin\libexpat.dll"
$bakPath = "$dllPath.bak"

if (Test-Path $bakPath) {
    Write-Host "Already fixed: $bakPath exists."
} elseif (Test-Path $dllPath) {
    Rename-Item -Path $dllPath -NewName "libexpat.dll.bak"
    Write-Host "Fixed: renamed $dllPath -> $bakPath"
} else {
    Write-Host "Nothing to fix: $dllPath not found (gstreamer_libs not installed here, or already fixed)."
}
