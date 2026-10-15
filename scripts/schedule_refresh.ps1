# Đăng ký / chạy Task Scheduler: refresh daily StockAI lúc 16:00 ICT T2–T6.
# Usage:
#   .\scripts\schedule_refresh.ps1 -Register
#   .\scripts\schedule_refresh.ps1 -RunNow
#   .\scripts\schedule_refresh.ps1 -Unregister

param(
    [switch]$Register,
    [switch]$RunNow,
    [switch]$Unregister,
    [string]$TaskName = "StockAI-RefreshDaily",
    [string]$Python = "",
    [string]$AsOf = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $Python = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    if (-not $Python) { $Python = "python" }
}

$Script = Join-Path $Root "scripts\refresh_daily.py"
$ArgList = @($Script)
if ($AsOf) {
    $ArgList += @("--as-of", $AsOf)
} else {
    $ArgList += @("--as-of", (Get-Date -Format "yyyy-MM-dd"))
}

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Unregistered $TaskName"
    exit 0
}

if ($Register) {
    $action = New-ScheduledTaskAction -Execute $Python -Argument ($ArgList -join " ") -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 4:00PM
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host "Registered $TaskName daily Mon-Fri 16:00 (local). WorkingDirectory=$Root"
    exit 0
}

if ($RunNow) {
    Write-Host "Running: $Python $($ArgList -join ' ')"
    & $Python @ArgList
    exit $LASTEXITCODE
}

Write-Host @"
StockAI schedule_refresh.ps1
  -Register     tạo task $TaskName (T2-T6 16:00)
  -RunNow       chạy refresh_daily.py ngay
  -Unregister   gỡ task
"@
