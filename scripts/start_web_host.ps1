param(
    [ValidateSet('start','restart','stop')][string]$Action = 'start',
    [ValidateSet(50733)][int]$Port = 50733
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskUrl = "http://127.0.0.1:$Port"
$taskRuntime = Join-Path $taskRoot 'data\private\web-runtime'

function Get-ManagedWebProcesses {
    $taskCandidates = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^python(w)?\.exe$' -and
        $_.CommandLine -match '(?:^|\s)-m\s+travel_agent\.web_app(?:\s|$)'
    })
    $taskOwned = [Collections.Generic.HashSet[int]]::new()
    foreach ($taskCandidate in $taskCandidates) {
        if ($taskCandidate.ExecutablePath -eq $taskPython) {
            [void]$taskOwned.Add([int]$taskCandidate.ProcessId)
        }
    }
    do {
        $taskPreviousCount = $taskOwned.Count
        foreach ($taskCandidate in $taskCandidates) {
            if ($taskOwned.Contains([int]$taskCandidate.ParentProcessId)) {
                [void]$taskOwned.Add([int]$taskCandidate.ProcessId)
            }
        }
    } while ($taskPreviousCount -ne $taskOwned.Count)
    @($taskCandidates | Where-Object { $taskOwned.Contains([int]$_.ProcessId) })
}

function Get-WebListeners {
    @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Stop-ManagedWeb {
    $taskProcesses = @(Get-ManagedWebProcesses)
    $taskIds = @($taskProcesses | ForEach-Object { $_.ProcessId })
    foreach ($taskProcess in ($taskProcesses | Sort-Object { $_.ParentProcessId -in $taskIds } -Descending)) {
        $taskCurrent = Get-CimInstance Win32_Process -Filter "ProcessId = $($taskProcess.ProcessId)"
        if ($taskCurrent -and $taskCurrent.CreationDate -eq $taskProcess.CreationDate -and
            $taskCurrent.CommandLine -eq $taskProcess.CommandLine) {
            Stop-Process -Id $taskProcess.ProcessId -ErrorAction Stop
        }
    }
    $taskStopWatch = [Diagnostics.Stopwatch]::StartNew()
    while (@(Get-ManagedWebProcesses).Count -gt 0 -and $taskStopWatch.Elapsed.TotalSeconds -lt 10) {
        Start-Sleep -Milliseconds 250
    }
    if (@(Get-ManagedWebProcesses).Count -gt 0) { throw '프로젝트 웹 프로세스가 아직 종료되지 않았습니다.' }
    $taskPidPath = Join-Path $taskRuntime 'launcher.pid'
    if (Test-Path -LiteralPath $taskPidPath) { Remove-Item -LiteralPath $taskPidPath }
}

$taskHasher = [Security.Cryptography.SHA256]::Create()
try { $taskHash = [BitConverter]::ToString($taskHasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($taskRoot))).Replace('-','').Substring(0,16) }
finally { $taskHasher.Dispose() }
$taskMutex = [Threading.Mutex]::new($false, "Local\TravelAgentWeb-$taskHash")
$taskLocked = $false
Push-Location $taskRoot
try {
    try { $taskLocked = $taskMutex.WaitOne(10000) }
    catch [Threading.AbandonedMutexException] { $taskLocked = $true }
    if (-not $taskLocked) { throw '다른 웹 시작·재시작 작업이 진행 중입니다.' }
    if ($Action -in @('restart','stop')) { Stop-ManagedWeb }
    if ($Action -eq 'stop') { Write-Output 'Local web stopped.'; return }

    $taskListeners = @(Get-WebListeners)
    $taskProcesses = @(Get-ManagedWebProcesses)
    if ($taskListeners.Count -gt 0) {
        if ($taskListeners.Count -eq 1 -and $taskListeners[0].LocalAddress -eq '127.0.0.1' -and
            $taskListeners[0].OwningProcess -in @($taskProcesses.ProcessId)) {
            $taskHealth = Invoke-RestMethod "$taskUrl/api/health" -TimeoutSec 5
            if ($taskHealth.status -eq 'ok') { Write-Output "Already running: $taskUrl"; return }
        }
        throw '고정 포트50733이 사용 중입니다. 다른 포트로 우회하지 않습니다.'
    }
    if ($taskProcesses.Count -gt 0) { throw '이전 웹 프로세스가 있습니다. -Action restart를 사용해주세요.' }
    New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
    if (-not $env:LLM_CONFIG_FILE -and (Test-Path -LiteralPath 'data/private/llm-config.json')) {
        $env:LLM_CONFIG_FILE = (Resolve-Path -LiteralPath 'data/private/llm-config.json').Path
    }
    $taskLauncher = Start-Process -FilePath $taskPython -ArgumentList @(
        '-m','travel_agent.web_app','--host','127.0.0.1','--port',"$Port",'--data-dir','data/private/web-host'
    ) -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $taskRuntime 'stdout.log') `
        -RedirectStandardError (Join-Path $taskRuntime 'stderr.log')
    Set-Content -LiteralPath (Join-Path $taskRuntime 'launcher.pid') -Value $taskLauncher.Id
    $taskWatch = [Diagnostics.Stopwatch]::StartNew()
    while ($taskWatch.Elapsed.TotalSeconds -lt 20) {
        $taskLauncher.Refresh()
        if ($taskLauncher.HasExited) { throw '웹 프로세스가 종료됐습니다. data/private/web-runtime/stderr.log를 확인해주세요.' }
        try {
            $taskListeners = @(Get-WebListeners)
            $taskProcesses = @(Get-ManagedWebProcesses)
            if ($taskListeners.Count -eq 1 -and $taskListeners[0].LocalAddress -eq '127.0.0.1' -and
                $taskListeners[0].OwningProcess -in @($taskProcesses.ProcessId)) {
                $taskHealth = Invoke-RestMethod "$taskUrl/api/health" -TimeoutSec 3
                if ($taskHealth.status -eq 'ok') { Write-Output "Web UI: $taskUrl"; return }
            }
        }
        catch { }
        Start-Sleep -Milliseconds 300
    }
    throw '고정 포트의 웹 서버 준비 상태를 확인하지 못했습니다.'
}
finally {
    Pop-Location
    if ($taskLocked) { $taskMutex.ReleaseMutex() }
    $taskMutex.Dispose()
}
