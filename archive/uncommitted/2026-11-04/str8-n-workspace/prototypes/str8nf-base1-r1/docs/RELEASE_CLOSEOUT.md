# STR8N-F 0.3.0 release closeout

The [0.3.0 release](https://github.com/95westus/STR8N-F/releases/tag/v0.3.0)
is public. [PR #2](https://github.com/95westus/STR8N-F/pull/2) promotes its
foundation, current README, manual and scoped evidence to `main` under the
owner's explicit merge authorization. Its GitHub merge record identifies
the exact main integration commit.

- F stays **0.3.0 g00000001 / BASE1 / PR05**, exactly 4096 bytes.
- Frozen F SHA-256:
  `8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1`.
- `v0.3.0` stays at the original packaged source checkpoint
  `a5f1d83`; later docs/receipts do not move that tag.
- The twelve published downloads retain their original sizes and hashes.
  No assets are replaced, rebuilt or added for this closeout.
- The operator kit includes the Python serial terminal, WDC RAM migration
  programs, CONFIG, OPAQUE, MAP, READBACK and DEMO; F.bin and the user manual
  are also separate release downloads.
- This closeout performs no firmware build, simulation, flashing or board access.

The README describes **one board with up to four boot environments**.
Compatible user-supplied images run one at a time on shared CPU, RAM and
peripherals. `main` carries the released foundation and current documentation;
future Mona and ABI work uses separate feature branches.

The [hardware scope](RELEASE_STATUS.md) remains unchanged. The 2512 receipts
and the 2609 extracted-rc1 existing-SNBT trial retain their exact tested scope.
The final ZIP has no additional live trial; WDC and programmer-F provisioning
from an extraction remain untested package routes. These are documented limits,
not new hardware passes. Mona and additional service ABI work remain planned.

[Publication receipt](../validation/base1-0.3.0-publication.json) and
[additive download receipt](../validation/base1-0.3.0-user-downloads.json)
bind all twelve release assets. Original archived metadata describes packaging
time; current source metadata records publication. Existing archives stay intact.
