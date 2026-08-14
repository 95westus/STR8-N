param(
    [string]$S19Path = "BUILD/v1.21/s19/str8n-v1.21-top-update-2000.s19",
    [string]$TopBinPath = "BUILD/v1.21/bin/str8n-v1.21-bank3-f000-ffff.bin",
    [switch]$DirectoryRefresh
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

[byte[]]$toolBytes = for($address=0x2000;$address -lt 0x4000;$address++){
    if($data.ContainsKey($address)){[byte]$data[$address]}
}
$toolText = [System.Text.Encoding]::ASCII.GetString($toolBytes)
$requiredText = if($DirectoryRefresh){
    @('STR8-N 1.21 DIRECTORY REFRESH')
}else{
    @('STR8-N 1.21 TOP UPDATE','TYPE STR8-N 1.21> ',
      'STR8-N 1.21 VERIFIED; RESET')
}
foreach($text in $requiredText){
    if(-not $toolText.Contains($text)){throw "Top updater is missing required text: $text"}
}

[byte[]]$top = [System.IO.File]::ReadAllBytes($TopBinPath)
if($top.Length -ne 0x1000){throw ('Top BIN is {0} bytes; expected 4096' -f $top.Length)}
for($offset=0;$offset -lt 0x1000;$offset++){
    if($data[0x4000+$offset] -ne $top[$offset]){throw ('Candidate differs from top BIN at ${0:X3}' -f $offset)}
}

if($DirectoryRefresh){
    for($offset=0x0FB0;$offset -le 0x0FF9;$offset++){
        if($data[0x4000+$offset] -ne 0xFF){throw ('Directory-refresh candidate byte ${0:X3} is not erased' -f $offset)}
    }
    $code = for($address=0x2000;$address -lt 0x4000;$address++){if($data.ContainsKey($address)){[byte]$data[$address]}}
    for($offset=0;$offset -le $code.Count-3;$offset++){
        if($code[$offset] -eq 0x9D -and $code[$offset+1] -eq 0xB0 -and $code[$offset+2] -eq 0x19){
            throw 'Directory-refresh build still contains the live-metadata overlay store'
        }
    }
}

$label = if($DirectoryRefresh){'DIRECTORY REFRESH S19'}else{'TOP UPDATE S19'}
Write-Host ('{0,-21} = PASS; bytes={1}; S9=$2000; SHA256={2}' -f $label,$data.Count,(Get-FileHash -Algorithm SHA256 -LiteralPath $S19Path).Hash)
