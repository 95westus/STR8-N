# WDCMONv2 Migration Provenance And Redistribution Boundary

This note records where the migration kit came from and why it does not ship a
copy of WDCMONv2. It is a project policy and provenance record, not legal
advice. Copyright exceptions and the effect of a board or tool license depend
on jurisdiction and on the terms under which a particular owner received the
software.

## What The Project Authored

The two W65C02 RAM applications are STR8-N project code:

```text
tools/wdcmonv2/wdcmonv2str8n-archive-2000.asm
tools/wdcmonv2/wdcmonv2str8n-install-2000.asm
```

They were written for this migration from the board's documented memory and
I/O contract and from existing MIT-licensed STR8-N implementation patterns.
The main in-repository ancestors are:

```text
src/str8-worker.asm
tools/bank-maint/str8n-v1.23-bank-maint-2000.asm
tools/top-update/str8n-v1.23-top-update-2000.asm
```

Those sources supplied the project's already-tested RAM-worker, bank-select,
FT245R console, SST39 flash, verification, and recovery patterns. The archive
application is read-only. The installer contains the STR8-N candidate sector,
not a WDCMONv2 sector. Neither application calls, links, includes, disassembles,
or carries WDCMONv2 firmware.

The host bridge in `tools/wdcmonv2/start_wdcmonv2_ram.ps1` is also project
code. Its protocol contract was taken from the published WDCMON v2 user manual
and corroborated against the locally installed
`C:\Program Files\WDC\Tools\bin\wdc_interface.py`. That installed Python file
identifies itself as copyright 2017 ECNX Development under the MIT License. It
is not copied into this repository or migration package.

The flash command sequences and physical limits come from Microchip's
SST39SF010A data sheet. The resulting archive and installer S19 files contain
assembled STR8-N project code and, for the installer, the STR8-N top-sector
candidate. They do not contain WDCMONv2.

## What An Owner-Local Archive Is

When the RAM archive application reads a stock flash bank, the terminal can
store those bytes as BIN and can encode the same bytes as S19. BIN and S19 are
two representations of the same captured program. Converting WDCMONv2 bytes
to S19 does not remove WDC's copyright interest or make the program part of
STR8-N.

Under United States law, the copyright owner normally controls reproduction,
derivative preparation, and distribution. 17 U.S.C. section 117 also contains
a limited rule allowing the owner of a copy of a computer program to make an
essential-step or archival copy under its stated conditions. Whether a board
owner is the legal "owner of a copy," whether section 117 applies, what a WDC
license permits, and what another country permits are questions this project
cannot decide for the operator.

The conservative project rule is therefore:

```text
OWNER-LOCAL BIN/S19/RECEIPT       allowed by the tooling; keep private
PUBLIC WDCMONV2 BIN OR S19        do not publish without an express grant
KIT WITH WDCMONV2 BYTES           prohibited by release policy
KIT WITH OUR CODE AND NO WDC BYTES eligible for normal project release review
```

If WDC supplies written terms that expressly permit redistribution, a release
may follow those exact terms, notices, scope, and version limits. Silence or
the availability of a binary on a board is not treated as permission. An
operator should also avoid presenting an archive or tool as WDC-approved when
it is not.

No WDCMONv2 firmware redistribution grant was located in the public WDCMON
manual or the installed WDC tool tree during this review. The manual itself
says that its document copyright includes reproduction rights; that notice is
not a license to redistribute monitor firmware. Installed WDC example assembly
also carries restrictive, all-rights-reserved headers, but those example-file
headers do not establish the license of a different WDCMON image. The absence
of a located grant is not proof that none exists; it is the reason this project
does not ship the bytes. A source distribution, board-sale agreement, or
separate WDC license supplied to an operator must be reviewed on its own.

The same distinction applies if an operator possesses WDCMONv2 source rather
than dumping a board. Assembling that source into S19 changes its machine
representation; it does not transfer copyright or expand redistribution
rights. Output assembled solely from this project's source is different and
is reviewed under this repository's license plus any applicable assembler or
third-party terms.

## Release And Test Gates

The migration ZIP has an explicit allowlist and manifest flags declaring that
WDCMONv2 firmware and local bank archives are absent. Release review must also
scan the package for accidental owner captures, including:

```text
bank0.bin / bank3.bin
owner-generated WDCMONv2 S19
terminal captures containing dense firmware records
programmer full-device reads
receipts that embed rather than merely identify the captured bytes
```

Hashes, lengths, vector values, product names, and an operator's proof that a
local archive exists may be documented without publishing the archive bytes.
The board-test transcript should redact or omit dense S-record payloads.

## References Consulted

- WDC, *WDCMON User Manual Version 2.0*, for the documented monitor protocol.
- WDC W65C02SXB documentation, for the board memory and I/O map.
- Microchip, *SST39SF010A/SST39SF020A/SST39SF040 Data Sheet*, for product ID,
  byte programming, polling, and 4K sector erase.
- U.S. Copyright Office, *Copyright Basics* and 17 U.S.C. sections 106 and
  117, for the U.S. reproduction/distribution and computer-copy framework.
- U.S. Copyright Office, *Compendium of U.S. Copyright Office Practices*,
  sections 721.2-721.5, for source/object-code representations and derivative
  computer programs.
- The installed ECNX Development `wdc_interface.py`, MIT licensed, as a local
  corroborating implementation of the published binary-monitor framing.
