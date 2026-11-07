$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts/setup.ps1 first.' }
$pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
$bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\pnpm\bin\pnpm.cjs'
if ($pnpm) { $frontendCommand = 'pnpm run dev' }
elseif (Test-Path -LiteralPath $bundled) { $frontendCommand = "node `"$bundled`" run dev" }
else { throw 'Install Node.js and pnpm before starting.' }
$backendArgs = "-NoProfile -Command Set-Location -LiteralPath '$root\backend'; & '$python' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
$frontendArgs = "-NoProfile -Command Set-Location -LiteralPath '$root\frontend'; $frontendCommand"
Start-Process powershell.exe -ArgumentList $backendArgs -WindowStyle Hidden
Start-Process powershell.exe -ArgumentList $frontendArgs -WindowStyle Hidden
Write-Host 'RetainIQ is starting at http://127.0.0.1:5174 (API docs: http://127.0.0.1:8000/docs).'
Write-Host 'The first local account is the administrator. Import demo data from Data Import.'
