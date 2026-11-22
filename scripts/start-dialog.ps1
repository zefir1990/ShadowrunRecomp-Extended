param(
    [string]$Rom = "",
    [string]$Exe = "",
    [int]$Port = 4378,
    [int]$DialogId = 0,
    [int]$Frame = 120,
    [switch]$Turbo
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
if (-not $Rom) { $Rom = Join-Path $root "game\shadowrun.bin" }
if (-not $Exe) { $Exe = Join-Path $root "build\ShadowrunRecomp.exe" }
foreach ($path in @($Rom, $Exe)) {
    if (-not (Test-Path $path)) { throw "missing $path" }
}
$debugIni = Join-Path (Split-Path -Parent $Exe) "debug.ini"
$settings = @(
    "port=$Port",
    "dialog_start=true",
    "dialog_id=$DialogId",
    "dialog_start_frame=$Frame"
)
Set-Content -Path $debugIni -Value $settings -Encoding ascii
$arguments = @($Rom, "--no-launcher")
if ($Turbo) { $arguments += "--turbo" }
Start-Process -FilePath $Exe -WorkingDirectory $root -ArgumentList $arguments
Write-Host "started $Exe"
Write-Host "dialog  id=$DialogId frame=$Frame"
Write-Host "port    $Port"
Write-Host "speed   $(if ($Turbo) { 'turbo' } else { 'normal' })"
Write-Host "catalog id=0 is the Hollywood Correctional Facility gate"
