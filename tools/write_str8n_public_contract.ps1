param(
    [string]$SourceDir = "src",
    [string]$OutPath = "BUILD/v1.21/include/str8n-public.inc"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$groups = @(
    [ordered]@{
        File = 'str8-ram-abi.inc'
        Names = @(
            'STR8_RAM_ABI_VERSION',
            'STR8_HIGH_TOOL_BASE', 'STR8_HIGH_TOOL_END',
            'HIM_AP_LINK_WORK_BASE', 'HIM_AP_LINK_WORK_END',
            'STR8_STATE_BASE', 'STR8_STATE_END',
            'STR8_BANK_JUMP_SIG0', 'STR8_BANK_JUMP_SIG1',
            'STR8_BANK_LAST_JUMP',
            'ASM_TARGET_END_EXCLUSIVE', 'ASM_TARGET_LAST'
        )
    },
    [ordered]@{
        File = 'str8-jump-eq.inc'
        Names = @(
            'STR8_BANK_SELECT_SERVICE', 'STR8_BANK_SELECT_RAM',
            'STR8_BANK_STATE_BYTE', 'STR8_BANK_STATE_MASK',
            'STR8_BANK_JUMP_SIG0_VALUE', 'STR8_BANK_JUMP_SIG1_VALUE',
            'STR8_BANK_COUNT', 'STR8_BANK_NONE'
        )
    },
    [ordered]@{
        File = 'str8-console-eq.inc'
        Names = @(
            'STR8_CONSOLE_INIT_SERVICE', 'STR8_ABI_QUERY_SERVICE',
            'STR8_CHARIN_SERVICE', 'STR8_CHAROUT_SERVICE',
            'STR8_CHAR_READY_SERVICE', 'STR8_RESIDENT_ABI_VERSION',
            'STR8_RESIDENT_ABI_CAPS'
        )
    },
    [ordered]@{
        File = 'str8-record-eq.inc'
        Names = @(
            'STR8_RECORD_SERVICE', 'STR8_REC_SIG0_ADDR',
            'STR8_REC_SIG1_ADDR', 'STR8_REC_VERSION_ADDR',
            'STR8_REC_CAPS_ADDR', 'STR8_REC_SIG0_VALUE',
            'STR8_REC_SIG1_VALUE', 'STR8_REC_VERSION_VALUE',
            'STR8_REC_CAPS_V2'
        )
    },
    [ordered]@{
        File = 'str8-worker-eq.inc'
        Names = @(
            'STR8_WORKER_RUN', 'STR8_WORKER_SELECT_END',
            'STR8_WORKER_SELECT_SIZE', 'STR8_WORKER_END',
            'STR8_WORKER_SIZE', 'STR8_WORKER_STORE',
            'STR8_WORKER_ABI_VERSION'
        )
    }
)

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('; Generated STR8-N public integration contract. DO NOT EDIT.')
$lines.Add('; R-YORS consumes this verified artifact; STR8-N owns the values.')
$lines.Add('')

foreach ($group in $groups) {
    $path = Join-Path $SourceDir $group.File
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required STR8-N contract source not found: $path"
    }
    [string[]]$source = Get-Content -LiteralPath $path
    foreach ($name in $group.Names) {
        $pattern = '^\s*' + [Regex]::Escape($name) + '\s+EQU\s+(.+?)\s*$'
        $matches = @($source | Where-Object { $_ -match $pattern })
        if ($matches.Count -ne 1) {
            throw "Expected one $name definition in $path; found $($matches.Count)"
        }
        $null = $matches[0] -match $pattern
        $value = $Matches[1].Trim()
        $lines.Add(('{0,-32} EQU             {1}' -f $name, $value))
    }
    $lines.Add('')
}

$parent = Split-Path -Parent $OutPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
[System.IO.File]::WriteAllLines($OutPath, $lines, [System.Text.Encoding]::ASCII)
Write-Host ('STR8-N PUBLIC ABI = {0}' -f $OutPath)
