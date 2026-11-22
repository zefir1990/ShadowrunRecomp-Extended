param(
    [string]$Rom = "",
    [string]$Exe = "",
    [int]$Port = 4378,
    [switch]$Paced
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
if (-not $Rom) { $Rom = Join-Path $root "game\shadowrun.bin" }
if (-not $Exe) { $Exe = Join-Path $root "build\ShadowrunRecomp.exe" }
$route = Join-Path $root "scripts\samurai-dialog.input"
foreach ($path in @($Rom, $Exe, $route)) {
    if (-not (Test-Path $path)) { throw "missing $path" }
}
$debugIni = Join-Path (Split-Path -Parent $Exe) "debug.ini"
Set-Content -Path $debugIni -Value "port=$Port" -Encoding ascii
$arguments = @($Rom, "--no-launcher", "--input-script", $route)
if (-not $Paced) { $arguments += "--turbo" }
Start-Process -FilePath $Exe -WorkingDirectory $root -ArgumentList $arguments
Write-Host "started $Exe"
Write-Host "route   $route (Samurai, motel manager dialog at frame 6265)"
Write-Host "port    $Port"
Write-Host "speed   $(if ($Paced) { 'paced' } else { 'turbo until the dialog' })"
