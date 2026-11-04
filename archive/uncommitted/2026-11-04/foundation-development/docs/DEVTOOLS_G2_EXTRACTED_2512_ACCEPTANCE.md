# Extracted developer kit: 2512 RAM acceptance

**Passed November 2, 2026, on 2512/65C02.** Accepted archive:
`BUILD/devtools-g2-candidate2-20261102-r2/STR8N-DEVTOOLS-g2-candidate2.zip`.
SHA-256: `7cdf5b00322426ad00a8e456bc236d34294dfe8a7f876732113c3ac0362e69d2`.
This closes the extracted-kit RAM acceptance scope. It does not publish a
release or qualify the developer tools on816 emulation/native operation.

The trial freshly extracted the archive and verified its complete file set,
hashes and terminal help. All application transfers used the extracted
console0.1.2 transfer backend and exact extracted BINs, not replacement
workspace payloads. Workspace escrow/readback helpers preserved owner memory;
they were not claimed as distributable kit components.

Seven recorded groups passed:

1. Fresh owner escrow, all four bank hashes and exact installed ASM/DBG/SF
   pairing with the extracted AP/02 images.
2. Extracted console Ctrl-C cancellation at SEND BIN, before any payload.
3. Exact ASM-RAM.bin load; numbered HELLO source, ASM/LST/SYMS/DUMP/S19,
   physical output readback, execution and HOLD return.
4. Exact DBG-RAM.bin load; seed stop, registers/disassembly, S, public PUTC
   N step-over, C and HOLD return.
5. A second exact DBG load; BC, Ctrl-C and X with original hooks/bytes.
6. Installed R ASM and R DBG front doors still launch; DBG start cancels.
7. Final independent readback: all four flash banks exactly unchanged.

Three complete BIN transfers were recorded: ASM once, DBG twice. The raw
loader supplies no CRC acknowledgement; the trial separately verified the
assembled output bytes and exercised the loaded code. It does not label
the terminal's host-complete event as a full RAM-image readback.

## Corrected example, unchanged firmware

Candidate1's manual/example used ORG1800 and incorrectly assumed the output
already occupied physical1800. This assembler stages output at0200; LST and
DUMP show logical addresses. The first trial stopped at its physical-readback
assertion before running the example and restored owner RAM/ZP/cache/hooks.

Candidate2 changes the example to ORG0200 and explains staging versus origin,
plus the F2 choose/F3 send/F4 recovery-load actions. Its firmware payloads and
terminal files are byte-for-byte identical to candidate1. No firmware was
rebuilt. The repeat verified the eight bytes at0200 and ran them successfully.
For a different origin, deliberately load S19 or copy the staged bytes before
executing there. Candidate1 and its failed trial remain archived.

## Preservation and limits

Golden F, MON A/B, all images, settings/metadata and every boot/wear record
remain exact. The final readbacks also match the bank captures preceding
the first trial. There were zero flash/journal, SPI-data/WORKSPACE or
RTC-setting writes, resets or power cuts. Source SAVE was not exercised.
No other board was accessed and published downloads were unchanged.

The shared RTC-priority lease/window was observed. Fresh owner RAM0200-66FF,
ZP00-DF, full6B00-77FF cache and BRK/HOLD hooks were restored and verified.
Final state REC>, COM4 released, RTC eligible.

This was console-backend/file acceptance; GUI physical keys were not repeated.
The previous physical-key receipt remains separate. Persistent AS/1/SF/1
writes retain their earlier2512 qualification; no new storage fixture was
used here. The later [2609 emulation RAM gate](DEVTOOLS_2609_EMULATION_RAM_ACCEPTANCE.md)
also passed; its installation/storage scopes remain separate. Native816 is
outside this increment. A complete extracted source-only rebuild is not claimed.

The ZIP is kept exact after testing. Its internal pre-test qualification
metadata is superseded for this scope by the adjacent `ACCEPTANCE-2512.json`,
which binds this accepted hash. It remains a local developer candidate.

Workspace evidence:

- `output/qualification/2512-devtools-g2-extracted-RAM-20261102-r1/report.json`
- `output/qualification/2512-devtools-g2-extracted-RAM-20261102-r2/report.json`
- `output/qualification/2512-devtools-g2-extracted-RAM-20261102-r2/completion.json`
- `BUILD/devtools-g2-candidate2-20261102-r2/ACCEPTANCE-2512.json`

Private owner escrow, bank captures and wire traces stay outside the kit.
