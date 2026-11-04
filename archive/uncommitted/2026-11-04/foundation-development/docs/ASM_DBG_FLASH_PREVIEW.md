# ASM/DBG flash preview on 2512

Installed and tested on2512/65C02 on November2,2026. The five-sector
installation, installed workflows and final owner/cache restoration passed.
This separate developer increment uses MON A/B g10 above the unchanged
Foundation 0.3.0 g1 / BASE1 / PR05. It is not in Candidate3 or the published
downloads. The installation receipt is recorded separately from the earlier
[RAM acceptance](ASM_DBG_2512_RAM_ACCEPTANCE.md) and
[AS/1 PROGRAM persistence acceptance](ASM_AS1_PROGRAM_ACCEPTANCE.md).

Later updates: the SF/1 source provider and
[DBG g2 installed acceptance](DBG_G2_2512_INSTALLED_ACCEPTANCE.md) have also
passed on2512. The original five-sector receipt below remains historical;
DBG g2 used its separate approved two-erase scope.

## Launch and return

From recovery, enter `B` to start the saved MON B. At `B3>`:

```text
APPS
R ASM
```

`APP ASM` is also supported. The editor uses numbered lines. For example:

```text
10 ; Write a marker, then return to the monitor.
20 ORG $0200
30 LDA #$42
40 STA $1900
50 JMP $7E67
60 END
ASM
LST
DUMP
QUIT
```

`ASM` emits eight bytes at $0200. `QUIT` returns to the monitor without
executing them. Enter `G 0200` to run them and return through public HOLD.
`D 1900` then shows the marker $42.

To debug that same output:

```text
R DBG
0200
R
U 0200 3
S
S
C
```

The launch prompt requests a RAM start address from $0200 through $3FFF.
`Q` at that prompt cancels before installing hooks. A valid start stops
before executing its first instruction. In `DBG>`, `?` lists the commands:
registers `R`, disassembly `U`, step `S`, step-over `N`, continue `C`, dump
`D`, modify `M`, breakpoint `B`, clear breakpoints `BC`, and exit `X`.
Program HOLD and `X` remove patches and restore the borrowed BRK/HOLD hooks.
Use IRQ-masked 65C02 RAM programs within the declared target range.

`APP DBG` is an alternative launch command. These interactive apps do not
advertise returning BATCH support; BATCH admission refuses them.

## Source persistence and RAM ownership

Inside the assembler, `SAVE SRAM name` and `LOAD SRAM name` use AS/1 records
in formatted PROGRAM storage. Unsaved loads ask for confirmation. CRC-invalid
source is refused. Source saving stages a capsule over the output buffer,
so assemble again afterward before running output. PROGRAM capacity and a
free directory slot are required. WORKSPACE is not used.

The later [FLASH source increment](ASM_FLASH_SOURCE_INCREMENT.md) is installed
and accepted on2512: `SAVE FLASH name` proposes an exact blank-sector extent
and requires `YES`; `LOAD FLASH name` validates the complete source before
copying it. Saves do not erase or replace names. B0:9 currently provides one
free source sector, fitting one record with up to4056 packed-source bytes.
Use PROGRAM for more revisions; WORKSPACE is not used.

| Tool | RAM while active |
| --- | --- |
| ASM | Output $0200–$1FFF; source $2000–$37FF; symbols $3800–$3FFF; code $4000–$63B7; state $6500–$66FF |
| DBG g2 | Targets $0200–$3FFF; code $4000–$508A; tables $5F00–$6407; state/cache $7000–$744F |
| Launch | Temporary decoder $6800–$69FF, parameters/bridge $6700–$67FF; ASM reloads PROGRAM at $6B00–$77FF |
| FLASH source | Private paired provider $7000–$77FF; SRAM operations reload PROGRAM afterward |

These are RAM-staged apps. Starting them borrows those regions; interactive
launches do not preserve an arbitrary existing program occupying their code
buffers. The installation/qualification harness separately escrows and
restores the original owner RAM, ZP and provider cache. A later XIP layout
can recover more application RAM. No F ABI expansion is required here.

## Flash layout and acceptance evidence

ASM occupies B0:A/B; DBG occupies B0:C/D. B3:E adds `R ASM`/`R DBG` routing.
The old all-zero B0:A–D preimages were archived. B0:8/9/E/F and all B1/B2,
MON A/B, settings and F are preserved by the reviewed installation scope.
Five append-only wear records retain all 20 previous journal rows on chip;
no C/D erase or boot-policy change is required.
That initial installation is historical. The source increment subsequently
updated A–D and used DBG padding D800–DFFF for the private source provider;
no additional sector allocation was needed. Its B0:9 test is restored exactly,
and all25 preceding journal rows remain, now30 rows at sequence1187.

Workspace evidence paths:

- `output/qualification/2512-devtools-launcher-RAM-20261102-r1/report.json`
- `output/qualification/2512-devtools-flash-scope-20261102-r1/review-document.md`
- `output/qualification/2512-devtools-flash-installed-20261102-r1/report.json`
- `output/qualification/2512-devtools-flash-closeout-20261102-r1/completion.json`

The closeout receipt determines whether installation is complete. The current
scope qualifies 2512/65C02; it does not claim the developer tools are qualified
on 2609/65C816. The [broader g2 boundary/callback/register RAM checks](DBG_BROAD_2512_RAM.md)
and the [g2 installation/installed checks](DBG_G2_2512_INSTALLED_ACCEPTANCE.md)
now pass on2512. The [candidate2 extracted RAM trial](DEVTOOLS_G2_EXTRACTED_2512_ACCEPTANCE.md)
also passed. The later [2609 emulation RAM acceptance](DEVTOOLS_2609_EMULATION_RAM_ACCEPTANCE.md)
qualifies the common-subset RAM path, with no2609 flash installation.
The following [2609 installed acceptance](2609_DEVTOOLS_INSTALLED_ACCEPTANCE.md)
then passed under its separate six-erase approval, using CPU16 envelopes.
FLASH source storage now passes
on2512 within the source increment's recorded scope.

2609's separate requested default-monitor check found MON B g10 already saved.
It verified the saved binding and started MON B with owner RAM/ZP preserved,
without a flash/journal write. Its receipt is
`output/qualification/2609-default-MON-g10-20261102-r1/report.json`.
