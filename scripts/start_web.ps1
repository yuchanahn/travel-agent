param([ValidateSet('start','restart','stop')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'start_web_host.ps1') -Action $Action
