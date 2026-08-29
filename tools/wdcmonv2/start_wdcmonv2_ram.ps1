param(
    [string]$Port,
    [string]$ImagePath,
    [int]$BaudRate = 115200,
    [int]$ChunkBytes = 256,
    [string]$TranscriptPath,
    [string]$EventLogPath,
    [string]$TransferPath,
    [string]$Transfer2Path,
    [switch]$NoReset,
    [switch]$PhysicalResetGate,
    [int]$PhysicalResetArmSeconds = 0,
    [switch]$TerminalOnly,
    [switch]$NoTerminal,
    [switch]$Force,
    [switch]$ValidateOnly,
    [switch]$ListPorts,
    [switch]$ProbeOnly,
    [int]$ListenOnlySeconds = 0,
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

class Wdcmonv2ProtocolMock {
    [System.Collections.Generic.Queue[byte]]$Receive
    [System.Collections.Generic.List[byte]]$Sent
    [System.Collections.Generic.List[byte]]$Commands
    [System.Collections.Generic.List[byte]]$Payload
    [byte[]]$Memory
    [string]$State
    [int]$SyncIndex
    [int]$Need
    [byte]$Command
    [int]$ExecutedAddress

    Wdcmonv2ProtocolMock() {
        $this.Receive = [System.Collections.Generic.Queue[byte]]::new()
        $this.Sent = [System.Collections.Generic.List[byte]]::new()
        $this.Commands = [System.Collections.Generic.List[byte]]::new()
        $this.Payload = [System.Collections.Generic.List[byte]]::new()
        $this.Memory = New-Object byte[] 65536
        $this.State = 'SYNC'
        $this.SyncIndex = 0
        $this.ExecutedAddress = -1
    }

    [void] EnqueueBoardInfo() {
        foreach ($byte in [byte[]]@(0x53,0x58,0x42,0x32,0x7B,0,0,0,0xC8,0,0,0)) { $this.Receive.Enqueue($byte) }
    }

    [int] DecodeU24([int]$Offset) {
        return [int]$this.Payload[$Offset] -bor ([int]$this.Payload[$Offset + 1] -shl 8) -bor ([int]$this.Payload[$Offset + 2] -shl 16)
    }

    [void] ProcessByte([byte]$Value) {
        $this.Sent.Add($Value)
        if ($this.State -eq 'SYNC') {
            $expected = if ($this.SyncIndex -eq 0) { 0x55 } else { 0xAA }
            if ($Value -ne $expected) { throw ('Mock expected sync ${0:X2}, received ${1:X2}' -f $expected, $Value) }
            $this.SyncIndex++
            if ($this.SyncIndex -eq 2) {
                $this.SyncIndex = 0
                $this.Receive.Enqueue([byte]0xCC)
                $this.State = 'COMMAND'
            }
            return
        }
        if ($this.State -eq 'COMMAND') {
            $this.Command = $Value
            $this.Commands.Add($Value)
            $this.Payload.Clear()
            if ($Value -eq 0x0C) {
                $this.EnqueueBoardInfo()
                $this.State = 'SYNC'
            } elseif ($Value -eq 0x02 -or $Value -eq 0x03) {
                $this.Need = 6
                $this.State = 'HEADER'
            } elseif ($Value -eq 0x06) {
                $this.Need = 3
                $this.State = 'HEADER'
            } else {
                throw ('Mock rejects unsupported command ${0:X2}' -f $Value)
            }
            return
        }

        $this.Payload.Add($Value)
        if ($this.State -eq 'HEADER' -and $this.Payload.Count -eq $this.Need) {
            $address = $this.DecodeU24(0)
            if ($this.Command -eq 0x06) {
                $this.ExecutedAddress = $address
                $this.State = 'SYNC'
                return
            }
            $length = $this.DecodeU24(3)
            if ($address -lt 0 -or $length -lt 0 -or ($address + $length) -gt $this.Memory.Length) {
                throw 'Mock memory range is invalid'
            }
            if ($this.Command -eq 0x03) {
                for ($i = 0; $i -lt $length; $i++) { $this.Receive.Enqueue($this.Memory[$address + $i]) }
                $this.State = 'SYNC'
            } else {
                $this.Need = 6 + $length
                if ($length -eq 0) {
                    $this.Receive.Enqueue([byte]0)
                    $this.State = 'SYNC'
                } else {
                    $this.State = 'WRITE'
                }
            }
            return
        }
        if ($this.State -eq 'WRITE' -and $this.Payload.Count -eq $this.Need) {
            $address = $this.DecodeU24(0)
            $length = $this.DecodeU24(3)
            for ($i = 0; $i -lt $length; $i++) { $this.Memory[$address + $i] = $this.Payload[6 + $i] }
            $this.Receive.Enqueue([byte]0)
            $this.State = 'SYNC'
        }
    }

    [void] Write([byte[]]$Buffer, [int]$Offset, [int]$Count) {
        for ($i = 0; $i -lt $Count; $i++) { $this.ProcessByte($Buffer[$Offset + $i]) }
    }

    [int] Read([byte[]]$Buffer, [int]$Offset, [int]$Count) {
        if ($this.Receive.Count -eq 0) { throw [System.TimeoutException]::new('Mock receive queue is empty') }
        $actual = [Math]::Min($Count, $this.Receive.Count)
        for ($i = 0; $i -lt $actual; $i++) { $Buffer[$Offset + $i] = $this.Receive.Dequeue() }
        return $actual
    }
}

$script:WdcSync0 = [byte]0x55
$script:WdcSync1 = [byte]0xAA
$script:WdcReady = [byte]0xCC
$script:WdcWriteMemory = [byte]0x02
$script:WdcReadMemory = [byte]0x03
$script:WdcExecuteMemory = [byte]0x06
$script:WdcBoardInfo = [byte]0x0C
$script:EventWriter = $null

function Write-SessionEvent {
    param([Parameter(Mandatory = $true)][string]$Text)
    if ($null -eq $script:EventWriter) { return }
    $script:EventWriter.WriteLine(('{0} {1}' -f ([DateTime]::UtcNow.ToString('o')), $Text))
    $script:EventWriter.Flush()
}

function Get-ByteSha256 {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-', '') } finally { $sha.Dispose() }
}

function Convert-ToByteArray {
    param([Parameter(Mandatory = $true)][object[]]$Values)
    $bytes = New-Object byte[] $Values.Count
    for ($i = 0; $i -lt $Values.Count; $i++) { $bytes[$i] = [byte]$Values[$i] }
    return $bytes
}

function Convert-ToU24LE {
    param([Parameter(Mandatory = $true)][int64]$Value)
    if ($Value -lt 0 -or $Value -gt 0xFFFFFF) { throw ('Value does not fit a WDCMONv2 u24: {0}' -f $Value) }
    return (Convert-ToByteArray @(
        ($Value -band 0xFF),
        (($Value -shr 8) -band 0xFF),
        (($Value -shr 16) -band 0xFF)
    ))
}

function Get-Fnv1a32 {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)
    [uint32]$hash = 2166136261
    foreach ($byte in $Bytes) {
        $mixed = [uint32]($hash -bxor [uint32]$byte)
        $hash = [uint32](([uint64]$mixed * [uint64]16777619) -band [uint64]4294967295)
    }
    return $hash
}

