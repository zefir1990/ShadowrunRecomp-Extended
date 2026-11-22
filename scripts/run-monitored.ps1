param(
    [string]$Rom = "",
    [string]$Exe = "",
    [string]$ReportDir = "",
    [string]$InputScript = "",
    [switch]$Turbo
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
if (-not $Rom) { $Rom = Join-Path $root "game\shadowrun.bin" }
if (-not $Exe) { $Exe = Join-Path $root "build\ShadowrunRecomp.exe" }
if (-not $ReportDir) { $ReportDir = Join-Path $root "build\crash-reports" }
$buildDirectory = Split-Path -Parent $Exe
$stderrLog = Join-Path $buildDirectory "monitor-stderr.log"
$stdoutLog = Join-Path $buildDirectory "monitor-stdout.log"
$errorLog = Join-Path $buildDirectory "last_error.log"
$debugIni = Join-Path $buildDirectory "debug.ini"
Set-Content -Path $debugIni -Value "port=4378" -Encoding ascii
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$errorLogBefore = if (Test-Path $errorLog) { (Get-Item $errorLog).Length } else { -1 }

$arguments = @($Rom, "--no-launcher")
if ($InputScript) { $arguments += @("--input-script", $InputScript) }
if (-not $Turbo) { $arguments += "--turbo" }
$started = Get-Date
$process = Start-Process -FilePath $Exe -WorkingDirectory $root -ArgumentList $arguments `
    -RedirectStandardError $stderrLog -RedirectStandardOutput $stdoutLog -PassThru
Write-Host "monitoring pid $($process.Id), report dir $ReportDir"
$process.WaitForExit()
$exitCode = $process.ExitCode
$finished = Get-Date

$errorLogAfter = if (Test-Path $errorLog) { (Get-Item $errorLog).Length } else { -1 }
$runnerCrash = $errorLogAfter -ne $errorLogBefore
$hardCrash = ($exitCode -ne 0) -and -not $runnerCrash
if ($exitCode -eq 0 -and -not $runnerCrash) {
    Write-Host "clean exit"
    exit 0
}

$report = Join-Path $ReportDir ("crash-{0}.md" -f $finished.ToString("yyyyMMdd-HHmmss"))
$lines = @(
    "# Crash report",
    "",
    "- started: $($started.ToString('s'))",
    "- finished: $($finished.ToString('s'))",
    "- exit code: $exitCode",
    "- runner crash log: $(if ($runnerCrash) { 'written' } else { 'not written' })",
    "- stderr log: $stderrLog",
    ""
)
if ($runnerCrash) {
    $lines += @("## last_error.log", "", '```', (Get-Content $errorLog -Tail 60 | Out-String).Trim(), '```', "")
}
if (Test-Path $stderrLog) {
    $lines += @("## runner stderr (tail)", "", '```', (Get-Content $stderrLog -Tail 120 | Out-String).Trim(), '```', "")
}
$lines | Set-Content -Path $report -Encoding utf8
Write-Host "CRASH: exit code $exitCode, report $report"
exit 3
