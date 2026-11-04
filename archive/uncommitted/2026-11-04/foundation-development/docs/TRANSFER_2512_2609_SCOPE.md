# S19 / large PROGRAM STORE installation review

Prepared November1,2026. **Owner approved;2512 passed,2609 owner-held.** F remains golden;
2205/2604, RTC settings/history and published downloads stay outside the scope.
No power cuts. This is a new write allowance beyond the completed15-erase
SRAM/WORK installation.

## Exact image scope

Four sector replacements per board: **B1:D, B2:9, B2:A and B3:E**.
Eight image erases total, eight append-only wear reservations, **zero C/D
erases and zero F writes**. Original target sectors and every old C/D row
are archived in the immutable private scope folder before execution.

B1:D adds the S19/STORE overlay in existing RP padding and updates its CRC;
the resident SRAM/WORK library bytes remain unchanged. B2:9/A replace only
the PROGRAM worker footprint9F00-ABFF; WB, bootstrap and STATUS bytes stay
exact. B3:E is the dispatcher that admits the new commands before WB loading.
MON A/B gD, their saved binding/default, masks/entries and unknown-wear flags
are unchanged. B0 and all other image sectors remain exact.

| Board | Reservations | Sequence | Existing rows retained | Rows after |
|---|---|---:|---:|---:|
|2512|D700-DA00|1116→1120|all23|27|
|2609|DA00-DD00|1072→1076|all26|30|

Tracked target erase counts, decimal:

|Board|B1:D|B2:9|B2:A|B3:E|
|---|---:|---:|---:|---:|
|2512|14→15|272→273|16→17|34→35|
|2609|18→19|265→266|16→17|48→49|

C/D/F totals stay2512=55/36/24 and2609=79/49/31. All current rows remain on
chip; no history rotation or generation-binding append is needed.

## Temporary PROGRAM qualification on2512

Freshly read and escrow slot4 at SPI00140-0017F and payload09800-0B7FF:
**8256 temporary bytes**, all restored and read back afterward. Admit only if
the primary/directory are valid, slot4 is uncommitted and those payload pages
remain unallocated; otherwise stop. Do not infer permission from erased/free
appearance alone. No format, mode-register write, reclaim or WORKSPACE write.

Use STORE's explicit9800 target for CPU4700-66FF, inspect TABLE, and RESTORE
load-only to verify the original source through the former WB/request area.
Do not run arbitrary owner RAM as code. Restore all temporary directory and
payload bytes exactly, then fresh owner RAM0200-66FF/ZP00-DF. No SPI mutation
on2609 is included; its installed admission/command/S19 checks are read-only.

Each unit yields to the RTC lease. Ports finish released at their original
monitor/recovery prompts. No reset is required by these software checks.

## STATUS regression correction already completed

The previous installation incorrectly treated8040-80FF and8240-82FF as free
padding. Both were restored from exact archived originals using1→0 programming
only:384 bytes per board, **no erases and no journal changes**. Rich VERSION,
board/CPU/EDU status, native TIME and the latest journal row passed afterward.
All four STATUS extents are now explicit packaging constraints; AC00-AFFF and
FA50-FFF9 are retained too. This correction is not part of the eight erases.

## Excluded/open

This scope closes the integrated RAM S19/PROGRAM STORE front doors only after
their positive installed checks pass. It does **not** claim legacy dense S19
flash-stream `I`, large flash STORE staging, a complete extracted shipping kit,
or live factory restoration. Factory execution intentionally removes F and
needs a separately reviewed target/recovery route.

Exact private plans/artifacts:
`output/qualification/TRANSFER-scope-20261101-r2/{2512,2609}/plan.json` and
`BUILD/transfer-final-g1-r2/manifest.json`. No write driver may expand these
targets, retry an erase automatically or consume an unreviewed rotation.

## Execution checkpoint

2512 completed exactly four image erases and four reservations, retaining
all23 old rows. The installed S19 command passed Ctrl-C and checked loading
through66FF. Actual8192-byte PROGRAM Store/Table/load-only Restore passed;
all8256 temporary SPI bytes, fresh owner RAM and ZP were restored and read
back. F, MON A/B, boot choices/binding, RTC settings and WORKSPACE stayed
unchanged. C/D were not erased. The private closeout independently rechecked
the target hashes, complete B3, old history, frozen sources, payload/header
CRCs and final SPI restoration frames:
`output/qualification/TRANSFER-checkpoint-20261101-r1/report.json`.

2609 has not received this installation. A newer owner hold from the RTC
work excludes COM8 access, reset and recovery retries until new explicit
owner instructions. Its four erases remain unused; the table above describes
the approved plan, not an executed2609 result. No further write is implied
by the closeout or by the RAM-only saved-EDU development.
