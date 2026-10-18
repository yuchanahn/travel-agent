$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if (-not (Test-Path -LiteralPath 'data/private/brave-api-key')) {
        throw 'Brave 키 파일이 없습니다: data/private/brave-api-key'
    }
    docker compose up -d --build
    if ($LASTEXITCODE -ne 0) { throw 'Docker 웹 실행에 실패했습니다.' }
    $taskWebAddress = docker compose port web 8000
    if ($LASTEXITCODE -ne 0) { throw '배정된 포트를 확인하지 못했습니다.' }
    $taskWebUrl = 'http://' + $taskWebAddress.Trim()
    $taskReady = $false
    $taskStartupWatch = [Diagnostics.Stopwatch]::StartNew()
    while ($taskStartupWatch.Elapsed.TotalSeconds -lt 30) {
        try {
            $taskHealth = Invoke-RestMethod ($taskWebUrl + '/api/health') -TimeoutSec 5
            if ($taskHealth.status -eq 'ok') { $taskReady = $true; break }
        }
        catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $taskReady) { throw '웹 화면의 준비 상태를 확인하지 못했습니다. docker compose logs web로 확인해주세요.' }
    Write-Output ('Web UI: ' + $taskWebUrl)
}
finally { Pop-Location }