function Get-HostFullPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    if ([System.IO.Path]::IsPathRooted($Path)) { return [System.IO.Path]::GetFullPath($Path) }
    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Path))
}

function Read-MigrationS19 {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "S19 image not found: $Path" }
    $memory = [System.Collections.Generic.SortedDictionary[int,byte]]::new()
    [int]$entry = -1
    $lineNumber = 0

    foreach ($raw in (Get-Content -LiteralPath $Path)) {
        $lineNumber++
        $line = $raw.Trim()
        if ($line.Length -eq 0) { continue }
        if ($line.Length -lt 10 -or $line[0] -ne 'S') { throw "Invalid S-record at line $lineNumber" }
        $type = $line[1]
        if ($type -notin @('0','1','2','3','5','6','7','8','9')) { throw "Unsupported S-record type S$type at line $lineNumber" }
        if ((($line.Length - 2) % 2) -ne 0 -or $line.Substring(2) -notmatch '^[0-9A-Fa-f]+$') {
            throw "Malformed hexadecimal S-record at line $lineNumber"
        }
        $record = New-Object byte[] (($line.Length - 2) / 2)
        for ($i = 0; $i -lt $record.Length; $i++) {
            $record[$i] = [Convert]::ToByte($line.Substring(2 + (2 * $i), 2), 16)
        }
        if ($record[0] -ne ($record.Length - 1)) { throw "S-record count mismatch at line $lineNumber" }
        $sum = 0
        foreach ($byte in $record) { $sum = ($sum + $byte) -band 0xFF }
        if ($sum -ne 0xFF) { throw "S-record checksum mismatch at line $lineNumber" }

        $addressBytes = switch ($type) {
            { $_ -in @('0','1','5','9') } { 2; break }
            { $_ -in @('2','6','8') } { 3; break }
            { $_ -in @('3','7') } { 4; break }
        }
        $address = [int64]0
        for ($i = 0; $i -lt $addressBytes; $i++) { $address = ($address -shl 8) -bor $record[1 + $i] }
        $dataLength = $record[0] - $addressBytes - 1

        if ($type -in @('1','2','3')) {
            if ($type -ne '1') { throw "Migration RAM images must use 16-bit S1 data records; found S$type at line $lineNumber" }
            for ($i = 0; $i -lt $dataLength; $i++) {
                $target = [int]($address + $i)
                if ($memory.ContainsKey($target)) { throw ('Overlapping S19 byte at ${0:X4}' -f $target) }
                $memory.Add($target, $record[1 + $addressBytes + $i])
            }
        } elseif ($type -in @('7','8','9')) {
            if ($type -ne '9') { throw "Migration RAM images must use an S9 entry record; found S$type at line $lineNumber" }
            if ($dataLength -ne 0) { throw "S9 record carries unexpected data at line $lineNumber" }
            if ($entry -ge 0) { throw 'S19 image contains more than one entry record' }
            $entry = [int]$address
        }
    }

    if ($memory.Count -eq 0) { throw 'S19 image contains no data' }
    if ($entry -lt 0) { throw 'S19 image has no S9 entry record' }
    $keys = @($memory.Keys)
    $first = [int]$keys[0]
    $last = [int]$keys[$keys.Count - 1]
    if ($first -lt 0x2000 -or $last -gt 0x7AFF) {
        throw ('Migration RAM image ${0:X4}-${1:X4} is outside the approved $2000-$7AFF window' -f $first, $last)
    }
    if ($entry -lt $first -or $entry -gt $last) {
        throw ('S9 entry ${0:X4} is outside loaded bytes ${1:X4}-${2:X4}' -f $entry, $first, $last)
    }
    $length = $last - $first + 1
    if ($memory.Count -ne $length) { throw 'Migration RAM image is sparse; a single dense range is required' }
    $image = New-Object byte[] $length
    for ($i = 0; $i -lt $length; $i++) { $image[$i] = $memory[$first + $i] }

    return [pscustomobject]@{
        Path = (Resolve-Path -LiteralPath $Path).Path
        First = $first
        Last = $last
        Entry = $entry
        Bytes = $image
        Fnv1a = Get-Fnv1a32 -Bytes $image
        Sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    }
}

