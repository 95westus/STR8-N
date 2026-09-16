param(
    [string]$Root = $PSScriptRoot,
    [System.Collections.IDictionary]$SourceFiles = @{},
    [string]$RepositoryRoot = '',
    [string]$Commit = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
$linkPattern = '(?<prefix>!?\[[^\]\r\n]*\]\()(?<target>[^)\r\n]+)(?<suffix>\))'
$utf8 = [Text.UTF8Encoding]::new($false)

# Build mode rewrites copies only. Original manuals and historical evidence
# are never changed by this tool. Verification mode performs no writes.
if ($SourceFiles.Count) {
    if ($Commit -notmatch '^[0-9a-fA-F]{40}$') { throw 'Documentation requires a full source commit' }
    $repoFull = [IO.Path]::GetFullPath($RepositoryRoot).TrimEnd('\', '/')
    $repoPrefix = $repoFull + [IO.Path]::DirectorySeparatorChar
    $destBySource = @{}
    foreach ($entry in $SourceFiles.GetEnumerator()) {
        $source = [IO.Path]::GetFullPath((Join-Path $repoFull $entry.Value))
        $destBySource[$source] = [IO.Path]::GetFullPath((Join-Path $rootFull $entry.Key))
    }
    foreach ($entry in $SourceFiles.GetEnumerator()) {
        if (-not $entry.Key.EndsWith('.md')) { continue }
        $source = [IO.Path]::GetFullPath((Join-Path $repoFull $entry.Value))
        $destination = [IO.Path]::GetFullPath((Join-Path $rootFull $entry.Key))
        $sourceDir = Split-Path -Parent $source
        $destDirUri = [Uri]::new((Split-Path -Parent $destination) + [IO.Path]::DirectorySeparatorChar)
        $markdown = [IO.File]::ReadAllText($source)
        $rewriter = [Text.RegularExpressions.MatchEvaluator]{
            param($match)
            $target = $match.Groups['target'].Value
            if ($target -match '^[a-zA-Z][a-zA-Z0-9+.-]*:' -or $target.StartsWith('#')) {
                return $match.Value
            }
            $parts = $target.Split([char[]]'#', 2)
            $pathPart = [Uri]::UnescapeDataString($parts[0].Trim('<', '>'))
            $anchor = if ($parts.Count -gt 1) { '#' + $parts[1] } else { '' }
            $resolved = [IO.Path]::GetFullPath((Join-Path $sourceDir $pathPart))
            if (-not (Test-Path -LiteralPath $resolved)) { throw "Missing documentation source target: $source -> $target" }
            if ($destBySource.ContainsKey($resolved)) {
                $mapped = $destDirUri.MakeRelativeUri([Uri]::new($destBySource[$resolved])).ToString() + $anchor
            } else {
                if (-not $resolved.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                    throw "Documentation source target is outside the repository: $target"
                }
                $relative = $resolved.Substring($repoPrefix.Length).Replace('\', '/')
                $kind = if (Test-Path -LiteralPath $resolved -PathType Container) { 'tree' } else { 'blob' }
                $mapped = 'https://github.com/95westus/STR8-N/' + $kind + '/' + $Commit + '/' + $relative + $anchor
            }
            return $match.Groups['prefix'].Value + $mapped + $match.Groups['suffix'].Value
        }.GetNewClosure()
        [IO.File]::WriteAllText($destination, [regex]::Replace($markdown, $linkPattern, $rewriter), $utf8)
    }
}

function Get-MarkdownAnchors {
    param([string]$Path)
    $anchors = @{}
    $duplicates = @{}
    $fenced = $false
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        if ($line -match '^\s{0,3}(?:\x60{3,}|~{3,})') { $fenced = -not $fenced; continue }
        if ($fenced -or $line -notmatch '^#{1,6}\s+(.+?)\s*#*\s*$') { continue }
        $heading = $Matches[1].ToLowerInvariant()
        $heading = [regex]::Replace($heading, '\[([^\]]+)\]\([^)]+\)', '$1')
        $slug = [regex]::Replace($heading, '[^\p{L}\p{N}_ \-]', '').Replace(' ', '-')
        if ($duplicates.ContainsKey($slug)) {
            $duplicates[$slug]++
            $anchor = $slug + '-' + $duplicates[$slug]
        } else {
            $duplicates[$slug] = 0
            $anchor = $slug
        }
        $anchors[$anchor] = $true
    }
    return $anchors
}

$anchorCache = @{}
$localCount = 0
$externalCount = 0
foreach ($file in Get-ChildItem -LiteralPath $rootFull -Recurse -File -Filter '*.md') {
    foreach ($match in [regex]::Matches([IO.File]::ReadAllText($file.FullName), $linkPattern)) {
        $target = $match.Groups['target'].Value
        if ($target -match '^[a-zA-Z][a-zA-Z0-9+.-]*:') { $externalCount++; continue }
        $parts = $target.Split([char[]]'#', 2)
        $pathPart = [Uri]::UnescapeDataString($parts[0].Trim('<', '>'))
        $resolved = if ($pathPart) {
            [IO.Path]::GetFullPath((Join-Path $file.DirectoryName $pathPart))
        } else { $file.FullName }
        if (-not $resolved.StartsWith($rootFull + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
                -not (Test-Path -LiteralPath $resolved)) {
            throw "Broken or escaping package link: $($file.Name) -> $target"
        }
        if ($parts.Count -gt 1 -and $parts[1] -and $resolved.EndsWith('.md')) {
            if (-not $anchorCache.ContainsKey($resolved)) { $anchorCache[$resolved] = Get-MarkdownAnchors $resolved }
            $anchor = [Uri]::UnescapeDataString($parts[1])
            if (-not $anchorCache[$resolved].ContainsKey($anchor)) {
                throw "Missing package heading: $($file.Name) -> $target"
            }
        }
        $localCount++
    }
}
Write-Host ('PACKAGE MANUAL LINKS = PASS; {0} local targets/headings; {1} external references (not fetched)' -f $localCount, $externalCount)
