# rc1 ABI reference — source-audited addresses

This reference targets the generation-49 public include, not v2.1.
Validate the initialized `RA` descriptor at `$7E60`: format 1 and 13 calls.
Calls require IRQ disabled and decimal clear. On 65C816: E=1, D=0, DBR=0,
PBR=0 and direct page zero. Calls are non-reentrant. A ROM entry requires its
resident flash bank visible; the initialized RAM entries work with any flash
bank selected. Do not assume undocumented register preservation.

| Service | RAM entry | ROM entry |
| --- | --- | --- |
| RESET | `$7E64` | `$F004` |
| HOLD | `$7E67` | `$F007` |
| CON_INIT | `$7E6A` | `$F00A` |
| PUTC | `$7E6D` | `$F00D` |
| GETC | `$7E70` | `$F010` |
| RAW_POLL | `$7E73` | `$F013` |
| CHECK_CANCEL | `$7E76` | `$F016` |
| RX_RESET | `$7E79` | `$F019` |
| HEX_OUT | `$7E7C` | `$F01F` |
| NEWLINE | `$7E7F` | `$F022` |
| HEX_NIBBLE | `$7E82` | `$F025` |
| CAPS_QUERY | `$7E85` | `$F028` |
| BOARD_QUERY | `$7E88` | `$F02B` |

PUTC outputs the character in A; GETC returns a character in A. HOLD transfers
control back to the monitor. RESET is disruptive. CAPS_QUERY returns A=format,
X=flags, Y=descriptor length, carry set; the current values are 1, `$17`, 4.
BOARD_QUERY returns A=format, X=CPU, Y=board/console flags, carry set. CPU
identifiers are `$02` for 65C02 and `$16` for 65C816. Native-vector capability
does not advertise native monitor-service calls.

## Configuration and optional-service discovery

| Address | Contract |
| --- | --- |
| `$7D80`, 16 bytes | RAM copy of latest committed configuration |
| `$7D04`, 8 bytes | `SV`, format, flags, service pointer LE16, application-end LE16 |
| `$7D07` | Optional-service flags: bit 0 RTC, bit 1 I2C |
| `$7D0C` | `$FF` reserves `$6500–$66FF` until reset |
| `$7E00` onward | Emulation interrupt handler pointers |
| `$7E10` onward | Native interrupt pointers; native application qualification deferred |

Discover the application-end limit rather than relying on the historical
`$66FF` include constant. Service failure does not release a reset-latched
reservation. Configuration RAM is not a fixed persistent storage pocket.

## S/R/T extension

The versioned `SR` descriptor at B3:`$E800` identifies format 3, revision 1
and a 24-byte stored-record header. B3 must be visible for these entries:

| Entry | Address |
| --- | --- |
| CLI save / restore / table | `$E808` / `$E80B` / `$E80E` |
| API save / restore | `$E811` / `$E814` |

API input A/X is the low/high address of a 23-byte application-RAM request:
bank byte, flash address LE16, RAM start LE16, RAM end LE16, 16-byte label.
Success returns C=1,A=0; failure returns C=0,A=error (1 argument, 2 occupied,
3 flash failure, 4 invalid record). X/Y and monitor scratch are clobbered.
Bank 3 is required on entry/exit, IRQ disabled, decimal clear, and 816 E=1
with DBR/PBR zero. Save writes persistent flash; this is not a campaign query.

Authoritative contracts:
public include (repository reference: `release/candidates/rc1/source/assembler/str8n-v2-public.inc`),
service discovery (repository reference: `release/candidates/rc1/source/core/service-eq.inc`),
S/R/T implementation (repository reference: `release/candidates/rc1/source/core/str8n-v2-sr.asm`).
These source links are repository audit references. The user packages must
carry the self-contained tables and usage documentation without a developer tree.
