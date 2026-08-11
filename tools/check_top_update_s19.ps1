param(
    [string]$S19Path = "BUILD/v1.2/s19/str8n-v1.2-top-update-2000.s19"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$data = @{}
$entry = $null

foreach ($raw in Get-Content -LiteralPath $S19Path) {
    $line = $raw.Trim()
    if (-not $line) { continue }
    if ($line -notmatch '^S([19])([0-9A-Fa-f]+)$') { throw "Unsupported record: $line" }
    $kind = $Matches[1]
    $hex = $Matches[2]
    $bytes = for ($i=0; $i -lt $hex.Length; $i+=2) { [Convert]::ToInt32($hex.Substring($i,2),16) }
    if ($bytes[0] -ne ($bytes.Count-1)) { throw "Bad count: $line" }
    $sum=0; foreach($b in $bytes){$sum=($sum+$b)-band 0xFF}; if($sum -ne 0xFF){throw "Bad checksum: $line"}
    $address=($bytes[1]-shl 8)-bor $bytes[2]
    if($kind -eq '9'){$entry=$address; continue}
    $length=$bytes[0]-3
    $last=$address+$length-1
    if($address -lt 0x2000 -or $last -gt 0x7AFF){throw ('Top updater S1 ${0:X4}-${1:X4} is outside L RAM' -f $address,$last)}
    for($i=0;$i -lt $length;$i++){$target=$address+$i;if($data.ContainsKey($target)){throw ('Duplicate byte ${0:X4}' -f $target)};$data[$target]=$bytes[3+$i]}
}
if($entry -ne 0x2000){throw ('Top updater S9 is ${0:X4}; expected $2000' -f $entry)}
foreach($address in @(0x2000,0x4000,0x4FFF)){if(-not $data.ContainsKey($address)){throw ('Required byte ${0:X4} absent' -f $address)}}
for($address=0x4000;$address -le 0x4FFF;$address++){if(-not $data.ContainsKey($address)){throw ('Candidate image hole at ${0:X4}' -f $address)}}
Write-Host ('TOP UPDATE S19     = PASS; bytes={0}; S9=$2000; SHA256={1}' -f $data.Count,(Get-FileHash -Algorithm SHA256 -LiteralPath $S19Path).Hash)
