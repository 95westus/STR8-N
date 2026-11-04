param([switch]$Raw)
$ErrorActionPreference = 'Stop'
$taskPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskPython = (Get-Command python -ErrorAction Stop).Source
}
$taskScript = Join-Path $PSScriptRoot 'teraterm_boot.py'
$taskArguments = @('-B', ('"' + $taskScript + '"'), '--launch')
if ($Raw) { $taskArguments += '--raw' }
Start-Process -FilePath $taskPython -ArgumentList $taskArguments -WindowStyle Hidden
