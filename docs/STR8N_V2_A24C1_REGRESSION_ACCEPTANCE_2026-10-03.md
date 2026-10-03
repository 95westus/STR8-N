# a24c1 two-board practical regression acceptance

Date: 2026-10-03. Board 2205: W65C02SXB, COM3, FTDI A10MPUPNA.
Board 2609: W65C816SXB, COM8, FTDI A10MPQXCA. This completes beta
checklist item 3 for the practical tests listed below, following the
[migration/reset](STR8N_V2_A24C1_TWO_BOARD_ACCEPTANCE_2026-10-03.md) and
[cold-start/configuration](STR8N_V2_A24C1_COLD_CONFIG_ACCEPTANCE_2026-10-03.md) sessions.

## Physical-board results

| Check | 2205 | 2609 |
| --- | --- | --- |
| B0-B3 selection and complete bank dumps | PASS | PASS |
| M/D RAM edit, readback and original scratch restoration | PASS | PASS |
| Malformed hex, protected RAM/flash/I/O, reversed range, unaligned install and sector-span rejection | PASS | PASS |
| L: probe/utility RAM loads independently read back byte for byte | PASS | PASS |
| G: execution of loaded probes and maintenance | PASS | PASS |
| Cross-bank RAM ABI: PUTC bank preservation, descriptor, CAPS_QUERY, BOARD_QUERY, HOLD | PASS | PASS |
| BRK and physical VIA1 timer IRQ: A/X/Y, stack, status and RTI | PASS | PASS |
| Physical NMI: A/X/Y, stack and RTI | PASS on repeat | PASS |
| Native BRK/physical NMI: A/X/Y, native frame, PBR and RTI | Not applicable | PASS |
| F direct programming and erase/rewrite with complete-sector readback | PASS | PASS |
| I dense S19 scratch-sector install and all-FF restore with complete readback | PASS | PASS |
| Temporary a24c1 in B1:F; J1 boot and J3 return | PASS | PASS |
| Maintenance map and editor N/P/F/D/R/W | PASS | PASS |
| CRC known answer: 123456789 -> 29B1 | PASS | PASS |
| Invalid editor commands preserve buffer CRC | PASS | PASS |
| RAM->RAM, RAM->flash, flash->RAM and flash->flash copies and V comparisons | PASS | PASS |
| Partial copy across B1:8/9 boundary | PASS | PASS |
| Deliberate compare mismatch reports destination 1400 | PASS | PASS |
| Buffered flash edit/write and sector-range erase | PASS | PASS |
| S8/S9 utility archive, readback CRCs 074B/78BD and cleanup | PASS | PASS |
| Invalid bank/RAM-range rejection and canceled writes, including second B3:F gate | PASS | PASS |
| Q return to original monitor | PASS | PASS |
| Final complete four-bank byte equality against starting images | PASS | PASS |

## Scratch plan and preservation

Both boards began with retained stock WDC firmware in B0, wholly erased
B1/B2, and a24c1 in B3:F with configuration `C 00 03 F007 40`.
All four complete banks were saved before temporary writes. Monitor flash
tests used B1:8. Maintenance used B1:8-9 and B2:8-9. The handoff test
installed the exact factory a24c1 core in B1:F, independently read it back,
booted it with J1, then returned with J3. Maintenance erased that temporary
F sector while running from the original B3 monitor.

B0 and B3 were not write targets. The B3:F maintenance confirmation test
answered Y at the first gate and N at the second, producing CANCELED.
Every temporary flash destination was restored to FF. Final independent
32-KiB dumps of each bank were compared byte for byte to the starting images.
Both boards ended at B3>, autostart disabled, with their original flash and
configuration unchanged. Maintenance used transient RAM scratch at
$1000-$14FF; it is not claimed that all application RAM remains unchanged.

| Bank | 2205 before = after SHA-256 | 2609 before = after SHA-256 |
| --- | --- | --- |
| B0 | `2f0000c74eceec809a814e31f822702977d7bfed5ee6f3bc4869627864ca59a8` | `1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94` |
| B1 | `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc` | Same |
| B2 | `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc` | Same |
| B3 | `61b5d94efd11a9de47e7cd70f7524dc47bc41b9bb86a8fbce96efd1c9dad2bc9` | Same |

## Artifact identities and evidence

The core firmware outside its configuration pocket matches factory F
SHA-256 `231fbec1b0e6a1e80f4a956009aa74f6259e4f0dfcf761f09f16755832aece36`.
The configured F sector retains the hash recorded in the cold/config report.

| Loaded S19 | SHA-256 |
| --- | --- |
| a24c1 RAM ABI probe | `5d84498a350edff13e40414af8351a7f2652281f320a2cdd9daeefea5c69c566` |
| a24c1 BRK/IRQ probe | `7c4988d0c5cf12bb948acd4d611d57c4e5cb104e939a50ac548c0c364b392947` |
| a24c1 NMI probe | `583cb03c98418e65520fedb2f9c9a174d61c7662df16de6106a8f799aa1d9fcf` |
| a24c1 native probe | `8b8e689c041882f9b5f005e38262cb756d8a04e306a86988bcebb968b2a26dfc` |
| Bank Maintenance 1.0 | `e435141e41430a96bed362f60d50931168c6377233950605764a73d88a341327` |

Owner-local evidence is under
`output/qualification/a24c1-acceptance-2026-10-03/COM3/` and `COM8/`.
Each contains append-only timestamped TX/RX logs, before/after bank BINs and
hash lists. IMAGE events identify loaded S19 files and hashes. The local
`regression.py` harness checks RAM loads and temporary sector images;
`verify_regression.py` verifies successful recorded results and exact bank
preservation, producing `regression-verification.json` with log hashes.

## Retained attempts and limits

The first 2205 physical-NMI attempt reported TIMEOUT and returned to the
monitor. No successful NMI was captured within that attempt's window; its
cause was not established. A freshly armed repeat passed with an owner
confirmed NMI press. Both attempts remain in the evidence.

Initial harness attempts also stopped on expected-string mismatches:
bank selection changes the prompt to B0>, protected operations report
Protected/Sector span, and maintenance plans print DEST B1 rather than DEST 1.
The harness was corrected, pending maintenance confirmation was canceled,
and the listed checks completed. These stops were capture/assertion issues;
they did not produce flash-failure reports. Original RAM edit scratch was
restored from the earliest captured readback.

This is scoped practical hardware acceptance, not an exhaustive matrix.
Native IRQ/COP/ABORT, other guest firmware and J0/J2 boots, ACIA/EDU,
overlapping-copy stress, transfer-tail/malformed-S19 stress, flash fault
injection, interrupted-write/power-loss recovery, and installer backup/retry/
restore paths are not established by this regression session. The subsequent
[backup/recovery session](STR8N_V2_A24C1_BACKUP_RECOVERY_ACCEPTANCE_2026-10-03.md)
closes item 4 within its model/physical-fixture scope. Beta packaging/
publication remains item 5.
