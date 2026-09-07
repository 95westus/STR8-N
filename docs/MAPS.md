# STR8-N v1.32 Maps and Diagrams

These diagrams describe the host-qualified and board-derived v1.32 release.

## Ownership

```mermaid
flowchart TB
    RESET[Physical RESET] --> S[STR8-N<br/>Bank 3 $F000-$FFFF]
    S -->|J0| B0[Bank 0 guest]
    S -->|J1| B1[Bank 1 guest]
    S -->|J2| B2[Bank 2 guest]
    S -->|C/W| B3[Bank 3 HIMON<br/>$C000]
    S -->|J3| R3[Bank 3 RESET vector<br/>normally STR8-N again]
    S -->|I| W[RAM worker<br/>$0200-$045F]
    W --> FLASH[Selected flash range]
    S -->|L| RAM[Recovery RAM program<br/>$2000-$7AFF, then S9]
    RAM -->|bank-maint S19| BM[Self-contained Bank Maintenance<br/>map/copy/adopt/reclaim/erase/AP put]
    BM -->|private RAM worker| FLASH2[Banked flash<br/>Bank 3 F guarded]
    BM -->|Q| S
    B3 -->|L, then explicit G| RAM2[HIMON RAM program]
```

## Build and artifact flow

```text
BUILD/
|-- v1.32/
|   |-- bin/                 all STR8-N binary images
|   |-- s19/                 all release and user-built S19 images
|   `-- test/range-matrix/   generated S19 qualification fixtures
|-- str8n-manifest.json      stable R-YORS discovery path
|-- obj/                     assembler intermediates
|-- lst/                     listings
`-- sym/                     symbols
```

```mermaid
flowchart LR
    SRC[src/str8.asm] --> TOP[4096-byte Bank-3 top BIN]
    SRC --> WORKER[608-byte worker evidence S19]
    BM_SRC[bank-maint ASM] --> BM[RAM bank-maint S19]
    TOP --> MANIFEST[verified manifest]
    WORKER --> MANIFEST
    BM --> MANIFEST
    RY[R-YORS 28K ASM+HIMON S19] --> FULL[32K Bank-0/1/2 8-F S19]
    TOP --> FULL
    TOP --> PROGRAMMER[external programmer]
    PROGRAMMER --> B3F[physical $1F000-$1FFFF]
    TOP --> UPDATE[guarded v1.32 top updater S19]
    UPDATE -->|STR8-N L, verified backup first| B3F
    TOP --> REFRESH[guarded directory-refresh S19]
    REFRESH -->|STR8-N L, backup, clear $FFB0-$FFEF, install $FFF0=$1E| B3F
    TOP --> ABI_TEST[resident ABI hardware-probe S19]
    BM -->|STR8-N L| RAM_TOOL[temporary maintenance session]
    FULL -->|STR8-N I| GUEST[enrolled Bank 0, 1, or 2]
    TOP --> WDC_TOP[migration-configured top<br/>D0 WDCM2; roles FF/FF]
    WDC_TOP --> WDC_INSTALL[factory migration RAM S19]
    WDC_INSTALL --> KIT[allowlisted migration ZIP<br/>no WDC/R-YORS payload bytes]
```

The top updater preserves the live directory pocket. The directory-refresh
artifact deliberately replaces that pocket with `$FF`, after first verifying
a full live-sector backup in Bank 1 sector F. Bank Maintenance `D` can then
adopt a payload into an erased row without rewriting payload bytes.

## Physical flash to CPU view

```text
physical flash       bank     CPU view
$00000-$07FFF        0        $8000-$FFFF
$08000-$0FFFF        1        $8000-$FFFF
$10000-$17FFF        2        $8000-$FFFF
$18000-$1EFFF        3        $8000-$EFFF payload
$1F000-$1FFFF        3        $F000-$FFFF protected STR8-N
```

```mermaid
flowchart LR
    LATCH[VIA PCR bank bits] --> WINDOW[CPU $8000-$FFFF window]
    B0[Physical Bank 0] --> LATCH
    B1[Physical Bank 1] --> LATCH
    B2[Physical Bank 2] --> LATCH
    B3[Physical Bank 3] --> LATCH
```

## Boot and handoff

