# STR8-N 2.0a24c1 detailed technical guide

This guide describes the implemented a24c1 monitor, RAM worker, stock-board
installer, configuration record and bank maintenance.
Mermaid diagrams show control flow and ownership; tables give exact addresses.
Use the [quick start](STR8N_V2_A24C1_QUICK_START.md) for installation and the
[operator manual](STR8N_V2_A24C1_MANUAL.md) for command syntax.

Firmware version is **2.0a24c1**. Maintenance is independently **1.0**.
a24c2 and its RST location byte are proposals, not features of this image.
Use the a24c1 configuration addresses given here.

## System components and ownership

The resident core executes from F in its resident bank. Code that must
continue while banks change or F is being modified executes from RAM.
The console bridge adds colors on the PC; the firmware sends plain bytes.

```mermaid
flowchart TB
    PC[Windows or Linux launcher] --> BR[WDCMON bridge and colored terminal]
    BR <-->|USB console bytes| BOARD[WDC SXB board]
    BOARD --> CORE[Resident F core]
    CORE --> WORK[RAM flash and console worker]
    CORE --> VEC[RAM vectors and public ABI]
    CORE --> CFG[Resident F configuration pocket]
    APP[RAM or banked application] --> VEC
    BM[Bank maintenance 1.0 in RAM] --> WORK
    BM --> VEC
```

The ROM facade requires the resident flash bank visible. Initialized RAM
entries can be called with another bank selected.

## CPU address space and flash translation

The SST39SF010A provides 128 KiB organized here as four 32 KiB banks.
For flash address A in `$8000-$FFFF`, physical offset is
`bank * $8000 + (A - $8000)`. Sector digits 8 through F name 4 KiB CPU pages.

```mermaid
flowchart LR
    CPU[CPU 8000-FFFF window] --> SEL{Selected bank}
    SEL --> B0[B0 physical 00000-07FFF]
    SEL --> B1[B1 physical 08000-0FFFF]
    SEL --> B2[B2 physical 10000-17FFF]
    SEL --> B3[B3 physical 18000-1FFFF]
    LOW[CPU 0000-7FFF] --> RAM[RAM and hardware I/O]
```

| CPU range | Ownership and restriction |
| --- | --- |
| `$0000-$00DF` | Application zero page |
| `$00E0-$00FF` | Monitor scratch; aliases have command-specific lifetimes |
| `$0100-$01FF` | CPU stack |
| `$0200-$68FF` | Application RAM, 26,368 bytes |
| `$6900-$78FF` | Full 4 KiB desired-sector image |
| `$7900-$7BFF` | Flash/console worker reservation; linked code ends `$7BF6` |
| `$7C00-$7C7F` | Line area; command limit 40 characters |
| `$7C80-$7CFF` | Byte workspace |
| `$7D00-$7D3F` | Monitor state, including resident bank and CPU identity |
| `$7D40-$7D7F` | 64-byte receive queue |
| `$7D80-$7D8F` | RAM configuration copy |
| `$7D90-$7DCA` | Private workspace |
| `$7DCB-$7DFF` | Unassigned in current definitions |
| `$7E00-$7E1F` | Emulation/native interrupt pointer area |
| `$7E20-$7EFF` | Vector code and public RAM facade; linked end `$7EE3` |
| `$7F00-$7FFF` | Hardware I/O address area |
| `$8000-$FFFF` | Selected flash bank |

```mermaid
block-beta
    columns 1
    ZP["0000-00FF: zero page"]
    STACK["0100-01FF: stack"]
    APP["0200-68FF: application RAM"]
    STAGE["6900-78FF: sector staging"]
    WORK["7900-7BFF: worker"]
    STATE["7C00-7DFF: buffers and state"]
    ABI["7E00-7EFF: pointers, vectors, ABI"]
    IO["7F00-7FFF: I/O"]
    FLASH["8000-FFFF: selected flash"]
```

## Resident flash and exact capacity

| Resident-bank range | Contents |
| --- | --- |
| `$F000-$FFBC` | Core and embedded RAM code images, 4,029 bytes |
| `$FFBD-$FFCF` | 19 unused bytes |
| `$FFD0-$FFDF` | 16-byte persistent configuration |
| `$FFE0-$FFFF` | Hardware vectors and reserved words |

```mermaid
flowchart TB
    F[F sector: F000-FFFF] --> CODE[F000-FFBC: core and RAM images]
    F --> FREE[FFBD-FFCF: 19 unused bytes]
    F --> CFG[FFD0-FFDF: configuration]
    F --> HW[FFE0-FFFF: hardware vector area]
    CODE --> COPY[Startup copies RAM implementations]
    COPY --> W[7900-7BF6 worker]
    COPY --> V[7E20-7EE3 vector code]
```

