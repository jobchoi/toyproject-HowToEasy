# Run in Windows PowerShell. Dedicated Python env/profile; no existing Chrome cookies.
param(
    [switch]$Diagnose,
    [string]$BlogId = 'somnium_quest',
    [ValidateSet('chrome', 'msedge', 'chromium')]
    [string]$Channel = 'chrome'
)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$stateDir = Join-Path $env:LOCALAPPDATA 'HowToEasyPosting'
$pythonEnv = Join-Path $stateDir 'venv'
$pythonExe = Join-Path $pythonEnv 'Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw 'Windows용 Python과 py 런처가 필요합니다. Python 설치 후 다시 실행하세요.'
    }
    & py -3 -m venv $pythonEnv
    if ($LASTEXITCODE -ne 0) { throw 'Windows Python 가상환경 생성 실패' }
}
& $pythonExe -m pip install -r (Join-Path $projectDir 'requirements-browser.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python 패키지 설치 실패' }
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $stateDir 'browsers'
if ($Channel -eq 'chromium') {
    & $pythonExe -m playwright install chromium --no-shell
    if ($LASTEXITCODE -ne 0) { throw 'Windows Chromium 설치 실패' }
}
$probeArgs = @((Join-Path $PSScriptRoot 'naver_browser_probe.py'), '--blog-id', $BlogId, '--channel', $Channel)
if ($Diagnose) { $probeArgs += '--diagnose' }
& $pythonExe @probeArgs
exit $LASTEXITCODE