function Read-SerialExact {
    param(
        [Parameter(Mandatory = $true)]$Serial,
        [Parameter(Mandatory = $true)][int]$Count,
        [Parameter(Mandatory = $true)][string]$Purpose
    )
    $result = New-Object byte[] $Count
    $offset = 0
    try {
        while ($offset -lt $Count) { $offset += $Serial.Read($result, $offset, $Count - $offset) }
    } catch [System.TimeoutException] {
        throw ("WDCMONv2 timeout during {0}: received {1}/{2} bytes" -f $Purpose, $offset, $Count)
    }
    return $result
}

function Write-SerialBytes {
    param(
        [Parameter(Mandatory = $true)]$Serial,
        [Parameter(Mandatory = $true)][byte[]]$Bytes
    )
    $Serial.Write($Bytes, 0, $Bytes.Length)
}

function Start-WdcCommand {
    param(
        [Parameter(Mandatory = $true)]$Serial,
        [Parameter(Mandatory = $true)][byte]$Command
    )
    Write-SerialBytes -Serial $Serial -Bytes (Convert-ToByteArray @($script:WdcSync0, $script:WdcSync1))
    $ready = Read-SerialExact -Serial $Serial -Count 1 -Purpose ('sync for command ${0:X2}' -f $Command)
    if ($ready[0] -ne $script:WdcReady) {
        throw ('WDCMONv2 sync failed for command ${0:X2}: expected CC, received {1:X2}' -f $Command, $ready[0])
    }
    Write-SerialBytes -Serial $Serial -Bytes (Convert-ToByteArray @($Command))
}

function Get-WdcBoardInfo {
    param([Parameter(Mandatory = $true)]$Serial)
    Start-WdcCommand -Serial $Serial -Command $script:WdcBoardInfo
    $reply = Read-SerialExact -Serial $Serial -Count 12 -Purpose 'board-info reply'
    $tag = [System.Text.Encoding]::ASCII.GetString($reply, 0, 4)
    if ($tag -ne 'SXB2') {
        throw ('Unsupported WDCMONv2 board identity {0}; expected SXB2' -f ([BitConverter]::ToString($reply)))
    }
    $hardware = [BitConverter]::ToUInt32($reply, 4)
    $software = [BitConverter]::ToUInt32($reply, 8)
    return [pscustomobject]@{ Tag = $tag; Hardware = $hardware; Software = $software; Raw = $reply }
}