```mermaid
xychart-beta
    title "Linked bytes versus reserved bytes"
    x-axis [Worker, Vectors, CoreBeforeConfig]
    y-axis "Bytes" 0 --> 4096
    bar [759, 196, 4029]
    bar [768, 224, 4048]
```

The first series is linked use; the second is reserved capacity. Free space
is respectively 9, 28 and 19 bytes. The worker image is also stored in
the core image; these counts must not be added as independent flash allocations.

## Startup and reset-only autostart

Reset establishes monitor state and RAM services before normal use. Valid
enabled configuration selects a countdown and guest target. Erased or invalid
configuration holds. USB readiness is probed without making headless autostart
depend on a connected terminal. Delay is nominal tenths at the expected clock.

```mermaid
flowchart TD
    RESET[Hardware RESET] --> INIT[Initialize state and RAM code]
    INIT --> READ[Read resident F configuration]
    READ --> VALID{Valid and enabled?}
    VALID -->|No| READY[Console readiness and banner path]
    READY --> PROMPT[Monitor prompt]
    VALID -->|Yes| WAIT[Configured hold countdown]
    WAIT --> KEY{Hold or cancel key?}
    KEY -->|Yes| PROMPT
    KEY -->|No, time remains| WAIT
    KEY -->|No, expired| TARGET{Vector mode?}
    TARGET -->|Yes| J[Selected bank RESET-vector handoff]
    TARGET -->|No| G[Configured bank and address handoff]
```

Software HOLD returns to monitor use without repeating reset-only autostart.
J selects and executes a bank's vector; it does not pulse the physical RESET
pin. Guest execution has no return contract.

## Configuration record and checksum flow

| Offset in `$FFD0` record | Meaning |
| --- | --- |
| 0 | Format, currently 1 |
| 1 | Autostart enabled, 0 or 1 |
| 2 | Target bank, 0 through 3 |
| 3-4 | Fixed target address, low byte then high byte |
| 5 | Delay, `$0A-$FF` tenths |
| 6 | Target mode, 0 fixed address or 1 RESET vector |
| 7-13 | C-created records initialize these bytes to zero; included in checksum |
| 14 | Accumulated sum of bytes 0-13 modulo 256 |
| 15 | Accumulated sum of each intermediate first sum modulo 256 |

Validation checks format, enable, bank, delay, mode, the fixed-address
boundary where applicable, and both checksum bytes. Checksums detect many
changes but are not a cryptographic identity check.

```mermaid
flowchart LR
    BYTES[Bytes 0-13 in order] --> S1[sum1 = sum1 + byte modulo 256]
    S1 --> S2[sum2 = sum2 + sum1 modulo 256]
    S2 --> NEXT{More bytes?}
    NEXT -->|Yes| BYTES
    NEXT -->|No| STORE[Store sum1 at 14 and sum2 at 15]
    STORE --> CHECK[Validation compares both recorded sums]
```

```mermaid
sequenceDiagram
    participant U as Operator
    participant C as Core C command
    participant B as RAM sector buffer
    participant W as RAM worker
    participant F as Resident F
    U->>C: C enable bank target delay
    C->>C: Parse fields and construct checksums
    C->>F: Snapshot full sector
    F-->>B: 4096 bytes at 6900-78FF
    C->>B: Replace 78D0-78DF
    C->>U: Preview and confirmation
    U->>C: Y
    C->>W: Analyze desired sector
    alt unchanged
        W-->>C: No mutation required
    else write required
        W->>F: Program or erase/rewrite
        W->>F: Compare complete sector
        F-->>W: Comparison result
    end
    W-->>C: Result
    C-->>U: Prompt or RAM failure/retry
```

## Flash mutation and failure states

Flash changes require RAM execution while the selected bank or resident F
is unavailable. The staging buffer represents the desired whole sector;
out-of-range bytes are retained where the command promises preservation.

```mermaid
stateDiagram-v2
    [*] --> Preflight
    Preflight --> Canceled: rejected input or confirmation
    Preflight --> Snapshot: accepted operation
    Snapshot --> Analyze
    Analyze --> Verified: unchanged
    Analyze --> Program: programming sufficient
    Analyze --> Erase: erase required
    Erase --> Program
    Program --> Compare
    Compare --> Verified: complete sector matches
    Compare --> FailedInRAM: mismatch or flash failure
    FailedInRAM --> Erase: Y retry for core failure
    Verified --> Prompt: configuration operation
    Verified --> Restart: raw core self-edit
    Canceled --> [*]
    Prompt --> [*]
    Restart --> [*]
```

