$ErrorActionPreference = 'Stop'
$ollamaBase = 'http://127.0.0.1:11434'
$ollamaModel = 'qwen3.5:4b-q4_K_M'

function Invoke-OllamaChat($request) {
    $json = $request | ConvertTo-Json -Depth 25
    Invoke-RestMethod "$ollamaBase/api/chat" -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($json)) -TimeoutSec 180
}

function Get-Metrics($reply) {
    [ordered]@{
        done = $reply.done
        done_reason = $reply.done_reason
        total_seconds = [math]::Round($reply.total_duration / 1e9, 3)
        load_seconds = [math]::Round($reply.load_duration / 1e9, 3)
        output_tokens = $reply.eval_count
        tokens_per_second = if ($reply.eval_duration -gt 0) { [math]::Round($reply.eval_count / ($reply.eval_duration / 1e9), 2) } else { $null }
    }
}

$options = @{ num_ctx = 4096; num_predict = 256; temperature = 0 }
$koreanReply = Invoke-OllamaChat @{
    model = $ollamaModel; stream = $false; think = $false; options = $options
    messages = @(
        @{ role = 'system'; content = '한국어로 간결하게 답하세요. 실시간 조회하지 않은 가격과 운영시간을 확정하지 마세요.' },
        @{ role = 'user'; content = '서울에서 출발해 차 없이 두 명이 총 40만 원 예산으로 1박 2일 여행을 하려고 해. 후보 지역 두 곳과 선택 이유를 세 문장 이내로 알려줘. 확정 가격은 필요 없어.' }
    )
}
Write-Output ('KOREAN_RESPONSE: ' + $koreanReply.message.content)

$tool = @{
    type = 'function'
    function = @{
        name = 'search_trips'
        description = '사용자 조건에 맞는 여행 후보를 조회한다.'
        parameters = @{
            type = 'object'
            properties = @{
                origin = @{ type = 'string'; description = '출발 도시' }
                budget_total_krw = @{ type = 'integer'; description = '전체 인원 총예산, 원' }
                travelers = @{ type = 'integer' }
                has_car = @{ type = 'boolean' }
            }
            required = @('origin','budget_total_krw','travelers','has_car')
        }
    }
}
$messages = @(
    @{ role = 'system'; content = '여행 후보를 제안하기 전에 search_trips 도구로 조회하세요. 반환된 데이터만 근거로 답하세요.' },
    @{ role = 'user'; content = '서울 출발, 차 없이 두 명, 전체 총예산 40만 원으로 여행 후보를 찾아줘.' }
)
$toolReply = Invoke-OllamaChat @{
    model = $ollamaModel; stream = $false; think = $false; options = $options
    messages = $messages; tools = @($tool)
}
$calls = @($toolReply.message.tool_calls)
$validCall = $false
$finalReply = $null
if ($calls.Count -eq 1 -and $calls[0].function.name -eq 'search_trips') {
    $arguments = $calls[0].function.arguments
    $validCall = ($arguments.origin -eq '서울' -and $arguments.budget_total_krw -eq 400000 -and $arguments.travelers -eq 2 -and $arguments.has_car -eq $false)
    if ($validCall) {
        # Fixed fixture, not a live travel search or verified market price.
        $fixture = @{ test_fixture = $true; trips = @(@{ destination = '춘천'; transport = '대중교통'; estimated_total_krw = 280000; price_verified = $false }); note = '동작 테스트용 가상 데이터이며 실제 가격은 조회하지 않았습니다.' } | ConvertTo-Json -Depth 8 -Compress
        $messages += $toolReply.message
        $messages += @{ role = 'tool'; tool_name = 'search_trips'; content = $fixture }
        $finalReply = Invoke-OllamaChat @{
            model = $ollamaModel; stream = $false; think = $false; options = $options
            messages = $messages; tools = @($tool)
        }
        Write-Output ('TOOL_FINAL_RESPONSE: ' + $finalReply.message.content)
    }
}
$loaded = Invoke-RestMethod "$ollamaBase/api/ps" -TimeoutSec 5
$report = [ordered]@{
    model = $ollamaModel
    tested_at = (Get-Date).ToString('o')
    context_tokens = 4096
    thinking = $false
    korean_response = $koreanReply.message.content
    korean_metrics = Get-Metrics $koreanReply
    korean_text_present = [bool]($koreanReply.message.content -match '[가-힣]')
    tool_calls = $calls
    tool_arguments_valid = $validCall
    tool_metrics = Get-Metrics $toolReply
    fixture_notice = 'Tool execution used fixed synthetic data, not a live travel search.'
    final_response = if ($finalReply) { $finalReply.message.content } else { $null }
    final_metrics = if ($finalReply) { Get-Metrics $finalReply } else { $null }
    running_models = $loaded.models
}
$reportPath = Join-Path $PSScriptRoot 'ollama-smoke-test-results.json'
$report | ConvertTo-Json -Depth 25 | Set-Content -LiteralPath $reportPath -Encoding utf8
$report | ConvertTo-Json -Depth 25
if (-not $report.korean_text_present -or -not $validCall -or -not $finalReply.message.content) { throw 'One or more smoke checks failed; inspect the report.' }
