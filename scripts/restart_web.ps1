$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'start_web_host.ps1') -Action restart
