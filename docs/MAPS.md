# STR8-N V2 Maps and Diagrams

These diagrams describe the current V2 implementation.

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
    B3 -->|L or L G| RAM[Temporary RAM program]
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
    R[Physical RESET<br/>forces Bank 3] --> P[STR8-N at $F000]
    P --> Q{0-2 H S}
    Q -->|0,1,2| C{Directory COMPLETE?}
    C -->|no| F[Refuse handoff]
    C -->|yes| J[Select bank and jump through RESET vector]
    Q -->|H or timeout| M{Compatible HIMON marker?}
    M -->|yes| H[Warm HIMON at $C000]
    M -->|no| S[STR8-N prompt]
    Q -->|S| S
    S -->|J0-J3| J
    S -->|I| I[Installer]
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
       | free margin           38 B   |
$FD35  +------------------------------+
       | resident code       3382 B   |
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
writes flash. HIMON `L`/`L G` owns RAM loading.

## Flash install versus RAM load

```mermaid
flowchart LR
    S19[S19 file] --> CHOICE{What should survive reset?}
    CHOICE -->|lasting image| I[STR8-N I]
    I --> FW[Selected flash sectors]
    CHOICE -->|temporary program| L[HIMON L or L G]
    L --> RP[STR8-N F009 parser]
    RP --> RM[HIMON copies valid data to RAM]
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