```mermaid
flowchart TD
    R[Physical RESET<br/>forces Bank 3] --> A[Silent pre-I/O quarantine<br/>keys ignored]
    A --> P[Flush input<br/>STR8-N 1.32]
    P --> Q{Silent live selector interval<br/>0-2 C W S}
    Q -->|0,1,2| C{Directory COMPLETE?}
    C -->|no| F[Refuse handoff]
    C -->|yes| J[Select bank and jump through RESET vector]
    Q -->|C, W, or timeout| M{Compatible HIMON marker?}
    M -->|C cold; W/timeout warm| H[HIMON at $C000]
    M -->|no| S[STR8-N prompt]
    Q -->|S| S
    S -->|J0-J3| J
    S -->|I| I[Installer]
    S -->|L| L[Load RAM $2000-$7AFF<br/>and execute S9]
```

## Factory WDCMONv2 migration

```mermaid
flowchart TD
    F[Factory board<br/>stock WDCMONv2 in B3; B0 erased] --> H[PowerShell bridge<br/>physical-reset gate]
    H --> V[Require SXB2 identity<br/>RAM load/readback byte-exact]
    V --> M{Exact MIGRATE confirmation?}
    M -->|no| X[Cancel in RAM<br/>flash unchanged]
    M -->|yes| C[Copy all eight B3 sectors to B0]
    C --> E[Whole-bank FNV prefilter<br/>plus byte-exact B0/B3 compare]
    E --> T[Validate carried 4K top<br/>then program/verify B3:F]
    T --> D[Publish COMPLETE D0 WDCM2<br/>roles FFF0/FFF1 remain FF/FF]
    D --> S[STR8-N 1.32 in B3]
    S -->|selector 0 or J0| W[Retained WDCMONv2 in B0<br/>CS0-CS3 chase]
    W -->|physical RESET| S
```

The accepted minimal path never writes B1 or B2 and does not install HIMON,
ASM-F2, or R-YORS. The optional read-only archive path remains available for
additional owner-local evidence but is not a gate for an erased-B0 factory
board.

## Install transaction

```mermaid
flowchart TD
    A[Choose bank, exact range,<br/>and new identity if needed] --> B{WRITE? Y}
    B -->|no| Z[Return to prompt<br/>no transaction]
    B -->|yes| D[Copy and verify embedded worker in RAM]
    D --> C[Write START and any<br/>first-enrollment identity]
    C --> E[Print S19<br/>sender may run full speed]
    E --> G[Stream, program and verify<br/>each completed non-final sector]
    G --> F{Exact extent, checksum,<br/>S9 and policy valid?}
    F -->|no| X[FAIL / bank remains incomplete]
    F -->|yes| H{COMMIT? Y}
    H -->|no or interrupted| X
    H -->|yes| K[Program and verify final sector]
    K --> L[Write COMPLETE journal bit]
    L --> O[OK / bank may boot]
```

`WRITE? Y` is the persistent boundary. START is already written when `S19`
appears; a missing or bad transfer therefore requires full-range recovery.

## Directory state and launch gate

```mermaid
stateDiagram-v2
    [*] --> Erased: external programmer / empty row
    Erased --> Started: WRITE? Y or maintenance enrollment
    Started --> Started: interrupted or failed transaction
    Started --> Complete: full image verified / COMPLETE written last
    Complete --> Started: later install begins
    Complete --> Complete: later install verifies
    Complete --> Exhausted: all 16 journal pairs used
    Exhausted --> Erased: guarded onboard or external refresh
```

`J0`-`J2` accept only `Complete`. Bank Maintenance `C` accepts only `Erased`
destination rows. Bank Maintenance `D` can adopt an existing payload only into
an `Erased` row; neither command overwrites or repairs an existing identity.
After proving all eight sectors of a Bank 0-2 payload are erased, `R` can
return only that bank's stale row to `Erased` by rewriting and verifying the
complete guarded Bank-3 sector F. It first keeps a verified original B3F copy
in the selected bank's sector F and erases that temporary backup only after
the protected rewrite verifies.

## Protected 4K top sector

```text
$FFFF  +------------------------------+
       | hardware vectors       6 B   |
$FFF9  +------------------------------+
       | WORK=$1E + reserve     10 B   |
$FFEF  +------------------------------+
       | bank directory        64 B   |
$FFAF  +------------------------------+
       | stored worker        608 B   |
$FD4F  +------------------------------+
       | available growth      10 B   |
$FD45  +------------------------------+
       | resident code/data  3398 B   |
$F000  +------------------------------+
```

