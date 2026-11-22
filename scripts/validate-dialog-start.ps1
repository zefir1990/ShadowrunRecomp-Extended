param(
    [string]$Rom = "",
    [string]$Exe = "",
    [int]$DialogId = 0,
    [int]$Frame = 120
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
if (-not $Rom) { $Rom = Join-Path $root "game\shadowrun.bin" }
if (-not $Exe) { $Exe = Join-Path $root "build\ShadowrunRecomp.exe" }
$inputScript = Join-Path $here "dialog-start-probe.input"
$debugIni = Join-Path (Split-Path -Parent $Exe) "debug.ini"
$logPath = Join-Path (Split-Path -Parent $Exe) "dialog-start.log"
$screenshot = Join-Path (Split-Path -Parent $Exe) "shots\dialog-start.png"
foreach ($path in @($Rom, $Exe, $inputScript)) {
    if (-not (Test-Path $path)) { throw "missing $path" }
}
New-Item -ItemType Directory -Force (Join-Path (Split-Path -Parent $Exe) "dumps") | Out-Null
New-Item -ItemType Directory -Force (Join-Path (Split-Path -Parent $Exe) "shots") | Out-Null
Remove-Item $screenshot -ErrorAction SilentlyContinue
$originalDebugIni = $null
if (Test-Path $debugIni) { $originalDebugIni = Get-Content -Raw $debugIni }
try {
    Set-Content -Path $debugIni -Encoding ascii -Value @(
        "port=4378",
        "dialog_start=true",
        "dialog_id=$DialogId",
        "dialog_start_frame=$Frame"
    )
    Push-Location $root
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Exe $Rom --no-launcher --input-script $inputScript --turbo --max-frames 400 *> $logPath
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorAction
        Pop-Location
    }
    $log = Get-Content -Raw $logPath
    $started = $log -match "\[dialog\] start"
    $catalog = $log -match "\[dialog\] id=$DialogId "
    $crashed = $log -match "CRASH REPORT"
    $hasScreenshot = Test-Path $screenshot
    Write-Host "exit=$exitCode started=$started catalog=$catalog crashed=$crashed screenshot=$hasScreenshot"
    if ($exitCode -ne 0 -or -not $started -or -not $catalog -or $crashed -or -not $hasScreenshot) {
        Write-Error "dialog start validation failed; see $logPath"
        exit 1
    }
    Write-Host "dialog start validation passed (id=$DialogId frame=$Frame)"
} finally {
    if ($null -eq $originalDebugIni) {
        Remove-Item $debugIni -ErrorAction SilentlyContinue
    } else {
        Set-Content -Path $debugIni -Value $originalDebugIni -Encoding ascii -NoNewline
    }
}
