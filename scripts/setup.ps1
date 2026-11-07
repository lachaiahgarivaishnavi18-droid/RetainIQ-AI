$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if (Get-Command uv -ErrorAction SilentlyContinue) { uv venv --python 3.12 .venv }
    else { py -3.12 -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 (or uv) and retry.' }
}
if (Test-Path -LiteralPath '.tools\bin\uv.exe') { & '.\.tools\bin\uv.exe' pip install --python .venv\Scripts\python.exe -r backend/requirements.txt }
else { & '.\.venv\Scripts\python.exe' -m ensurepip; & '.\.venv\Scripts\python.exe' -m pip install -r backend/requirements.txt }
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
Set-Location -LiteralPath (Join-Path $root 'frontend')
$bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\pnpm\bin\pnpm.cjs'
if (Get-Command pnpm -ErrorAction SilentlyContinue) { pnpm install --frozen-lockfile }
elseif (Test-Path -LiteralPath $bundled) { node $bundled install --frozen-lockfile }
else { throw 'Install pnpm, then retry setup.' }
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
Write-Host 'Setup complete. Run .\scripts\start.ps1 from the project root.'