function Get-WdcBoardInfoAfterResetArm {
    param(
        [Parameter(Mandatory = $true)]$Serial,
        [Parameter(Mandatory = $true)][int]$Seconds
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    $oldTimeout = $Serial.ReadTimeout
    $Serial.ReadTimeout = 100
    try {
        $Serial.DiscardInBuffer()
        while ([DateTime]::UtcNow -lt $deadline) {
            Write-SerialBytes -Serial $Serial -Bytes (Convert-ToByteArray @($script:WdcSync0, $script:WdcSync1))
            try {
                $value = $Serial.ReadByte()
                if ($value -eq $script:WdcReady) {
                    # Sync pairs can accumulate in the USB transmit queue while
                    # the board is held in reset.  Let WDCMON consume them and
                    # discard only their $CC acknowledgements before BOARD_INFO.
                    Start-Sleep -Milliseconds 100
                    $Serial.DiscardInBuffer()
                    Write-SerialBytes -Serial $Serial -Bytes (Convert-ToByteArray @($script:WdcBoardInfo))
                    $Serial.ReadTimeout = [Math]::Max($oldTimeout, 5000)
                    $reply = Read-SerialExact -Serial $Serial -Count 12 -Purpose 'armed board-info reply'
                    $tag = [System.Text.Encoding]::ASCII.GetString($reply, 0, 4)
                    if ($tag -ne 'SXB2') {
                        throw ('Unsupported WDCMONv2 board identity {0}; expected SXB2' -f ([BitConverter]::ToString($reply)))
                    }
                    return [pscustomobject]@{
                        Tag = $tag
                        Hardware = [BitConverter]::ToUInt32($reply, 4)
                        Software = [BitConverter]::ToUInt32($reply, 8)
                        Raw = $reply
                    }
                }
                while ($Serial.BytesToRead -gt 0) {
                    if ($Serial.ReadByte() -eq $script:WdcReady) {
                        Start-Sleep -Milliseconds 100
                        $Serial.DiscardInBuffer()
                        Write-SerialBytes -Serial $Serial -Bytes (Convert-ToByteArray @($script:WdcBoardInfo))
                        $Serial.ReadTimeout = [Math]::Max($oldTimeout, 5000)
                        $reply = Read-SerialExact -Serial $Serial -Count 12 -Purpose 'armed board-info reply'
                        $tag = [System.Text.Encoding]::ASCII.GetString($reply, 0, 4)
                        if ($tag -ne 'SXB2') {
                            throw ('Unsupported WDCMONv2 board identity {0}; expected SXB2' -f ([BitConverter]::ToString($reply)))
                        }
                        return [pscustomobject]@{
                            Tag = $tag
                            Hardware = [BitConverter]::ToUInt32($reply, 4)
                            Software = [BitConverter]::ToUInt32($reply, 8)
                            Raw = $reply
                        }
                    }
                }
            } catch [System.TimeoutException] {
            }
        }
    } finally {
        $Serial.ReadTimeout = $oldTimeout
    }
    throw "WDCMONv2 armed reset sync timed out after $Seconds seconds"
}

function Write-WdcMemory {
    param(
        [Parameter(Mandatory = $true)]$Serial,
        [Parameter(Mandatory = $true)][int]$Address,
        [Parameter(Mandatory = $true)][byte[]]$Bytes
    )
    Start-WdcCommand -Serial $Serial -Command $script:WdcWriteMemory
    Write-SerialBytes -Serial $Serial -Bytes (Convert-ToU24LE $Address)
    Write-SerialBytes -Serial $Serial -Bytes (Convert-ToU24LE $Bytes.Length)
    Write-SerialBytes -Serial $Serial -Bytes $Bytes
    $reply = Read-SerialExact -Serial $Serial -Count 1 -Purpose ('write acknowledgement at ${0:X4}' -f $Address)
    if ($reply[0] -ne 0) { throw ('WDCMONv2 rejected RAM write at ${0:X4}: status ${1:X2}' -f $Address, $reply[0]) }
}

function Read-WdcMemory {
    param(
        [Parameter(Mandatory = $true)]$Serial,
        [Parameter(Mandatory = $true)][int]$Address,
        [Parameter(Mandatory = $true)][int]$Count
    )
    Start-WdcCommand -Serial $Serial -Command $script:WdcReadMemory
    Write-SerialBytes -Serial $Serial -Bytes (Convert-ToU24LE $Address)
    Write-SerialBytes -Serial $Serial -Bytes (Convert-ToU24LE $Count)
    return (Read-SerialExact -Serial $Serial -Count $Count -Purpose ('RAM readback at ${0:X4}' -f $Address))
}

function Start-WdcMemory {
    param(
        [Parameter(Mandatory = $true)]$Serial,
        [Parameter(Mandatory = $true)][int]$Address
    )
    Start-WdcCommand -Serial $Serial -Command $script:WdcExecuteMemory
    Write-SerialBytes -Serial $Serial -Bytes (Convert-ToU24LE $Address)
}

function Start-RawTerminal {
    param(
        [Parameter(Mandatory = $true)][System.IO.Ports.SerialPort]$Serial,
        [System.IO.Stream]$Log,
        [byte[]]$TransferBytes,
        [string]$TransferName,
        [string]$TransferSha256,
        [byte[]]$Transfer2Bytes,
        [string]$Transfer2Name,
        [string]$Transfer2Sha256
    )
    $stdout = [Console]::OpenStandardOutput()
    $oldControlC = [Console]::TreatControlCAsInput
    [Console]::TreatControlCAsInput = $true
    $txLine = [System.Text.StringBuilder]::new()
    Write-SessionEvent 'TERMINAL START'
    if ($null -ne $Transfer2Bytes) {
        Write-Host ("TERMINAL ACTIVE; CTRL+] EXITS; CTRL+B PROBES WDCMON; CTRL+U SENDS {0}; CTRL+D SENDS {1}; ENTER SENDS CR" -f $TransferName, $Transfer2Name)
    } elseif ($null -ne $TransferBytes) {
        Write-Host ("TERMINAL ACTIVE; CTRL+] EXITS; CTRL+B PROBES WDCMON; CTRL+U SENDS {0}; ENTER SENDS CR" -f $TransferName)
    } else {
        Write-Host 'TERMINAL ACTIVE; CTRL+] EXITS; CTRL+B PROBES WDCMON; ENTER SENDS CR'
    }
    try {
        $buffer = New-Object byte[] 4096
        while ($true) {
            $available = $Serial.BytesToRead
            if ($available -gt 0) {
                $count = $Serial.Read($buffer, 0, [Math]::Min($available, $buffer.Length))
                if ($count -gt 0) {
                    $stdout.Write($buffer, 0, $count)
                    $stdout.Flush()
                    if ($null -ne $Log) { $Log.Write($buffer, 0, $count); $Log.Flush() }
                }
            }
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true)
                $value = [int]$key.KeyChar
                if ($value -eq 0x1D) {
                    Write-SessionEvent 'CTRL+] TERMINAL EXIT'
                    break
                }
                if ($value -eq 0x02) {
                    try {
                        $probe = Get-WdcBoardInfo -Serial $Serial
                        if ($null -ne $Log) { $Log.Write($probe.Raw, 0, $probe.Raw.Length); $Log.Flush() }
                        Write-SessionEvent ("CTRL+B WDCMON PROBE PASS TAG={0} HW={1:N2} WDCMON={2:N2}" -f $probe.Tag, ($probe.Hardware / 100.0), ($probe.Software / 100.0))
                        Write-Host ("`nWDCMON PROBE = {0}; HW={1:N2}; WDCMON={2:N2}" -f $probe.Tag, ($probe.Hardware / 100.0), ($probe.Software / 100.0))
                    } catch {
                        Write-SessionEvent ("CTRL+B WDCMON PROBE FAIL {0}" -f $_.Exception.Message)
                        Write-Warning ("WDCMON probe failed: {0}" -f $_.Exception.Message)
                    }
                    continue
                }
                if ($value -eq 0x15 -and $null -ne $TransferBytes) {
                    Write-SessionEvent ("CTRL+U FILE SEND NAME={0} BYTES={1} SHA256={2}" -f $TransferName, $TransferBytes.Length, $TransferSha256)
                    Write-Host ("`nSENDING {0} ({1} bytes)" -f $TransferName, $TransferBytes.Length)
                    for ($offset = 0; $offset -lt $TransferBytes.Length; $offset += 64) {
                        $count = [Math]::Min(64, $TransferBytes.Length - $offset)
                        $Serial.Write($TransferBytes, $offset, $count)
                        Start-Sleep -Milliseconds 2
                    }
                    Write-Host 'FILE SENT'
                    continue
                }
                if ($value -eq 0x04 -and $null -ne $Transfer2Bytes) {
                    Write-SessionEvent ("CTRL+D FILE SEND NAME={0} BYTES={1} SHA256={2}" -f $Transfer2Name, $Transfer2Bytes.Length, $Transfer2Sha256)
                    Write-Host ("`nSENDING {0} ({1} bytes)" -f $Transfer2Name, $Transfer2Bytes.Length)
                    for ($offset = 0; $offset -lt $Transfer2Bytes.Length; $offset += 64) {
                        $count = [Math]::Min(64, $Transfer2Bytes.Length - $offset)
                        $Serial.Write($Transfer2Bytes, $offset, $count)
                        Start-Sleep -Milliseconds 2
                    }
                    Write-Host 'FILE SENT'
                    continue
                }
                if ($key.Key -eq [ConsoleKey]::Enter) {
                    Write-SessionEvent ("TX LINE {0}" -f $txLine.ToString())
                    $null = $txLine.Clear()
                    $value = 0x0D
                } elseif ($value -eq 0x08 -or $value -eq 0x7F) {
                    if ($txLine.Length -gt 0) { $null = $txLine.Remove($txLine.Length - 1, 1) }
                } elseif ($value -ge 0x20 -and $value -le 0x7E) {
                    $null = $txLine.Append([char]$value)
                } elseif ($value -ge 0 -and $value -le 0xFF) {
                    Write-SessionEvent ('TX BYTE ${0:X2}' -f $value)
                }
                if ($value -ge 0 -and $value -le 0xFF) {
                    Write-SerialBytes -Serial $Serial -Bytes (Convert-ToByteArray @($value))
                }
            }
            if ($available -eq 0) { Start-Sleep -Milliseconds 10 }
        }
    } finally {
        Write-SessionEvent 'TERMINAL STOP'
        [Console]::TreatControlCAsInput = $oldControlC
    }
}

