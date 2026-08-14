Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$files = @(
    'src/str8.asm',
    'src/str8-worker.asm',
    'src/str8-jump-eq.inc',
    'src/str8-ram-abi.inc',
    'tools/bank-maint/str8n-v1.21-bank-maint-2000.asm',
    'tools/top-update/str8n-v1.21-top-update-2000.asm'
)
$pattern = '\$(?:1A|1B|1C|1D|1E|1F)[0-9A-Fa-f]{2}(?![0-9A-Fa-f])'
$violations = [System.Collections.Generic.List[string]]::new()
foreach ($path in $files) {
    foreach ($match in Select-String -LiteralPath $path -Pattern $pattern) {
        $code = ($match.Line -split ';',2)[0]
        if ($code -match $pattern) { $violations.Add(('{0}:{1}: {2}' -f $path,$match.LineNumber,$match.Line.Trim())) }
    }
}
if ($violations.Count) { throw ("v1.2 active source allocates user low RAM:`n" + ($violations -join "`n")) }
Write-Host 'RAM ABI SOURCE CHECK = PASS; $1A00-$1FFF has no active allocation'
