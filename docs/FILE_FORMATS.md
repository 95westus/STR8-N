# STR8-N files and transfer formats

This guide applies to frozen **F**, optional **MON**, **UTIL** and **DEV**,
including the PC tools that prepare, send, capture and verify their files.
See the [component/source/release guide](COMPONENT_GUIDE.md) and
[qualification scope](QUALIFICATION_SCOPE.md).

## Choose by content and destination

| File or artifact | Meaning | Supported route |
| --- | --- | --- |
| F `.bin` | Exactly 4096 bytes of Foundation; no load-address wrapper | Explicit programmer/migration procedure for B3:$F000–$FFFF; never recovery raw `L` |
| Self-contained RAM `.bin` | Contiguous executable bytes linked for the documented load/entry address | F `REC> L` only for packets starting at $0200 and fitting $0200–$64FF |
| MON/AP/02/sector `.bin` | Flash component, envelope, service or data sector; may include a header | Install at the manifest's bank/address with the matching installer; never assume the header is an entry point |
| Owner memory `.bin` | Raw flash, SPI SRAM, EEPROM, CPU RAM or zero-page bytes | UTIL MEMORY `load`/`offload` or matching region backup/restore; not executable by implication |
| `.s19` / `.srec` | ASCII S-records carrying addresses, data and per-record checksums | Current Terminal RAM S19 route accepts S0/S1/S9; the on-board MON loader checks records before writing |
| `.s28`, `.s37`, `.s29` or another S-record suffix | A filename convention, not proof of supported record types or CPU mode | Inspect the actual records. Current Terminal accepts only `.s19`/`.srec`; S2/S3/S7/S8 records are unsupported by its RAM path and the current on-board loader |
| OIP1 `header.bin` / `payload.bin` | Protocol frame and a separate 4096-byte replacement sector | Send the header at `SEND OIP1 HEADER`, then payload only at `SEND 4096` |
| `.json`, `.map`, source, ZIP | Manifest/receipt, assembler symbols, source or package | Read/inspect/extract on the PC; not a board executable |

A `.bin` contains no universal address information. A backup's `flash.bin`
contains all four 32 KiB banks; it is not the 4 KiB F image. MEMORY's serial
restore can replace 124 KiB only when the protected F bytes already match.
See [memory coverage and exclusions](MEMORY_UTILITY.md).

## Raw RAM BIN: F and Terminal

For a named kit, F5/F6/F7/F8 resolve MAP/CONFIG/OPAQUE/DEMO using
`preset-assets.json`. F2 selects another self-contained RAM packet. At an
observed `REC>`, F4 sends `L`, waits for `SEND BIN`, then sends the exact file
bytes. Alternatively enter `L` yourself and use F3 at `SEND BIN`.

The packet must start at $0200 and contain 1–25344 bytes. F runs it after the
nominal three-second input-idle interval. Raw `L` has no declared length,
transfer checksum or independent readback. A leading Ctrl-C cancels before the
first payload byte; subsequent Ctrl-C bytes are ordinary binary data. An
interrupted transfer can execute a partial program after idle.

Use the matching manifest's size and SHA-256, then check the expected prompt.
Never send F, a flash-sector image, AP/02 image, text S-record, backup dump or
OIP1 header as a raw executable. Do not add CR/LF or decode binary as text.
`Q`, `QUIT` or returning to MON does not automatically restore borrowed RAM.

## RAM S-record: MON and Terminal

At MON, enter `S19` and wait for:

```text
SEND S19 (S0/S1/S9); Ctrl-C cancels
```

Shift+F2 chooses an ASCII `.s19`/`.srec` file; Shift+F3 sends it at that exact
RAM-loader prompt. The current PC validator checks the entire file first,
including counts/checksums, at least one S1 data record and a final S9.
S1 destinations must fit $0200–$66FF. The on-board loader also checks each
record before committing it. S9 reports an entry address; it does not run it.
Inspect the result and entry before a deliberate `G address`.
The contracts are implemented in the
[PC validator](https://github.com/95westus/STR8-N/blob/main/tools/console_core.py)
and [on-board loader](https://github.com/95westus/STR8-N/blob/main/monitors/native/s19-loader.asm).

The actual record types determine compatibility. A file named `.s29` is not
accepted by this Terminal route. Renaming S2/S3 records to `.s19` does not
convert their addresses; renaming any S-record to `.bin` does not convert text
to machine bytes. Re-export or convert with a tool that validates record types,
address range, gaps and entry point, then check against the target manifest.
No generic S-record converter or wider-address loader is added by this guide.

DEV ASM's `S19` command exports address-bearing text. If `ORG` differs from its
physical $0200 output buffer, load the exported records at the intended origin
before executing. This is distinct from copying raw bytes to a chosen address.
See the [DEV manual](DEVELOPER_MANUAL.md).

Dense flash S19 belongs to FLASH's separate complete-sector protocol. The
Terminal RAM S19 shortcut does not perform flash transfer. WDC migration uses
its own matched engine/host procedure; a generated `migrator.s19` is not
automatically interchangeable with MON RAM input or F raw `L`.

## PC backup, restore, load and offload

UTIL MEMORY saves raw region files plus a manifest of region, byte count,
device identity and SHA-256. Keep the complete backup directory for `inspect`,
`verify`, `plan` and `restore`. `load` reads raw bytes at a region offset;
`offload` writes a raw region image to the PC. Neither interprets S-record text
or infers a flash bank from a filename. Use the [MEMORY guide](MEMORY_UTILITY.md)
for exact region sizes, protected F checks, agent selection and write options.

Owner captures, profiles, receipts and generated BUILD/output files stay local.
Keep LICENSE and applicable third-party notices with distributed components.
Published release assets retain their original names and bytes; the current
canonical names describe newly built named kits.
