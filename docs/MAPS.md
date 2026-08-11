# STR8-N v1.1 Maps and Diagrams

These diagrams describe the current v1.1 implementation.

## Ownership

```mermaid
flowchart TB
    RESET[Physical RESET] --> S[STR8-N<br/>Bank 3 $F000-$FFFF]
    S -->|J0| B0[Bank 0 guest]
    S -->|J1| B1[Bank 1 guest]
    S -->|J2| B2[Bank 2 guest]
    S -->|H| B3[Bank 3 HIMON<br/>$C000]
    S -->|J3| R3[Bank 3 RESET vector<br/>normally STR8-N again]
    S -->|I| W[RAM worker<br/>$0200-$0453]
    W --> FLASH[Selected flash range]
    S -->|L| RAM[Recovery RAM program<br/>$2000-$7AFF, then S9]
    RAM -->|bank-maint S19| BM[Self-contained Bank Maintenance<br/>map/copy/erase/AP put]
    BM -->|private RAM worker| FLASH2[Banked flash<br/>Bank 3 F protected]
    BM -->|Q| S
    B3 -->|L or L G| RAM2[HIMON RAM program]
```

## Build and artifact flow

```text
BUILD/
|-- v1.1/
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
    SRC --> WORKER[596-byte worker evidence S19]
    BM_SRC[bank-maint ASM] --> BM[RAM bank-maint S19]
    TOP --> MANIFEST[verified manifest]
    WORKER --> MANIFEST
    BM --> MANIFEST
    RY[R-YORS 28K ASM+HIMON S19] --> FULL[32K Bank-0/1/2 8-F S19]
    TOP --> FULL
    TOP --> PROGRAMMER[external programmer<br/>physical $1F000-$1FFFF]
    BM -->|STR8-N L| RAM_TOOL[temporary maintenance session]
    FULL -->|STR8-N I| GUEST[enrolled Bank 0, 1, or 2]
```

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
    R[Physical RESET<br/>forces Bank 3] --> A[Six one-second WAIT pulses<br/>keys ignored]
    A --> P[Flush input<br/>STR8-N 1.1]
    P --> Q{Six live selector dots<br/>0-2 H S}
    Q -->|0,1,2| C{Directory COMPLETE?}
    C -->|no| F[Refuse handoff]
    C -->|yes| J[Select bank and jump through RESET vector]
    Q -->|H or timeout| M{Compatible HIMON marker?}
    M -->|H: warm; timeout: cold| H[HIMON at $C000]
    M -->|no| S[STR8-N prompt]
    Q -->|S| S
    S -->|J0-J3| J
    S -->|I| I[Installer]
    S -->|L| L[Load RAM $2000-$7AFF<br/>and execute S9]
```

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
    Exhausted --> Erased: external programmer refresh
```

`J0`-`J2` accept only `Complete`. Bank Maintenance `C` accepts only `Erased`
destination rows; it does not overwrite or repair an existing identity.

## Protected 4K top sector

```text
$FFFF  +------------------------------+
       | hardware vectors       6 B   |
$FFF9  +------------------------------+
       | configuration         10 B   |
$FFEF  +------------------------------+
       | bank directory        64 B   |
$FFAF  +------------------------------+
       | stored worker        596 B   |
$FD5B  +------------------------------+
       | free margin            8 B   |
$FD53  +------------------------------+
       | resident code/data  3412 B   |
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
    CHOICE -->|monitor load/load-go| HL[HIMON L or L G]
    HL --> RP
```

## Recovery RAM load

```mermaid
flowchart TD
    C[STR8-N L] --> P[Receive and validate S0/S1/S9]
    P -->|valid S1| R{Whole record inside<br/>$2000-$7AFF?}
    R -->|yes| M[Copy record to RAM]
    R -->|no| F[Return to prompt; do not execute]
    M --> P
    P -->|valid S9 after data| E{S9 inside<br/>$2000-$7AFF?}
    E -->|no| F
    E -->|yes| G[SEI, CLD, X/SP=$FF,<br/>jump to S9]
```

## Transient RAM during install

```text
$1FFF  +------------------------------+
       | update state $1FE9-$1FFF     |
$1FE8  +------------------------------+
       | other RAM                    |
$19FF  +------------------------------+
       | 4K sector tray $0A00-$19FF  |
$09FF  +------------------------------+
       | other RAM                    |
$0453  +------------------------------+
       | worker $0200-$0453           |
$01FF  +------------------------------+
       | stack                        |
$00FF  +------------------------------+
       | state and ZP scratch         |
$0000  +------------------------------+
```

## RAM capacity by operating path

```text
Board RAM below I/O                         32,512 bytes  $0000-$7EFF
STR8-N L accepted window                    23,296 bytes  $2000-$7AFF
I named transient/service areas              5,015 bytes  excluding L flag
Fixed delay and IVI cells                        13 bytes
Maximum hardware stack                         256 bytes  dynamic
Outside named I/fixed areas                  27,484 bytes  before stack use
R-YORS normal application convention         18,694 bytes  monitor-dependent
Bank-maint loaded image                       4,651 bytes  $2000-$322A
```

```mermaid
flowchart LR
    TOTAL[32,512 B board RAM] --> LOW[8,192 B below $2000]
    TOTAL --> LWIN[23,296 B accepted by STR8-N L]
    TOTAL --> HIGH[1,024 B $7B00-$7EFF<br/>parser, IVI, I/O-adjacent]
    LWIN --> BMIMG[4,651 B bank-maint image]
    LWIN --> LOTHER[18,645 B remaining in L window]
```

The numbers describe STR8-N boundaries, not a promise that HIMON, ASM, or an
arbitrary guest leaves every other byte unused.

## Bank-maintenance RAM tool

```mermaid
flowchart TD
    L[STR8-N L] --> S[S19 loads $2000-$322A<br/>S9=$2000]
    S --> B[Copy private worker<br/>$3000-$322A to $0200-$042A]
    B --> M{Command}
    M -->|M| MAP[Stage and inspect sectors<br/>no flash mutation]
    M -->|C| COPY[Require empty directory row<br/>copy and verify full bank]
    COPY --> ID[TYPE + five-character DESC<br/>START, identity, COMPLETE]
    M -->|E| ERASE[Erase selected sectors<br/>Bank 3 F protected]
    M -->|P| AP[Validated AP put<br/>Bank 0 $BF00]
    M -->|Q| Q[Jump Bank 3 $F000]
    MAP --> M
    ID --> M
    ERASE --> M
    AP --> M
```

```text
$0200-$042A  runtime private mutation worker       555 bytes
$0A00-$19FF  staged flash sector                  4096 bytes
$1B00-$1DDA  maintenance state                     731 bytes
$2000-$322A  loaded program, padding, stored worker 4651 bytes
```

## Supported interfaces

```mermaid
flowchart LR
    CALLER[RAM or compatible payload] --> R[$F009 SR/02<br/>parse one S19 record]
    CALLER --> B[$F010<br/>select bank]
    R --> DESC[$7E95-$7EA8<br/>request/result]
    R --> DATA[$7B00-$7BFB<br/>decoded data]
    B --> RAM[$0203 RAM entry<br/>can return after switch]
    OLD1[$F003 retired] -.-> STOP[Do not call]
    OLD2[$F006 retired] -.-> STOP
```
