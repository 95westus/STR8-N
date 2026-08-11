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
    A[Choose bank and exact sector range] --> B[Create or match directory identity]
    B --> D[Copy and verify embedded worker in RAM]
    D --> E[Receive first valid dense S1]
    E --> C[Write START journal bit]
    C --> G[Stream, program and verify<br/>each completed non-final sector]
    G --> F{Exact extent, checksum,<br/>S9 and policy valid?}
    F -->|no| X[FAIL / bank remains incomplete]
    F -->|yes| H{COMMIT? Y}
    H -->|no or interrupted| X
    H -->|yes| K[Program and verify final sector]
    K --> L[Write COMPLETE journal bit]
    L --> O[OK / bank may boot]
```

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