function Receive-SerialWindow {
    param(
        [Parameter(Mandatory = $true)][System.IO.Ports.SerialPort]$Serial,
        [Parameter(Mandatory = $true)][int]$Seconds,
        [System.IO.Stream]$Log
    )
    $stdout = [Console]::OpenStandardOutput()
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    $total = 0
    $buffer = New-Object byte[] 4096
    while ([DateTime]::UtcNow -lt $deadline) {
        $available = $Serial.BytesToRead
        if ($available -gt 0) {
            $count = $Serial.Read($buffer, 0, [Math]::Min($available, $buffer.Length))
            if ($count -gt 0) {
                $total += $count
                $stdout.Write($buffer, 0, $count)
                $stdout.Flush()
                if ($null -ne $Log) { $Log.Write($buffer, 0, $count); $Log.Flush() }
            }
        } else {
            Start-Sleep -Milliseconds 10
        }
    }
    Write-Host ("`nLISTEN ONLY = COMPLETE; RX={0} BYTES; TX=0 BYTES" -f $total)
}

if ($ListPorts) {
    [System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object
    return
}

if ($SelfTest) {
    $u24 = Convert-ToU24LE 0x123456
    if ([BitConverter]::ToString($u24) -ne '56-34-12') { throw 'u24 little-endian codec self-test failed' }
    $fixture = Convert-ToByteArray @(0x68,0x65,0x6C,0x6C,0x6F)
    if ((Get-Fnv1a32 -Bytes $fixture) -ne [uint32]0x4F9F2CAB) { throw 'FNV-1a self-test failed' }
    $mock = [Wdcmonv2ProtocolMock]::new()
    $board = Get-WdcBoardInfo -Serial $mock
    if ($board.Tag -ne 'SXB2' -or $board.Hardware -ne 123 -or $board.Software -ne 200) { throw 'Board-info protocol self-test failed' }
    $writeFixture = Convert-ToByteArray @(0x11,0x22,0x33,0x44)
    Write-WdcMemory -Serial $mock -Address 0x2000 -Bytes $writeFixture
    $readFixture = Read-WdcMemory -Serial $mock -Address 0x2000 -Count $writeFixture.Length
    if ([BitConverter]::ToString($readFixture) -ne '11-22-33-44') { throw 'RAM write/read protocol self-test failed' }
    Start-WdcMemory -Serial $mock -Address 0x2345
    if ($mock.ExecutedAddress -ne 0x2345) { throw 'Execute-address protocol self-test failed' }
    if ([BitConverter]::ToString($mock.Commands.ToArray()) -ne '0C-02-03-06') { throw 'WDCMONv2 command-order self-test failed' }
    $expectedWire = Convert-ToByteArray @(
        0x55,0xAA,0x0C,
        0x55,0xAA,0x02,0x00,0x20,0x00,0x04,0x00,0x00,0x11,0x22,0x33,0x44,
        0x55,0xAA,0x03,0x00,0x20,0x00,0x04,0x00,0x00,
        0x55,0xAA,0x06,0x45,0x23,0x00
    )
    if ([BitConverter]::ToString($mock.Sent.ToArray()) -ne [BitConverter]::ToString($expectedWire)) {
        throw 'WDCMONv2 wire-framing self-test failed'
    }
    if ($mock.Receive.Count -ne 0 -or $mock.State -ne 'SYNC') { throw 'WDCMONv2 protocol self-test left unread or partial state' }
    $eventMemory = [System.IO.MemoryStream]::new()
    $eventEncoding = [System.Text.UTF8Encoding]::new($false)
    $eventWriter = [System.IO.StreamWriter]::new($eventMemory, $eventEncoding, 1024, $true)
    $script:EventWriter = $eventWriter
    try {
        Write-SessionEvent 'SELFTEST EVENT'
    } finally {
        $eventWriter.Dispose()
        $script:EventWriter = $null
    }
    $eventText = $eventEncoding.GetString($eventMemory.ToArray())
    $eventMemory.Dispose()
    if ($eventText -notmatch 'SELFTEST EVENT') { throw 'Session event-log self-test failed' }
    Write-Host 'WDCMONV2 HOST BRIDGE SELF-TEST = PASS'
    Write-Host 'PROTOCOL EMULATOR = PASS; $0C/$02/$03/$06 EXACT WIRE FRAMES'
    Write-Host 'SESSION EVENT LOG SELF-TEST = PASS'
    if (-not $ImagePath) { return }
}

$image = $null
if ($ImagePath) {
    $image = Read-MigrationS19 -Path $ImagePath
    Write-Host ('S19 SHA256 = {0}' -f $image.Sha256)
    Write-Host ('RAM RANGE  = ${0:X4}-${1:X4} ({2} bytes)' -f $image.First, $image.Last, $image.Bytes.Length)
    Write-Host ('ENTRY      = ${0:X4}' -f $image.Entry)
    Write-Host ('RAM FNV1A  = {0:X8}' -f $image.Fnv1a)
} elseif (-not $ProbeOnly -and $ListenOnlySeconds -eq 0 -and -not $TerminalOnly) {
    throw 'Specify -ImagePath, or use -ListPorts/-ProbeOnly/-ListenOnlySeconds/-SelfTest'
}
if ($ValidateOnly) {
    if ($null -eq $image) { throw '-ValidateOnly requires -ImagePath' }
    Write-Host 'MIGRATION S19 = VALID'
    return
}

if (-not $Port) { throw 'Specify the stock-board COM port with -Port (use -ListPorts to enumerate)' }
if ($ChunkBytes -lt 16 -or $ChunkBytes -gt 4096) { throw '-ChunkBytes must be in the range 16..4096' }
if ($ListenOnlySeconds -lt 0 -or $ListenOnlySeconds -gt 60) { throw '-ListenOnlySeconds must be in the range 0..60' }
if ($PhysicalResetArmSeconds -lt 0 -or $PhysicalResetArmSeconds -gt 120) { throw '-PhysicalResetArmSeconds must be in the range 0..120' }
if ($ProbeOnly -and $ListenOnlySeconds -gt 0) { throw '-ProbeOnly and -ListenOnlySeconds are mutually exclusive' }
if ($null -ne $image -and ($ProbeOnly -or $ListenOnlySeconds -gt 0)) { throw '-ImagePath cannot be combined with -ProbeOnly or -ListenOnlySeconds' }
if ($TerminalOnly -and $null -ne $image) { throw '-TerminalOnly cannot be combined with -ImagePath' }
if ($TerminalOnly -and ($ProbeOnly -or $ListenOnlySeconds -gt 0 -or $PhysicalResetGate -or $PhysicalResetArmSeconds -gt 0)) { throw '-TerminalOnly cannot be combined with a probe, listener, or physical-reset mode' }
if ($TerminalOnly -and -not $NoReset) { throw '-TerminalOnly requires -NoReset' }
if ($TerminalOnly -and $NoTerminal) { throw '-TerminalOnly cannot be combined with -NoTerminal' }
if ($PhysicalResetGate -and -not $NoReset) { throw '-PhysicalResetGate requires -NoReset' }
if ($PhysicalResetArmSeconds -gt 0 -and -not $NoReset) { throw '-PhysicalResetArmSeconds requires -NoReset' }
if ($PhysicalResetGate -and $PhysicalResetArmSeconds -gt 0) { throw '-PhysicalResetGate and -PhysicalResetArmSeconds are mutually exclusive' }
if (-not $ProbeOnly -and $ListenOnlySeconds -eq 0 -and -not $NoTerminal) {
    if ([Console]::IsInputRedirected) { throw 'Interactive terminal input is redirected; use a real console or make -NoTerminal explicit' }
    try { $null = [Console]::KeyAvailable } catch { throw ('Interactive console is unavailable: {0}' -f $_.Exception.Message) }
}
$transcriptFull = $null
if (-not $ProbeOnly -and $TranscriptPath -and ($ListenOnlySeconds -gt 0 -or -not $NoTerminal)) {
    $transcriptFull = Get-HostFullPath -Path $TranscriptPath
    if ((Test-Path -LiteralPath $transcriptFull) -and -not $Force) {
        throw "Transcript exists; use -Force to replace it: $transcriptFull"
    }
    $transcriptParent = Split-Path -Parent $transcriptFull
    if ($transcriptParent -and -not (Test-Path -LiteralPath $transcriptParent)) {
        New-Item -ItemType Directory -Force -Path $transcriptParent | Out-Null
    }
}
$eventFull = $null
if ($EventLogPath) {
    $eventFull = Get-HostFullPath -Path $EventLogPath
} elseif ($null -ne $transcriptFull) {
    $eventFull = $transcriptFull + '.events.txt'
}
if ($null -ne $transcriptFull -and $null -ne $eventFull -and
    [string]::Equals($transcriptFull, $eventFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw '-TranscriptPath and -EventLogPath must name different files'
}
if ($null -ne $eventFull) {
    if ((Test-Path -LiteralPath $eventFull) -and -not $Force) {
        throw "Session event log exists; use -Force to replace it: $eventFull"
    }
    $eventParent = Split-Path -Parent $eventFull
    if ($eventParent -and -not (Test-Path -LiteralPath $eventParent)) {
        New-Item -ItemType Directory -Force -Path $eventParent | Out-Null
    }
}
$transferBytes = $null
$transferName = $null
$transferSha256 = $null
if (-not $ProbeOnly -and $ListenOnlySeconds -eq 0 -and -not $NoTerminal -and $TransferPath) {
    if (-not (Test-Path -LiteralPath $TransferPath -PathType Leaf)) { throw "Transfer file not found: $TransferPath" }
    $transferFull = (Resolve-Path -LiteralPath $TransferPath).Path
    $transferBytes = [System.IO.File]::ReadAllBytes($transferFull)
    $transferName = Split-Path -Leaf $transferFull
    $transferSha256 = Get-ByteSha256 -Bytes $transferBytes
}
$transfer2Bytes = $null
$transfer2Name = $null
$transfer2Sha256 = $null
if (-not $ProbeOnly -and $ListenOnlySeconds -eq 0 -and -not $NoTerminal -and $Transfer2Path) {
    if (-not (Test-Path -LiteralPath $Transfer2Path -PathType Leaf)) { throw "Second transfer file not found: $Transfer2Path" }
    $transfer2Full = (Resolve-Path -LiteralPath $Transfer2Path).Path
    $transfer2Bytes = [System.IO.File]::ReadAllBytes($transfer2Full)
    $transfer2Name = Split-Path -Leaf $transfer2Full
    $transfer2Sha256 = Get-ByteSha256 -Bytes $transfer2Bytes
}

$serial = [System.IO.Ports.SerialPort]::new($Port, $BaudRate, [System.IO.Ports.Parity]::None, 8, [System.IO.Ports.StopBits]::One)
$serial.Handshake = [System.IO.Ports.Handshake]::RequestToSend
$serial.ReadTimeout = 1000
$serial.WriteTimeout = 5000
$serial.DtrEnable = $false
$sessionOutcome = 'INCOMPLETE'
$eventStream = $null
$rawLog = $null
try {
    if ($null -ne $eventFull) {
        $eventEncoding = [System.Text.UTF8Encoding]::new($false)
        $eventMode = [System.IO.FileMode]::CreateNew
        if ($Force) { $eventMode = [System.IO.FileMode]::Create }
        $eventStream = [System.IO.File]::Open($eventFull, $eventMode, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
        $script:EventWriter = [System.IO.StreamWriter]::new($eventStream, $eventEncoding)
        Write-Host "SESSION EVENT LOG = $eventFull"
        Write-SessionEvent ("SESSION START PORT={0} BAUD={1} RESET={2}" -f $Port, $BaudRate, (-not $NoReset))
        if ($null -ne $image) {
            Write-SessionEvent ("IMAGE SHA256={0} RANGE=${1:X4}-${2:X4} BYTES={3} ENTRY=${4:X4} FNV1A={5:X8}" -f $image.Sha256, $image.First, $image.Last, $image.Bytes.Length, $image.Entry, $image.Fnv1a)
        }
        if ($null -ne $transferBytes) {
            Write-SessionEvent ("TRANSFER READY NAME={0} BYTES={1} SHA256={2}" -f $transferName, $transferBytes.Length, $transferSha256)
        }
        if ($null -ne $transfer2Bytes) {
            Write-SessionEvent ("TRANSFER2 READY NAME={0} BYTES={1} SHA256={2}" -f $transfer2Name, $transfer2Bytes.Length, $transfer2Sha256)
        }
    }
    if ($null -ne $transcriptFull) {
        $rawMode = [System.IO.FileMode]::CreateNew
        if ($Force) { $rawMode = [System.IO.FileMode]::Create }
        $rawLog = [System.IO.File]::Open($transcriptFull, $rawMode, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
        Write-Host "RAW RX TRANSCRIPT = $transcriptFull"
        Write-SessionEvent ("RAW RX LOG READY PATH={0}" -f $transcriptFull)
    }
    $serial.Open()
    $serial.DiscardInBuffer()
    $serial.DiscardOutBuffer()
    if ($TerminalOnly) {
        Start-RawTerminal -Serial $serial -Log $rawLog -TransferBytes $transferBytes -TransferName $transferName -TransferSha256 $transferSha256 -Transfer2Bytes $transfer2Bytes -Transfer2Name $transfer2Name -Transfer2Sha256 $transfer2Sha256
        $sessionOutcome = 'TERMINAL-ONLY SESSION COMPLETE'
        return
    }
    if (-not $NoReset) {
        $serial.DtrEnable = $false
        Start-Sleep -Milliseconds 300
        $serial.DtrEnable = $true
        Start-Sleep -Milliseconds 300
        $serial.DtrEnable = $false
        Start-Sleep -Milliseconds 1000
        $startupByteCount = $serial.BytesToRead
        $serial.DiscardInBuffer()
        Write-SessionEvent ("RESET SETTLE=1000ms STARTUP_RX_DISCARDED={0}" -f $startupByteCount)
        Write-Host ("RESET SETTLE = 1000 ms; STARTUP RX DISCARDED = {0}" -f $startupByteCount)
    }
    if ($PhysicalResetGate) {
        Write-Host 'PHYSICAL RESET GATE: reset the board, wait two seconds, then press ENTER here'
        $null = Read-Host
        $startupByteCount = $serial.BytesToRead
        $serial.DiscardInBuffer()
        Write-SessionEvent ("PHYSICAL RESET GATE STARTUP_RX_DISCARDED={0}" -f $startupByteCount)
        Write-Host ("PHYSICAL RESET GATE = RELEASED; STARTUP RX DISCARDED = {0}" -f $startupByteCount)
    }

    if ($ListenOnlySeconds -gt 0) {
        Receive-SerialWindow -Serial $serial -Seconds $ListenOnlySeconds -Log $rawLog
        $sessionOutcome = 'LISTEN WINDOW COMPLETE'
        return
    }

    if ($PhysicalResetArmSeconds -gt 0) {
        Write-Host ("PHYSICAL RESET ARM = ACTIVE FOR {0} SECONDS; PRESS PHYSICAL RESET NOW" -f $PhysicalResetArmSeconds)
        Write-SessionEvent ("PHYSICAL RESET ARM START SECONDS={0}" -f $PhysicalResetArmSeconds)
        $board = Get-WdcBoardInfoAfterResetArm -Serial $serial -Seconds $PhysicalResetArmSeconds
        Write-SessionEvent 'PHYSICAL RESET ARM SYNC=PASS'
    } else {
        $board = Get-WdcBoardInfo -Serial $serial
    }
    Write-SessionEvent ('BOARD TAG={0} HW={1:N2} WDCMON={2:N2}' -f $board.Tag, ($board.Hardware / 100.0), ($board.Software / 100.0))
    Write-Host ('BOARD      = {0}; HW={1:N2}; WDCMON={2:N2}' -f $board.Tag, ($board.Hardware / 100.0), ($board.Software / 100.0))
    if ($ProbeOnly) {
        $sessionOutcome = 'PROBE PASS; NO RAM OR FLASH COMMAND ISSUED'
        Write-Host 'WDCMONV2 PROBE = PASS; NO RAM OR FLASH COMMAND ISSUED'
        return
    }

    for ($offset = 0; $offset -lt $image.Bytes.Length; $offset += $ChunkBytes) {
        $count = [Math]::Min($ChunkBytes, $image.Bytes.Length - $offset)
        $chunk = New-Object byte[] $count
        [Array]::Copy($image.Bytes, $offset, $chunk, 0, $count)
        $address = $image.First + $offset
        Write-WdcMemory -Serial $serial -Address $address -Bytes $chunk
        $readback = Read-WdcMemory -Serial $serial -Address $address -Count $count
        for ($i = 0; $i -lt $count; $i++) {
            if ($readback[$i] -ne $chunk[$i]) {
                throw ('RAM readback mismatch at ${0:X4}: wrote ${1:X2}, read ${2:X2}' -f ($address + $i), $chunk[$i], $readback[$i])
            }
        }
        Write-Host -NoNewline '.'
    }
    Write-SessionEvent 'RAM READBACK BYTE-EXACT'
    Write-Host "`nRAM READBACK = BYTE-EXACT"
    Write-Host ('EXECUTE      = ${0:X4}' -f $image.Entry)
    Write-SessionEvent ('EXECUTE ${0:X4}' -f $image.Entry)
    Start-WdcMemory -Serial $serial -Address $image.Entry

    if ($NoTerminal) {
        $sessionOutcome = 'RAM APPLICATION STARTED; PORT CLOSED BY REQUEST'
        Write-Warning 'RAM application is running, but this process will close the port. Reopening a terminal may toggle DTR and reset the board.'
    } else {
        Start-RawTerminal -Serial $serial -Log $rawLog -TransferBytes $transferBytes -TransferName $transferName -TransferSha256 $transferSha256 -Transfer2Bytes $transfer2Bytes -Transfer2Name $transfer2Name -Transfer2Sha256 $transfer2Sha256
        $sessionOutcome = 'TERMINAL CLOSED BY OPERATOR'
    }
} catch {
    Write-SessionEvent ("ERROR {0}" -f $_.Exception.Message)
    throw
} finally {
    Write-SessionEvent ("SESSION END OUTCOME={0}" -f $sessionOutcome)
    if ($serial.IsOpen) { $serial.Close() }
    $serial.Dispose()
    if ($null -ne $rawLog) { $rawLog.Dispose() }
    if ($null -ne $script:EventWriter) {
        $script:EventWriter.Dispose()
        $script:EventWriter = $null
    }
    if ($null -ne $eventStream) { $eventStream.Dispose() }
}