A failed core write remains in RAM. Configuration retry rewrites the complete
staged sector, then returns to the saving command when verified. Raw self-edit
uses restart semantics. Physical NMI/vector fetches, hardware failure and power
loss are not made safe by the RAM retry loop. There is one persistent config copy.

## Stock WDCMON installer gates

The RAM installer is loaded at `$2000`. Its current linked range is
`$2000-$2DB4`, 3,509 bytes; it does not embed the core BIN. The entry uses
SEC, `$FB`, SEI to establish 816 emulation; `$FB` is a one-byte NOP on C02.
Use the manifest to identify the exact build rather than relying on size.

```mermaid
sequenceDiagram
    participant U as Operator
    participant H as Host launcher and bridge
    participant M as Stock WDCMON
    participant I as RAM installer
    U->>H: Enter board port
    H->>U: Physical RESET gate
    U->>M: Press RESET
    U->>H: Wait two seconds, then Enter
    H->>M: Board query
    M-->>H: SXB tag and version
    H->>U: Confirm uppercase physical model
    U->>H: W65C02SXB or W65C816SXB
    H->>M: Load installer RAM
    H->>M: Read back RAM
    H->>M: Execute 2000 after byte-exact compare
    M->>I: Transfer execution
    I->>U: Backup and transfer prompts
    U->>H: Ctrl-U at BIN prompt
    H->>I: Exact 4096-byte core BIN
    I->>U: Exact install confirmation
    I->>I: Source guard, write and verify B3:F
    I->>U: Verified, press physical RESET
```

```mermaid
flowchart TD
    START[Identify stock flash and hash B3] --> BANK{Bank entry}
    BANK -->|0, 1 or 2| RANGE[Parse sector or ascending range]
    BANK -->|NONE| N1[Require NO BACKUP]
    BANK -->|Invalid| HALT[Cancel and halt in RAM]
    RANGE --> DEST{Destination range}
    DEST -->|Identical| READY[Backup policy satisfied]
    DEST -->|Erased| CONF[Require BACKUP B3]
    DEST -->|Occupied and different| HALT
    CONF --> COPY[Copy and compare backup]
    CONF -->|Invalid confirmation| HALT
    COPY -->|Match| READY
    COPY -->|Failure| HALT
    N1 --> N2[Require INSTALL WITHOUT BACKUP]
    N1 -->|Invalid confirmation| HALT
    N2 --> READY
    N2 -->|Invalid confirmation| HALT
    READY --> RX[Receive and validate core BIN]
    RX --> TEXT[Require INSTALL STR8-N 2.0A24C1]
    RX -->|Invalid image| HALT
    TEXT --> GUARD[Recheck original B3 hash]
    TEXT -->|Invalid confirmation| HALT
    GUARD --> WRITE[Write and verify B3:F only]
    GUARD -->|Source changed| HALT
    WRITE -->|Success| RESET[Wait for physical RESET]
    WRITE -->|Failure| REC[RAM recovery prompt]
    REC -->|R| WRITE
    REC -->|O and verified F backup| OLD[Restore old F and verify]
    REC -->|O without F backup| REC
```

Invalid confirmations halt; neither NONE nor a backup ending before F
provides an old-F restoration source. The source hash guard is an integrity
gate for this process, not cryptographic authentication. No stock-board
installer path should be used as an installed STR8-N updater.

## RAM loading and banked application calls

```mermaid
flowchart TD
    L[L command] --> RECORD[Read S19 record]
    RECORD --> VALID{Format checksum and RAM bounds valid?}
    VALID -->|No| ERROR[Reject record and return error]
    VALID -->|Yes| COPY[Write permitted RAM bytes]
    COPY --> LAST{Termination record?}
    LAST -->|No| RECORD
    LAST -->|Yes| ENTRY[Report entry address and return prompt]
    ENTRY --> G[Operator G address]
    G --> APP[Application executes]
    APP --> RAMABI[Initialized RAM ABI]
    RAMABI --> CON[RAM console implementation]
```

Loading does not execute the S9 entry automatically. Earlier accepted records
survive later errors/cancellation. The public RA descriptor at `$7E60` precedes
the three-byte JMP slots at `$7E64-$7E88`. The descriptor is `RA 01 0D`.

