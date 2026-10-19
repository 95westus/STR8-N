# rc1 DBG1 RAM debugger

Requires the **generation-50 DBG1 candidate**, including its matching ASM,
MON A/B and resident core. Published rc1 generation 49 does not include this
extension. Both retain the `2.0rc1` version string and `ASM 0.5` title: check
`VERSION` for `00000032` (50 decimal), rather than relying on those titles.
See [board results](DEBUGGER_BOARD_RESULTS.md) for the tested package identity.

The debugger supports **65C02 and 65C816 emulation-mode applications only**.
On the 816, E=1 and direct page, DBR and PBR must be zero. Keep IRQ masked.
Native applications and native debugging are outside scope; the existing
startup CPU detector is unchanged.

## Enter automatically with BRK xx

Run a RAM application normally, for example `G 0200`. An application `BRK $01`
enters `DBG>` automatically; there is no enable command. ASM accepts
`BRK $xx` and `BRK #$xx`, with a one-byte signature. Bare `BRK` supplies `$00`.
All forms occupy two bytes: opcode `$00`, then the signature byte.

Signatures `$00-$7F` stop for inspection. `$80-$84` are the implemented BRK
services. Registered system/user signatures call their RAM handlers; other
unrecognized signatures stop. A stop displays the saved PC, A, X, Y, P and
stack pointer (`S=` in output). For an explicit BRK, PC is the instruction
after its two bytes. At a patched breakpoint, PC is the original instruction
that has not yet executed. The signature byte is data, not another instruction.

Debugging is confined to permitted application RAM, normally `$0200-$64FF`.
The optional-service descriptor can release the area through `$66FF`; use its
discovered limit. RAM execution still needs compatible hardware vectors in the
selected flash bank. The complete candidate supplies them in B1/B2/B3; an
empty or unrelated B0 does not provide automatic BRK entry.

## Commands at DBG>

All addresses, values and counts are hexadecimal.

| Command | Action |
| --- | --- |
| `C` | Continue, rearming persistent breakpoints |
| `S` | Execute one instruction; enter a RAM JSR target |
| `N` | Execute one instruction; step over JSR to the matching return depth |
| `B` | List persistent breakpoints |
| `B address` | Set one of eight persistent breakpoints |
| `BC address` | Clear one breakpoint |
| `BC *` | Clear all eight |
| `R` | Display saved registers |
| `R A=12`, `R X=34`, `R Y=56`, `R P=24`, `R SP=FF`, `R PC=0200` | Edit one saved register |
| `D start [end]` | Shared monitor hex dump |
| `M address byte ...` | Shared monitor atomic RAM edit |
| `U [address] [count]` | Disassemble RAM; defaults to saved PC and eight instructions |
| `F` | List built-in and registered BRK function IDs |
| `?` | Show help |
| `X` | Abort, clean up and return to the monitor |

The prompt determines meaning: monitor `C` configures and monitor `S` stores
in flash; debugger `C` continues and debugger `S` steps. Debugger `U`
disassembles, whereas monitor `U A|B` updates a slot. Debugger `F` lists
functions; monitor `F` patches flash.

`S` on JSR enters the subroutine; step its instructions and RTS to return.
`N` on JSR runs until the return address and original stack depth match,
including recursive calls. A user breakpoint inside the call interrupts `N`.
On other supported instructions, `N` behaves like `S`. Stepping a BRK service
stops immediately after that service returns. `S` refuses a transfer out of
application RAM; `N` can run a firmware call to its return. Neither is a timer
or a cycle-accurate execution mode.

## All eight persistent breakpoints

Choose instruction boundaries in the loaded RAM program. `B address` uses one
of eight records; a ninth distinct breakpoint is refused with `?` and keeps
the existing eight. Two internal stepping records do not consume user slots.
See the [ASM eight-breakpoint example](ASM_GUIDE.md#eight-breakpoint-loop) for
a program with eight consecutive one-byte instructions.

While stopped, all patched bytes are restored, so `D`, `M` and `U` show/edit
the original instructions. `C`, `S` and `N` preserve the breakpoint records
and rearm them when needed. Continuing at a hit executes the original
instruction once before rearming that address, so a loop can hit it again.
An edit at a breakpoint changes the instruction saved when it is next armed.
The running program must not overwrite armed breakpoint bytes.

Persistent means across continue/step operations in the current program.
HOLD, `X` and reset clear the records and dynamic registrations; they do not
persist across program loads or power cycles. Use `BC address` or `BC *`
when you want to keep running the current program without those stops.

## Inspecting saved memory and execution limits

Shared D/M return to `DBG>`. Low-page accesses use the saved application
zero-page/stack images; a low-page D/M request must remain in one page, and
zero-page writes above `$DF` are refused. Do not edit private debugger state
or interpret these commands as permission to access I/O.

The component occupies B1:`$A000-$AFFF`: 3,967 code bytes plus a two-byte CRC,
leaving 127 bytes. It uses existing reserved monitor workspace and does not
reduce application RAM or ASM buffers. Applications need nine free stack
bytes for entry. Bytes below SP are scratch, not preserved allocated stack.

WAI, STP and unsupported opcode encodings cannot be stepped. On 65C816 E=1,
the debugger uses the instruction subset shared with ASM's 65C02 table.
RMB/SMB/BBR/BBS encodings have different 816 meanings: `U` shows `.BYTE`, and
`S`/`N` refuse them, as they do other encodings outside that subset. Full
816-only decoding is outside this version. Clear a breakpoint on an
unsupported instruction before using `C` to execute it. The hidden accumulator
B byte is preserved but has no register-edit field.

IRQ/NMI execution is not virtualized. Private loaders and flash staging share
workspace with the debugger; do not call them from an active session. S/R/T
staging and resident flash mutation protect the debugger sector. These limits
do not grant flash debugging or native-mode support.

The eight-hour hardware soak passed 431 cycles on each board (2604 MON B,
2609 MON A in E=1), with all eight breakpoints hit twice per cycle. Original
application RAM restoration, unchanged flash/settings, and the final drift
snapshot passed. See [results and measurement limits](DEBUGGER_BOARD_RESULTS.md).
Native mode remains outside scope.

Use the [ASM examples](ASM_GUIDE.md#debugging-ram-programs-with-dbg1),
[BRK ABI and registrations](ABI_REFERENCE.md#dbg1-brk-functions-and-registrations)
and [hardware/offline results](DEBUGGER_BOARD_RESULTS.md) for the next step.
