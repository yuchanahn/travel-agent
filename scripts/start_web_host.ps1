param([int]$Port = 50730)
$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & '.\.venv\Scripts\python.exe' -m travel_agent.web_app --host 127.0.0.1 --port $Port --data-dir data/private/web-host
    if ($LASTEXITCODE -ne 0) { throw '호스트 웹 실행에 실패했습니다.' }
}
finally { Pop-Location }