| Interface | Contract |
| --- | --- |
| ROM signature/facade | `$F000`, RESET `$F004`, HOLD `$F007`; resident bank visible |
| RAM signature/facade | `$7E60`, RESET `$7E64`, HOLD `$7E67`; initialized monitor required |
| Capability descriptor | `$F035`, `CA 01 17`; native vectors advertised, native service calls not advertised |
| Call mode | IRQ disabled, decimal clear; 816 E=1, DBR=0, PBR=0 |
| Reentrancy | Monitor services are not reentrant |
| Native interrupt pointers | Handlers own widths, bank/direct-page requirements, frame and RTI |

See [public definitions](../src/v2-config/str8n-v2-public.inc) for every slot,
flag and pointer. Use published symbols rather than guessed internal labels.

## Bank maintenance data paths

The utility runs at `$2000-$3347`, with editor buffer `$5000-$5FFF` and state
`$6000-$61FF`. It uses the core's `$6900-$78FF` staging and RAM worker.
RAM copy/read/write bounds exclude the utility and its workspace.

```mermaid
flowchart LR
    RAM[Permitted application RAM] <-->|C or V| FLASH[Selected flash bank]
    RAM <-->|C or V| RAM2[Another permitted RAM range]
    FLASH <-->|C or V| FLASH2[Another flash bank or range]
    RAM -->|R| EDIT[Editor 5000-5FFF]
    FLASH -->|R| EDIT
    PATCH[P or F patch/fill] --> EDIT
    NEW[N new fill] --> EDIT
    SELF[S 8 or S 9 utility block] --> EDIT
    EDIT -->|W| STAGE[Desired sector 6900-78FF]
    STAGE --> WORK[RAM worker]
    WORK --> FLASH
    EDIT --> D[D display and K CRC]
```

```mermaid
flowchart TD
    CMD[Erase copy or buffer write] --> PLAN[Show normalized destination]
    PLAN --> Y{Y confirmation?}
    Y -->|No| STOP[Cancel before destination change]
    Y -->|Yes| TOP{Touches B3:F?}
    TOP -->|Yes| TOKEN{B3F confirmation?}
    TOKEN -->|No| STOP
    TOKEN -->|Yes| TOUCHED[Mark resident F targeted]
    TOUCHED --> OP[Perform and verify operation]
    TOP -->|No| OP
    OP --> RESULT[Return result]
    TOUCHED --> Q[Q blocked if resident F was targeted]
    Q --> J[Use explicit J to known firmware]
```

The mark applies when resident F is targeted, even if a subsequent operation
repairs it. Completed sectors remain changed on later failure or cancellation;
there is no multi-sector transaction rollback. CRC is CRC-16/CCITT-FALSE,
polynomial `$1021`, initial `$FFFF`. An archived S 8/S 9 utility needs restoration
to RAM before execution; J 1 does not launch the archive.

## Console display and logging

```mermaid
flowchart LR
    RX[Board byte stream] --> RAW[Unmodified raw transcript]
    RX --> LINE[Display line and partial-prompt buffer]
    LINE --> CLASS{Text classification}
    CLASS -->|Failure refusal halt| RED[Red]
    CLASS -->|Input reset transfer write| YELLOW[Yellow]
    CLASS -->|Success verification| GREEN[Green]
    CLASS -->|Other information| CYAN[Cyan]
    KEYS[Host key input] --> EVENT[Session event log]
    KEYS --> TX[Serial input or file transfer]
```

Color is a display aid. Partial text is flushed after approximately 100 ms
of receive inactivity; newline and prompt markers flush earlier. A mixed
success/reset line is yellow because action takes priority. Ctrl-U sends
the core BIN in the installer session; Ctrl-D sends maintenance. Ctrl-] exits.
Do not press a file-transfer key before the corresponding receive prompt.

## Linux launcher

`INSTALL-A24C1.sh` resolves its directory and starts `install_a24c1_linux.py`.
It needs Python 3 and pyserial. On Debian/Ubuntu install them with
`sudo apt install python3 python3-serial`. Use an interactive terminal and a
serial device such as `/dev/ttyUSB0`; the account must have access to the device.

The script sets 115200, 8-N-1, RTS/CTS hardware flow control and DTR false
before opening the port, then requests physical RESET. Linux drivers may still
toggle modem control on open, so installed-monitor reconnect behavior needs
physical testing. It validates the S19 checksum/dense bounds, checks the core
BIN length, asks for physical board confirmation, and reads back every RAM
chunk before issuing the execution command. It never auto-confirms a flash write.

