# Board name and RMP/1 proposal

Status: proposed 2026-09-16. This document does not assign the bytes, change
the canonical image, implement a maintenance command, or claim board proof.

Companion notes: [R-YORS integration](../../R-YORS/DOC/GUIDES/PLANNING/BOARD_NAME_RMP1_PROPOSAL.md),
[R-YORS II integration](../../R-YORS-II/DOC/BOARD_NAME_RMP1_PROPOSAL.md), and
[RTERM wire extension](../../RTERM/docs/BOARD_NAME_EXTENSION_PROPOSAL.md).

## Proposed persistent field

Reserve the remaining Bank-3 top-sector configuration bytes as one board
label:

```text
$FFF3-$FFF9  STR8_CONFIG_BOARD_NAME[7]
```

The field is a physical-board label, not a DNS hostname, authentication
identity, authorization token, or unique hardware identifier. Seven `$FF`
bytes mean unnamed. A configured value is exactly seven uppercase ASCII bytes;
shorter labels are right-padded with spaces. Accepted characters are `A-Z`,
`0-9`, hyphen, and space. Readers must treat an all-`$FF` field or any invalid
byte sequence as unnamed.

Examples are `RYORS01`, `SXB3-1 `, and `LAB6502`.

The canonical STR8-N image continues to emit `$FF` at `$FFF3-$FFF9` until the
proposal is accepted and implemented. Assignment consumes the complete
remaining configuration reserve and therefore requires a public-contract,
manifest, layout-check, updater, documentation, and release review.

## Mutation contract

The name lives in Bank 3 sector F. It cannot be safely changed as an isolated
flash poke when any requested bit changes from zero to one. A future structured
maintenance operation must:

1. validate the requested label and current configuration;
2. stage all 4096 bytes of B3:F in RAM;
3. retain and exactly verify the original in the configured protected backup
   sector;
4. change only staged `$FFF3-$FFF9`;
5. erase, rewrite, and byte-verify the complete B3:F sector from RAM; and
6. require reset after success and report the sector as suspect after an
   interrupted or failed rewrite.

The operation should extend the guarded configuration editor used for the
`$FFF2` search-policy field. It must not create a general resident flash-poke
primitive.

## Consumer and RMP/1 boundary

Boot or supervisory code should read and validate the name while Bank 3 is
selected, then cache the seven bytes in RAM before handing execution to another
bank. An RMP/1 endpoint must use the cached value; it must not switch flash
banks merely to answer a protocol handshake.

The companion RTERM proposal adds an optional target-name suffix to CONTROL
ACCEPT. The board label is correlation and display data only. It grants no
console authority and cannot authorize flash mutation.

## Acceptance gates

Acceptance requires coordinated STR8-N, R-YORS, R-YORS II, and RTERM contract
updates; source-derived constants and manifests; invalid/erased-name tests;
old/new RMP/1 interoperability tests; interrupted full-sector rewrite tests;
exact post-write B3:F and four-bank readback; reset recovery; and retained
hardware evidence.