## Legal top-aligned install sizes

```text
Banks 0-2, ending at $FFFF       Bank 3, ending below STR8-N
 4K  F    $F000-$FFFF            4K  E    $E000-$EFFF
 8K  E-F  $E000-$FFFF            8K  D-E  $D000-$EFFF
12K  D-F  $D000-$FFFF           12K  C-E  $C000-$EFFF
16K  C-F  $C000-$FFFF           16K  B-E  $B000-$EFFF
20K  B-F  $B000-$FFFF           20K  A-E  $A000-$EFFF
24K  A-F  $A000-$FFFF           24K  9-E  $9000-$EFFF
28K  9-F  $9000-$FFFF           28K  8-E  $8000-$EFFF
32K  8-F  $8000-$FFFF
```

These are useful top-aligned examples, not a restriction. Any contiguous
sector span inside `8-F` (Banks 0-2) or `8-E` (Bank 3) is accepted. `I` always
writes flash. STR8-N `L` is a separate recovery RAM load-and-execute path.

## Full R-YORS Bank-0/1/2 image

```text
$FFFF  +------------------------------+
       | STR8-N clone + vectors       |
$F000  +------------------------------+
       | HIMON                        |
$C000  +------------------------------+
       | ASM-F2                       |
$8000  +------------------------------+

range: $8000-$FFFF (8-F), 32768 bytes
S9:    $F000, matching RESET at $FFFC-$FFFD
```

This image is built from the current R-YORS `8-E` payload and the current
STR8-N top BIN. It is not used to update Bank 3 sector F.

## Flash install versus RAM load

```mermaid
flowchart LR
    S19[S19 file] --> CHOICE{What should survive reset?}
    CHOICE -->|lasting image| I[STR8-N I]
    I --> FW[Selected flash sectors]
    CHOICE -->|recovery program| SL[STR8-N L]
    SL --> RP[STR8-N F009 parser]
    RP --> BOUND[check complete S1 span<br/>$2000-$7AFF]
    BOUND --> RM[copy to RAM and jump to S9]
    CHOICE -->|monitor load-only| HL[HIMON L]
    HL --> HP[STR8-N $F009 SR/02 parser<br/>HIMON policy below $7A00; explicit G]
```

## Recovery RAM load

```mermaid
flowchart TD
    C[STR8-N L] --> P[Receive and validate S0/S1/S9]
    P -->|valid S1| R{Whole record inside<br/>$2000-$7AFF?}
    R -->|yes| M[Copy record to RAM]
    R -->|no| Q[Latch failure; discard through<br/>valid S9 or Ctrl-C]
    M --> P
    P -->|valid S9 after data| E{S9 inside<br/>$2000-$7AFF?}
    P -->|parse/checksum/type failure| Q
    E -->|no| F[Return to prompt; do not execute]
    E -->|yes| G[SEI, CLD, X/SP=$FF,<br/>jump to S9]
    Q --> F
```

## STR8-N v1.32 RAM ownership

```text
$7DFF  +------------------------------+
       | STR8 state $7DE7-$7DFF       |
$7DE6  +------------------------------+
       | reserved $7DC8-$7DE6         |
$7DC7  +------------------------------+
       | HIMON AP link $7DC0-$7DC7    |
$7DBF  +------------------------------+
       | High Tool Overlay            |
       | $7C00-$7DBF                  |
$7BFF  +------------------------------+
       | monitor / record service RAM |
       +------------------------------+
$1FFF  +------------------------------+
       | standalone STR8 user-low RAM |
       | $1A00-$1FFF                  |
$19FF  +------------------------------+
       | 4K sector tray $0A00-$19FF  |
$09FF  +------------------------------+
       | free WCT tail $0460-$09FF    |
       | allocate down from $09FF     |
$045F  +------------------------------+
       | current worker $0200-$045F   |
$01FF  +------------------------------+
       | stack                        |
$00FF  +------------------------------+
       | state and ZP scratch         |
$0000  +------------------------------+
```