```mermaid
flowchart TD
    SH[INSTALL-A24C1.sh] --> PY[Python Linux bridge]
    PY --> FILES[Validate installer core and maintenance]
    FILES --> MODE{Launch mode}
    MODE -->|Validate only| OFFLINE[Report file checks without serial access]
    MODE -->|Stock installation| RESET[Open device and request physical RESET]
    RESET --> BOARD[Query and confirm board]
    BOARD --> LOAD[RAM load and byte-exact readback]
    LOAD --> EXEC[Execute RAM installer]
    EXEC --> TERM[Colored raw terminal]
    MODE -->|Terminal only| TERM
    TERM --> RESTORE[On exit restore host terminal settings]
```

Ctrl-U sends the core during stock installation; Ctrl-D sends maintenance.
In terminal-only mode Ctrl-U sends maintenance. Ctrl-] exits; Ctrl-C is sent
through to the board. Terminal settings are restored on normal exit or error.
The Windows-only Ctrl-B host probe shortcut is not implemented on Linux.
Linux has no raw/event log options in this first launcher; the logging diagram
above describes the Windows bridge. `--validate-only` needs no pyserial and
opens no device. Ubuntu WSL file/protocol tests pass. The owner reported a
successful native Linux run on 2026-10-02.

## Build identity and release checks

| Command or artifact | Purpose |
| --- | --- |
| `make v2-config` | Build core and probes |
| `make v2-config-check` | Core and configuration regression |
| `make v2-config-wdcmon-check` | Build and execute installer model checks |
| `make bank-maint-v2-check` | Maintenance CPU/flash model checks |
| `INSTALL-A24C1.ps1 -ValidateOnly` | File/S19 checks without opening serial |
| Installer manifest | Exact installer/core hashes and backup policy |
| Core build report | Symbol addresses, byte counts and artifact hashes |

The current core F SHA-256 is
`231fbec1b0e6a1e80f4a956009aa74f6259e4f0dfcf761f09f16755832aece36`.
Configured live F differs from the erased-pocket factory image. Validate the
settings separately and compare firmware outside `$FFD0-$FFDF`; retain a hash
of the complete board readback. Installer and bridge hashes change when their
messages or host presentation change; the final package must capture new hashes.

## Board acceptance and remaining qualification

For each CPU family, record physical board identity, COM port, exact image
hashes, bank inventory, backup choice and test result. Acceptance includes
verified stock migration, physical RESET banner/prompt, full power-off/on,
configuration persistence and hold cancellation, S19 load and execution,
bank selection/handoffs, RAM ABI and interrupt checks, and maintenance operations
on known scratch sectors with neighboring-bank preservation.

Repeat backup reuse/refusal and permitted recovery cases separately.
Native-vector behavior needs its own recorded results.
Host-model success is not a substitute for physical qualification. The user
has confirmed the colored script works well; this does not by itself record
completed migration/reset acceptance on both boards. The successful verified
stock migration plus physical reset milestone is still the basis for beta 1.

## Proposed a24c2 differences

```mermaid
flowchart LR
    A24C1[a24c1 implemented] --> C1APP[Application 0200-68FF]
    A24C1 --> C1BUF[Staging 6900-78FF]
    A24C1 --> WORK[Worker 7900-7BFF]
    A24C2[a24c2 proposal] -.-> C2APP[Application 0200-5FFF]
    A24C2 -.-> PAGE[Reserved 6000-60FF]
    A24C2 -.-> C2BUF[Staging 6100-70FF]
    A24C2 -.-> RST[RST reservation 7100-78FF]
    A24C2 -.-> WORK
```

The future maintenance state at `$6000-$61FF` conflicts with that proposal's
reservation/staging boundary and must be reviewed. No a24c2 RST locator field,
copy-length descriptor or RAM entry contract has been assigned. See the
[proposal](STR8N_V2_A24C2_RAM_LAYOUT.md); do not substitute its addresses here.

## Implementation references

- [RAM and hardware definitions](../src/v2-config/str8n-v2-eq.inc)
- [Public interface](../src/v2-config/str8n-v2-public.inc)
- [Configuration implementation](../src/v2-config/str8n-v2-config.inc)
- [Flash worker](../src/v2-config/str8n-v2-flash-worker.inc)
- [Installer policy](../tools/wdcmonv2/a24c1-backup-policy.asm)
- [Bridge](../tools/wdcmonv2/start_wdcmonv2_ram.ps1)
- [Maintenance guide](STR8N_BANK_MAINT_V2.md)
- [Configuration guide](STR8N_V2_FLASH_CONFIG.md)
