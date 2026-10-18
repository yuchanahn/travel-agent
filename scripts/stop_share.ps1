$ErrorActionPreference = 'Stop'
$taskShareRoot = Split-Path -Parent $PSScriptRoot
$taskPidFile = Join-Path $taskShareRoot 'data/private/share/ngrok.pid'
if (Test-Path -LiteralPath $taskPidFile) {
    $taskSharePid = [int](Get-Content -LiteralPath $taskPidFile -Raw).Trim()
    $taskShareProcess = Get-Process -Id $taskSharePid -ErrorAction SilentlyContinue
    if ($taskShareProcess -and $taskShareProcess.ProcessName -eq 'ngrok') {
        Stop-Process -Id $taskSharePid
    }
}
docker container inspect travel-agent-share --format '{{.State.Status}}' 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { docker stop travel-agent-share }
Write-Output '공유용 터널·컨테이너를 중지했습니다. 로컬 웹과 저장 기록은 유지합니다.'
