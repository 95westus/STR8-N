# STR8-N direct ACIA RAM test

This 165-byte RAM program bypasses STR8-N console selection and accesses the
W65C51N directly. It does not write flash.

Build it with `make v2`. The loadable file is:

`BUILD/v2-alpha18/str8n-v2-alpha18-acia-test-2000.s19`

On the primary FT245 terminal:

1. Enter STR8-N alpha18 and confirm a `Bn>` prompt.
2. Enter `L` and send the ACIA-test S19 file.
3. Confirm `Entry 2000`.
4. Open the ACIA adapter terminal at 19200 baud, 8 data bits, no parity, one
   stop bit, and no software flow control.
5. Enter `G 2000` on the FT245 terminal.

The FT245 terminal reports `ACIA RX MONITOR; SEND Q`. The ACIA terminal should
receive this about once per second:

```text
ACIA 19200 8N1 - TYPE; Q EXITS
```

Characters typed on the ACIA terminal are echoed. Every received byte is also
reported on FT245 as `ACIA RX $xx`. `Q` or `q` prints `ACIA EXIT` and returns
through STR8-N HOLD. If FT245 remains configured, the STR8-N banner and prompt
then appear on the FT245 terminal. If ACIA output works but FT245 reports no
received bytes, check adapter TX to board RX, common ground, and terminal
transmit/flow-control settings.

Use a 5 V-compatible USB-to-TTL UART adapter. Cross board TX to adapter RX and
board RX to adapter TX, connect ground, and hold the ACIA CTS input low. Do not
use a true ±RS-232 adapter. The test initializes control `$1F`, command `$0B`,
checks RDRF for input, and uses a fixed transmit delay instead of TDRE.
