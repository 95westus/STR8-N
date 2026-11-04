# BANK MAINT 2.4 above Foundation

The BASE1 port supplies the familiar BM> workflow on both SXB CPU profiles.
Foundation remains STR8N-F0.3.0 g1 / BASE1 / PR05. BANK MAINT is a separate
RAM application stored at B1:8-A; it does not extend or replace golden F.

```text
REC> B
B3> R MAINT
STR8-N BANK MAINT 2.4 / BASE1 PR05 g1
BM> ?
```

`R MAINT` / `RESTORE MAINT` opens BANK MAINT. Bare `MAINT` opens the
storage/EDU workbench. `R FLASH` keeps the existing FLASH/CONFIG tool;
`R CLOCK` opens the full CLOCK application. These are reserved native names,
independent of the selected data bank. `Q` returns quietly to the monitor.

## Commands

Numbers are hexadecimal. For source/destination, R means RAM and0-3 means
flash bank. RAM copy/compare workspace is $0200-$1FFF. Loading the app borrows
$2000-$66FF; Q restores ZP and the monitor session, not a saved application
RAM image. The installation trials restore the complete owner RAM separately.

| Command | Function |
| --- | --- |
| NAME | Show the saved board name |
| NAME text / NAME CLEAR | Append a board name or clear it; exact YES confirmation |
| M1 / M2 / M3 | Grid / ranges / tracked wear |
| E bank sector[-sector] | Erase a sector or sector range after Y confirmation |
| C src start-end dst start | Copy RAM or flash; overlapping RAM uses memmove ordering |
| V src start-end dst start | Compare; report MATCH or first differing destination |
| R src start-end | Read up to4096 bytes into the independent editor |
| D [offset[-end]] | Display editor bytes |
| P offset byte... | Patch editor bytes |
| F offset[-end] byte | Fill part of the editor |
| N length byte | Create an editor image of length1-$1000 |
| K | CRC16-CCITT-FALSE of the current editor length |
| W dst start | Write editor and verify, after Y confirmation |
| T / TABLE [bank\|first-last] | Discover stored flash records and native app rows |
| VERSION | Monitor/Foundation identity and BANK MAINT version |
| BOOT | Inspect saved default, enables and entries |
| BOOT ? | Existing CONFIG grammar for explicit boot-policy operations |
| J bank | Deliberate enabled opaque-bank boot; J3 enters Foundation startup |
| Q | Quiet return to Bx> |

Raw writes protect this app at B1:8-A, all B2 utilities and all B3 sectors.
The separate NAME and BOOT paths use their admitted metadata/journal writers.
Copy/editor flash writes preserve bytes outside their destination range and
use the existing worker's accounted erase/program/verify path. A failed
operation stops; completed earlier sectors remain. Ctrl-C requests cancellation
between safe operation boundaries; ESC also cancels current input. Neither
confirmations nor writes are automatic.

## Examples

Inspect the catalogue and current boot settings:

```text
BM> TABLE
B1:8000 2000-42FC 22FD C MAINT
B1:B000 2000-4FE1 2FE2 C CLOCK
B2:B000 2000-4FD4 2FD5 C CLOCK
B2:E000 2000-3A28 1A29 C FLASH
BM> BOOT
BM> NAME
```

The B1 CLOCK row is a retained legacy record, not the current R CLOCK route.
`C` means committed SR01 or a checked, sealed native RP image. SR01 has no
payload CRC; its row does not establish compatible executable code. `?` marks
a pending record. T scans record extents without searching inside payloads.

Read a sector and edit its RAM buffer without changing flash:

```text
BM> R 0 9000-9FFF
BM> D 0-3F
BM> P 10 12 34
BM> F 20-2F FF
BM> K
```

For a chosen writable destination, `W 0 9000` displays the plan and requires
`Y` to write. `E 0 9` erases that sector after the same confirmation. These
are real owner operations and replace the chosen bytes. The acceptance fixture
at B0:9 was temporary and is restored; it is not designated permanent scratch.

Create/copy/compare a short RAM pattern:

```text
BM> N 10 A5
BM> W R 1300
WRITE? TYPE Y> Y
VERIFIED
BM> C R 1300-130F R 1400
WRITE? TYPE Y> Y
VERIFIED
BM> V R 1300-130F R 1400
MATCH
```

To deliberately configure a separately installed opaque image, the existing
grammar is `BOOT B 0 8000` to enable B0/entry$8000 and `BOOT C 0` to save B0
as default. These commands immediately append boot records; they are not
executed by the examples or acceptance trial. `BOOT C B` saves MON B again.
Use BOOT prefix here because unprefixed C is BM's copy command.

Read-only BATCH example:

```text
B3> BATCH R MAINT;N 10 A5;K;Q
```

The app consumes queued lines through the common BATCH reader and returns
to the monitor. Destructive confirmations still require live input. J/reset
is refused inside BATCH.

## Boundaries

NAME is board naming. The older X named flash/PROGRAM transfer has not been
ported; the current workbench STORE/TABLE/RESTORE PROGRAM workflow remains
available separately. No per-sector naming format, factory restoration or
legacy binary-compatibility extension was added. ASM/DBG remain separate work.

See the [reviewed installation scope](BANK_MAINT_2512_2609_SCOPE.md) for the
specific archived records, sector allocations and erase/history accounting.
This development installation does not change published Foundation downloads.
