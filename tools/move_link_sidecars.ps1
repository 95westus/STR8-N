param(
    [Parameter(Mandatory = $true)][string]$S19Path,
    [Parameter(Mandatory = $true)][string]$MapDir,
    [Parameter(Mandatory = $true)][string]$SymDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$s19Full = [IO.Path]::GetFullPath($S19Path)
if (-not (Test-Path -LiteralPath $s19Full -PathType Leaf)) {
    throw "Linked S19 is missing: $s19Full"
}

$stem = [IO.Path]::Combine(
    [IO.Path]::GetDirectoryName($s19Full),
    [IO.Path]::GetFileNameWithoutExtension($s19Full)
)

foreach ($sidecar in @(
        @{ Extension = '.map'; Directory = $MapDir },
        @{ Extension = '.sym'; Directory = $SymDir }
    )) {
    $source = $stem + $sidecar.Extension
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Linker sidecar is missing: $source"
    }
    $destinationDir = [IO.Path]::GetFullPath($sidecar.Directory)
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    $destination = Join-Path $destinationDir ([IO.Path]::GetFileName($source))
    Move-Item -LiteralPath $source -Destination $destination -Force
}

