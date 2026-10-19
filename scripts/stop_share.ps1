$ErrorActionPreference = 'Stop'
$taskShareRoot = Split-Path -Parent $PSScriptRoot
$taskProjectPath = $taskShareRoot.Replace('\','/')
$taskTunnels = @(Get-CimInstance Win32_Process -Filter 'Name = "ngrok.exe"' | Where-Object {
    $_.CommandLine -and $_.CommandLine.Replace('\','/').Contains($taskProjectPath) -and
    $_.CommandLine.Replace('\','/').Contains('data/private/share')
})
$taskTunnelIds = @($taskTunnels.ProcessId)
foreach ($taskTunnel in ($taskTunnels | Sort-Object { $_.ParentProcessId -in $taskTunnelIds } -Descending)) {
    $taskCurrent = Get-CimInstance Win32_Process -Filter "ProcessId = $($taskTunnel.ProcessId)"
    if ($taskCurrent -and $taskCurrent.CreationDate -eq $taskTunnel.CreationDate -and
        $taskCurrent.CommandLine -eq $taskTunnel.CommandLine) {
        Stop-Process -Id $taskTunnel.ProcessId
    }
}
docker container inspect travel-agent-share --format '{{.State.Status}}' 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    docker update --restart=no travel-agent-share
    if ($LASTEXITCODE -ne 0) { throw '공유 컨테이너 자동 재시작 해제 실패' }
    docker stop travel-agent-share
    if ($LASTEXITCODE -ne 0) { throw '공유 컨테이너 중지 실패' }
}
Write-Output '공유용 터널·컨테이너를 중지했습니다. 로컬 웹과 저장 기록은 유지합니다.'
