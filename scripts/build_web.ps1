# Build SPA web/ → web/dist (phục vụ bởi FastAPI khi web_dist_dir tồn tại)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "web")

if (Test-Path "package-lock.json") { npm ci } else { npm install }
npm run build
Write-Host "OK: web/dist sẵn sàng."
