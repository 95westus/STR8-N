# JCR1 source-bound journal lab

This is a case-specific RAM lab for the reviewed 2512 C/D interruption trial,
not a general repair utility or a release-kit payload. See the
[B3 budget and fault cases](2512_CD_RECOVERY_SCOPE_REVIEW.md). The production
CONFIG writer, general damaged-history classifier and frozen F are unchanged.
The [2512 hardware acceptance](2512_CD_RECOVERY_ACCEPTANCE.md) records the six
reviewed chip-idle power-cycle results and their limits.

## Image and admission

The image is 19968 bytes, loaded at 0200 through matching golden F's REC> L.
Code ends below 4000; rendered metadata/frames occupy 4000-43FF. Mutable lab
state is 6100-611F, while the existing writer uses 6700 and system RAM/ZP.
Original owner RAM must already be escrowed; raw L cannot save its old prefix.

| Address | Contents |
| --- | --- |
| 4000-4003 | JCR1 magic |
| 4004 | Protocol version 1 |
| 4005 | Operation 1-7 |
| 4006 | Cut 0=none, 1=128 bytes, 2=before commit, 3=after commit, 4=peer erased |
| 4007 | Target page high byte, C0-DF |
| 4008 | Bounded fill count; zero for other operations |
| 400C | Expected selected committed source page |
| 4010-401F | Four source-bank FNV32 values, little endian |
| 4020-4023 | Expected B3 result/checkpoint FNV32, little endian |
| 4100-41FF | Intended committed SNBT record; unused by bounded fill |
| 4200-42FF | Exact target-page preimage |
| 4300-43FF | Exact selected committed source record |
| 4FFC-4FFF | FNV32 over the complete 0200-4FFB image, little endian |

The builder emits an unrendered template that refuses execution. A phase packet
must be sealed without assembly. Fresh live complete-bank captures must admit
the reviewed reference before packets can execute; each packet then rechecks
its own image, golden F fingerprint, all four banks, BF/B5 chip and selected
record. Nothing is programmed before the matching Y confirmation. Source and
self guards run again after Y. These checks are integrity/admission checks,
not a cryptographic security boundary against a hostile host.

## Operations

1. Append the next normal nonreserved page; optional controlled cut.
2. Complete an explicitly inspected uncommitted page in place. Every byte must
   already equal the intended value or be FF; equal bytes are not reprogrammed.
3. Reinstate only one of the three original snapshot fingerprints, at its
   original C000/C100/D000 address, after the target page is verified blank.
4. Exercise native JE_SPACE: commit the last-page intent, erase/verify the
   occupied peer, then stop at the guarded chip-idle checkpoint.
5. Recognize the exact already committed record. No append/program/erase.
6. Fill a bounded blank interval ending no later than page E, using native
   JE_SPACE/JE_SEAL/JE_WRITE and unchanged policy/counters.
7. Publish the newer peer snapshot after its original historical prefix has
   been reinstated and verified. Preserve the surviving intent's current counts.

Record CRCs, fields, sequence increments and unchanged body/counts are checked.
The original B default may only be restored with its original C100 fingerprint
present. That is escrow restoration, with no legacy MON execution. Ordinary
CONFIG's incompatible-target refusal remains intact.

The lab copy instruments writer checkpoints, permits exact-preimage completion
and skips identical bytes. It guards every record destination within C/D.
Any unexpected state refuses or halts for inspection; no retry, erase, counter
rollback, generic force repair or automatic reset is supplied. Stable completion
returns to REC>; a fault checkpoint waits for the operator's approved power cut.
Idle checkpoints/completion return LEDs to 01. All rendered packets and captures
contain private owner data and stay outside public source/kit assets.
