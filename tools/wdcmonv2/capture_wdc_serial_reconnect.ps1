param(
    [Parameter(Mandatory = $true)]
    [string]$Port,
    [int]$BaudRate = 115200,
    [int]$Seconds = 90,
    [string]$RawPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Seconds -lt 1 -or $Seconds -gt 600) {
    throw '-Seconds must be in the range 1..600'
}

$raw = $null
$serial = $null
$deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
$buffer = New-Object byte[] 4096
$received = 0

try {
    if ($RawPath) {
        $resolvedRawPath = [System.IO.Path]::GetFullPath($RawPath)
        $rawDirectory = [System.IO.Path]::GetDirectoryName($resolvedRawPath)
        if ($rawDirectory -and -not [System.IO.Directory]::Exists($rawDirectory)) {
            [System.IO.Directory]::CreateDirectory($rawDirectory) | Out-Null
        }
        $raw = [System.IO.File]::Open(
            $resolvedRawPath,
            [System.IO.FileMode]::Create,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::Read
        )
    }

    Write-Host ('RECONNECT LISTENER ARMED ON {0} FOR {1} SECONDS; TX=0 DTR=0 RTS=0' -f $Port, $Seconds)

    while ([DateTime]::UtcNow -lt $deadline) {
        if ($null -eq $serial -or -not $serial.IsOpen) {
            try {
                $serial = [System.IO.Ports.SerialPort]::new($Port, $BaudRate, 'None', 8, 'One')
                $serial.Handshake = 'None'
                $serial.DtrEnable = $false
                $serial.RtsEnable = $false
                $serial.ReadTimeout = 100
                $serial.WriteTimeout = 100
                $serial.Open()
                Write-Host ('[{0} connected]' -f $Port)
            } catch {
                if ($null -ne $serial) {
                    try { $serial.Dispose() } catch {}
                    $serial = $null
                }
                Start-Sleep -Milliseconds 100
                continue
            }
        }

        try {
            $available = $serial.BytesToRead
            if ($available -eq 0) {
                Start-Sleep -Milliseconds 20
                continue
            }

            $count = $serial.Read($buffer, 0, [Math]::Min($available, $buffer.Length))
            if ($count -le 0) { continue }
            $received += $count
            if ($null -ne $raw) {
                $raw.Write($buffer, 0, $count)
                $raw.Flush()
            }
            [Console]::Write([System.Text.Encoding]::ASCII.GetString($buffer, 0, $count))
        } catch {
            Write-Host ''
            Write-Host ('[{0} disconnected; waiting to reconnect]' -f $Port)
            try { $serial.Dispose() } catch {}
            $serial = $null
        }
    }
} finally {
    if ($null -ne $serial) {
        try { $serial.Close() } catch {}
        $serial.Dispose()
    }
    if ($null -ne $raw) {
        $raw.Dispose()
    }
}

Write-Host ''
Write-Host ('RECONNECT LISTENER COMPLETE; RX={0} BYTES' -f $received)
if ($RawPath) {
    Write-Host ('RAW={0}' -f [System.IO.Path]::GetFullPath($RawPath))
}
