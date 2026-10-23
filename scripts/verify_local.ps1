param([string]$NodePath)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPreviousMcp = $env:MCP_CONFIG_FILE
Push-Location $taskRoot
try {
    if (-not $NodePath) {
        $taskBundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
        $NodePath = if (Test-Path -LiteralPath $taskBundledNode) { $taskBundledNode } else { (Get-Command node -ErrorAction Stop).Source }
    }
    $taskNodeVersion = & $NodePath --version
    if ($LASTEXITCODE -ne 0 -or [int]($taskNodeVersion.TrimStart('v').Split('.')[0]) -lt 24) {
        throw 'Use Node.js 24 or newer via -NodePath. This script does not install a runtime.'
    }
    Write-Output "Node: $taskNodeVersion"
    # Contract tests use local fixtures; never discover personal MCP servers.
    $env:MCP_CONFIG_FILE = (Resolve-Path -LiteralPath 'examples/mcp-servers.example.json').Path
    & '.\.venv\Scripts\python.exe' -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Python contract tests failed.' }
    foreach ($taskTest in @('test_chat_continuation.cjs','test_chat_deletion.cjs','test_comparison.cjs','test_evidence_links.cjs','test_execution_metrics.cjs')) {
        & $NodePath (Join-Path 'tests' $taskTest)
        if ($LASTEXITCODE -ne 0) { throw "JavaScript check failed: $taskTest" }
    }
    & $NodePath --test tests/test_google_dom_fixture.cjs tests/test_google_record_matrix.cjs
    if ($LASTEXITCODE -ne 0) { throw 'Archived HTTP research fixture checks failed.' }
    Write-Output 'PASS: local contracts and JS checks. No live recommendation quality or browser screenshot is implied.'
}
finally {
    if ($null -eq $taskPreviousMcp) { Remove-Item Env:MCP_CONFIG_FILE -ErrorAction SilentlyContinue }
    else { $env:MCP_CONFIG_FILE = $taskPreviousMcp }
    Pop-Location
}