STR8-N itself leaves `$1A00-$1FFF` free for user programs in v1.32. In the
integrated R-YORS payload, APMAN transiently uses `$1A00-$1AFF` as its command
shadow while `AP`, `APS`, or banked `INSTALL` delegates; `$1B00-$1FFF` remains
the unconditional user-low slice outside another phase owner. The whole `$0200-$09FF` Worker
Code Tray (WCT) remains phase-owned and volatile during worker calls, but the
maintained runtime workers do not extend above `$045F`: the unified STR8-N
worker ends at `$045F`, the Bank Maintenance private worker ends at `$042A`,
and HIMON's bank-safe helpers end below both. A phase-local allocator may
therefore consume the currently free `$0460-$09FF` tail downward from `$09FF`,
provided it checks its low-water mark against the published exclusive
`STR8_WORKER_END` and does not expect those bytes to survive a worker call.
Development and proof programs may still use other addresses in the WCT and
are not covered by this maintained-runtime high-water guarantee.

Bank Maintenance and the other foreground tools use the single-owner
`$7C00-$7DBF` overlay. The exact `$7DE7-$7DFF` Recovery State Capsule fields
are listed in the [Technical Guide](TECHNICAL_GUIDE.md#str8-n-v130-high-ram-abi).

## RAM capacity by operating path

```text
Board RAM below I/O                         32,512 bytes  $0000-$7EFF
STR8-N L accepted window                    23,296 bytes  $2000-$7AFF
I named transient/service areas              5,014 bytes  excluding L flag
Fixed IVI cells                                  11 bytes
Maximum hardware stack                         256 bytes  dynamic
Outside named I/fixed areas                  27,487 bytes  before stack use
R-YORS normal application convention         18,694 bytes  monitor-dependent
Bank-maint loaded image                       6,579 bytes  $2000-$39B2
```

```mermaid
flowchart LR
    TOTAL[32,512 B board RAM] --> LOW[8,192 B below $2000]
    TOTAL --> LWIN[23,296 B accepted by STR8-N L]
    TOTAL --> HIGH[1,024 B $7B00-$7EFF<br/>parser, IVI, I/O-adjacent]
    LWIN --> BMIMG[6,579 B bank-maint image]
    LWIN --> LOTHER[16,717 B remaining in L window]
```

The numbers describe STR8-N boundaries, not a promise that HIMON, ASM, or an
arbitrary guest leaves every other byte unused.

## Bank-maintenance RAM tool

```mermaid
flowchart TD
    L[STR8-N L] --> S[S19 loads $2000-$39B2<br/>S9=$2000]
    S --> B[Copy private worker<br/>$3400-$362A to $0200-$042A]
    B --> M{Command}
    M -->|M| MAP[Stage and inspect sectors<br/>no flash mutation]
    M -->|C| COPY[Require empty directory row<br/>copy and verify full bank]
    COPY --> ID[TYPE + five-character DESC<br/>START, identity, COMPLETE]
    COPY -->|identity cancelled| PAYLOAD[Verified payload remains<br/>directory row stays erased]
    M -->|D| ADOPT[Validate existing RESET<br/>require empty directory row]
    PAYLOAD --> ADOPT
    ADOPT --> ID2[TYPE + DESC + B3 ENTRY<br/>START, identity, COMPLETE]
    M -->|R D0-D2| RECLAIM[Prove all 8 payload sectors erased<br/>confirm CLEAR Dn]
    RECLAIM -->|any used sector, including retained F backup| REFUSE[BANK NOT ERASED<br/>no mutation]
    M -->|R D3| COMPACT[Require journal 00000000<br/>find erased scratch; confirm RESET J3]
    M -->|N D0-D3| RENAME[Validate COMPLETE record + new DESC<br/>find erased scratch; confirm RENAME Dn XXXXX]
    RECLAIM --> BACKUP[Verify original B3F backup<br/>in selected bank sector F]
    COMPACT --> BACKUP2[Verify original B3F backup<br/>in discovered erased sector]
    RENAME --> BACKUP3[Verify original B3F backup<br/>in discovered erased sector]
    BACKUP --> TOP[Rewrite and verify Bank 3 F<br/>then erase backup]
    BACKUP2 --> TOP2[Write D3 journal FCFFFFFF<br/>verify B3F; then erase backup]
    BACKUP3 --> TOP3[Change only selected DESC bytes<br/>verify B3F; then erase backup]
    M -->|E| ERASE[Erase selected sectors<br/>Bank 3 F protected]
    M -->|P| AP[Validated AP put<br/>Bank 0 $BF00]
    M -->|Q| Q[Jump Bank 3 $F000]
    MAP --> M
    ID --> M
    ID2 --> M
    REFUSE --> M
    TOP3 --> M
    ERASE --> M
    AP --> M
```

```text
$0200-$042A  runtime private mutation worker       555 bytes
$0A00-$19FF  staged flash sector                  4096 bytes
$7C00-$7D1A  maintenance state/tables              283 bytes allocated
$2000-$39B2  loaded program, worker, extensions     6579 bytes
```

The isolated STR8-iN/65 maintenance image used during WDC migration is a
separate `$2000-$3B15` / 6,934-byte artifact. It adds prompted defaults for
adoption and the scoped-search `F` byte, remains outside the canonical
manifest and migration ZIP, and is not required by the current migrator
because that migrator already publishes COMPLETE D0 `WDCM2`.

## Accepted v1.29 factory-board path

```mermaid
flowchart LR
    STOCK[Factory WDCMONv2<br/>B3] -->|verified eight-sector copy| B0[Retained WDCMONv2<br/>B0 + D0 WDCM2]
    STOCK -->|replace B3:F only| N[STR8-N 1.29<br/>B3:F]
    N -->|S| SHELL[STR8-N prompt]
    SHELL -->|J0| B0
    N -->|selector 0| B0
    B0 -->|physical RESET| N
```

The 2026-08-28 board capture proves the copy, candidate verification, STR8-N
launch, full retained EDU application startup, and final physical RESET.
The operator separately observed the expected CS0-CS3 chase.

## Accepted v1.21 board path

> [!NOTE]
> Archived v1.21 acceptance topology. It is retained as hardware evidence, not
> as a current v1.32 operating procedure or memory map.

```mermaid
flowchart LR
    TOP[Guarded v1.21 top updater] -->|verified B1:F backup| B3F[B3:F programmed and verified]
    B3F --> S[STR8-N 1.21]
    PAYLOAD[R-YORS 1303 8-E S19] -->|six sectors + final commit| B3[R-YORS in Bank 3]
    S --> B3
    B3 -->|intentional physical RESET| COLD[STR8-N 1.21 cold path<br/>HIMON 1303]
    COLD --> BM[Bank Maintenance map<br/>no mutation]
    BM -->|Q, then J3| SYN[Synthetic RESET-vector handoff]
    SYN --> COLD
    BM -->|C copy; cancel identity| B2P[B2 payload present<br/>D2 erased]
    B2P -->|D ADOPT B2| D2[D2 COMPLETE]
    D2 -->|J2| FACTORY[Factory onboard firmware]
    FACTORY -->|physical RESET| COLD
    BM -->|U verified backup| B1F[Retained B1:F recovery backup]
    B1F -->|E B1 8-D| B1HOLD[B1 E E E E E E W B<br/>J1 prohibited]
    B1HOLD -->|R D1| GUARD[BANK NOT ERASED<br/>backup preserved]
```

This complete path is board-accepted. The one failed intermediate `8-E`
transfer stopped before `COMMIT`; a clean retry completed, preserving the
fail-closed transaction boundary. The 2026-08-18 continuation adds the
copy-cancel-adopt-`J2` path and the retained-B1:F reclaim refusal shown above.

## Supported interfaces

```mermaid
flowchart LR
    CALLER[RAM or compatible payload] --> R[$F009 SR/02<br/>parse one S19 record]
    CALLER --> B[$F010<br/>select bank]
    CALLER --> Q[$F006 ABI_QUERY<br/>version and capabilities]
    CALLER --> I[$F003 CONSOLE_INIT<br/>restore raw console]
    CALLER --> CI[$F013 CHARIN<br/>blocking raw input]
    CALLER --> CO[$F019 CHAROUT<br/>blocking raw output]
    CALLER --> CR[$F03E CHAR_READY<br/>non-consuming poll]
    R --> DESC[$7E95-$7EA8<br/>request/result]
    R --> DATA[$7B00-$7BFB<br/>decoded data]
    B --> RAM[$0203 RAM entry<br/>can return after switch]
```
