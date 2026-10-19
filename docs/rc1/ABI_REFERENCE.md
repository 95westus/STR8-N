# rc1 ABI reference — source-audited addresses

The JSR facade below targets the generation-49 public include and remains
unchanged in DBG1 generation 50. The separate
[BRK extension](#dbg1-brk-functions-and-registrations) requires DBG1; this is
not a v2.1 or native-mode ABI.
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

## DBG1 BRK functions and registrations

`BRK $xx` encodes `$00,xx`, consumes two bytes and resumes after the signature.
It enters through the current flash bank's hardware vector. Use only permitted
application RAM under the matching generation-50 MON A/B, core and ASM.
65C02 and 65C816 E=1 are supported; on 816, direct page/DBR/PBR must be zero.
IRQ must remain masked. Native applications/debugging are outside scope.

| Signature | Implemented contract |
| --- | --- |
| `$00-$7F` | Stop at `DBG>` |
| `$80` | Query: A=`01` (BRK ABI version), X=`10` (16 user slots), Y=`04` (4 system slots), C=1; capacities, not free counts |
| `$81` | Register user callback; A/X=low/high address of four-byte request; success C=1,A=0; invalid/duplicate/full C=0,A=1 |
| `$82` | Unregister a registered user ID in A (`$C0-$FE`); success C=1,A=0; not found C=0,A=1 |
| `$83` | Print saved registers and continue, preserving saved registers/flags |
| `$84` | Output Y bytes from A/X low/high RAM pointer; valid call preserves saved registers/flags; invalid range C=0,A=1; Y=0 outputs nothing |
| `$85-$9F` | No additional fixed services implemented; stop if unrecognized |
| `$A0-$BF` | Call a registered system callback, otherwise stop |
| `$C0-$FE` | Call a registered user callback, otherwise stop |
| `$FF` | Not user-registrable; an application use is unrecognized and stops |

Unlike registration/query success, successful `$84` preserves the input carry;
do not require C=1 as a new success result. These calls save context and have
more overhead than a JSR. The existing 13 JSR entries remain available.
Future console wrappers `$85-$8E` are
[proposals only](../../release/candidates/rc1-debugger/BRK_ABI.md).
Private firmware uses of `$FC/$FD/$FF` are origin-checked; application
`$FC/$FD` still follow user registration rules.

### Separate user and system capacity

| Class | Allowed IDs | Entries | RAM cost | Registration |
| --- | --- | --- | --- | --- |
| Fixed firmware | `$80-$9F` (currently `$80-$84`) | No dynamic entry | No registry slot | Built into firmware |
| System | `$A0-$BF` | 4 | 16 bytes | Driver/firmware entry described below |
| User | `$C0-$FE` | 16 | 64 bytes | `BRK $81`, removal with `BRK $82` |

There are 20 simultaneous dynamic entries in 80 reserved bytes at
`$7C30-$7C7F`: system `$7C30-$7C3F`, user `$7C40-$7C7F`. The number of IDs in
a range is not the number of slots. User registrations cannot consume the
four system entries or replace fixed/system IDs. IDs must be unique in their
class. No system-unregister service is provided in this version.

The request layout is `ID, handler-low, handler-high, flags`. Flags must be
zero. All four request bytes and the callback entry must lie in permitted
application RAM, using the current discovered limit. Registration copies the
request fields; it does not relocate or retain the callback's code. Keep the
handler loaded until unregister or program exit.

All dynamic registrations clear at **HOLD, X or reset**, including system
entries. A driver must register for each new program; "system" means separate
capacity/ownership, not persistence across program loads. Debugger `F` lists
the five built-ins and current registered IDs/handler addresses.

### Callback and saved-context contract

Both classes receive A=`00`, X=`70` (pointer `$7000`), Y=signature, and return
with **RTS**. Change results in this saved context, not just live A/X/Y/P:

| Offset from `$7000` | Saved application value |
| --- | --- |
| 0-1 | Resume PC, little endian, after the two-byte BRK |
| 2 | A |
| 3 | X |
| 4 | Y |
| 5 | P; bit 0 is application carry |
| 6 | SP |

For example, `LDA #$42` / `STA $7002` / `RTS` returns A=`42` to the
application. A live `SEC` alone does not set the saved application carry;
update bit 0 of `$7005` for a carry result. Preserve flash-bank selection and
the E=1/zero-bank/direct-page/IRQ preconditions. Do not call private loaders,
flash staging, HOLD, or another BRK from a callback. Nested BRK is refused
with live C=0,A=9 without replacing the outer saved context; it is not a
supported way to nest services. Other context bytes are private.

See the [ASM user-registration example](ASM_GUIDE.md#user-registration-example).
Its request and handler are assembled into RAM along with the caller.

### System registration entry and example

With **B1 visible, IRQ masked and no active debug session**, load the LE16
entry pointer stored at B1:`$A008-$A009`. Pass A/X=request low/high pointer;
call that pointer through a RAM trampoline and return with RTS. `$A008` is
pointer data, not a JSR entry address. Success returns C=1,A=0; invalid,
duplicate, full or active-session requests return C=0,A=1. Other live
register/scratch preservation is unspecified. Only `$A0-$BF` is admitted.

This ASM source runs at `$0200`. Assemble/export normally, leave ASM, select
`B1`, then `G 0200` on an idle DBG1 board. It registers `$A1` before any BRK,
calls it, then stops at `BRK 01` with saved A=`66`. C reaches HOLD and clears
the registration. The `$00/$01` trampoline pointer is application scratch.

<!-- debugger-example: system-registration -->
```asm
10 ORG $0200
20 SEI
30 CLD
40 LDA $A008
50 STA $00
60 LDA $A009
70 STA $01
80 LDA #<request
90 LDX #>request
100 JSR register
110 BCC failed
120 BRK $A1
130 BRK $01
140 JMP $7E67
150 register: JMP ($0000)
160 failed: BRK $7F
170 JMP $7E67
180 request: BYTE $A1
190 WORD handler
200 BYTE 0
210 handler: LDA #$66
220 STA $7002
230 RTS
240 END
```

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
