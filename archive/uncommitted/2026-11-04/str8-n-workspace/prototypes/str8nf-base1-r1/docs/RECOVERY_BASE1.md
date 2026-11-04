# BASE1 independent readback and owner-RAM restoration

Recovery assumes [golden F](GOLDEN_F_RECOVERY_SCOPE.md): valid, verified and
unchanged. REC> runs in F, and the RAM service below relies on matching F CRC
routines. Neither is a promised recovery path for erased or corrupted F.
Interrupted-F testing is outside the installed-BASE1 runtime contract and
remains NOT RUN. Initial installation/explicit F upgrade is a separate case.

The [2512 C/D interruption trial](2512_CD_RECOVERY_ACCEPTANCE.md) passed six
reviewed chip-idle USB power-cycle cases using a separate source-bound RAM lab
for exact partial-record completion, committed-record recognition and peer-erase
recovery. Original records/images/policy/RAM were restored; F stayed unchanged.
This does not turn the read-only service into a flash writer or relax general
damaged-history refusal. Electrical interruption during an active flash pulse
and arbitrary damaged layouts remain outside that pass.

The matching `STR8N-F-READBACK-RAM.bin` is 3078 bytes and loads through F's raw L
at 0200, then copies a 439-byte service to 6800. Its visible prompt is
`RAM SERVICE BASE1> `. This is a new fixed-range protocol; old `RAM SERVICE>`
clients are incompatible.

| Command bytes | Response or input |
| --- | --- |
| F, then bank byte 00-03 | 32768 flash bytes, CRC16 little endian, prompt |
| M | RAM 0200-66FF: 25856 bytes, CRC16, prompt |
| Z | Owner ZP 00-DF: 224 bytes, CRC16, prompt |
| W, then 25856 bytes and CRC16 | Restore 0200-66FF; prompt only if CRC/RX valid |
| Y, then 224 bytes and CRC16 | Stage at 6700, check CRC/RX, then restore 00-DF |
| Q | Return to F recovery |
| J | Software restart through F; not a physical-reset test |

The service never writes flash. F must match PR05 and remain visible for CRC
calls; each flash-data fetch temporarily selects its bank and restores B3.
The service at 6800 and its 6700 staging frame do not overlap owner RAM.
ZP E0-FF and the runtime stack are system scratch, not restored owner bytes.

The host client `tools/nf_recovery.py` opens no port. The WDC migration executor
uses it only after observing the physical-reset recovery face. It loads the
matching image, independently reads all four final banks and compares their
SHA-256 values to the admitted plan. It then restores RAM and ZP, reads both
back byte-for-byte and returns to `REC>`. Only that completed path reports owner
restoration verified. A timeout, CRC or byte mismatch stops without retries.

Loading a RAM tool borrows application RAM. Original escrow must precede the
first helper upload; a dump taken afterward cannot recover the overwritten
prefix. The implemented [live C/D route](LIVE_CD_PROVISIONING.md) requires
explicit original pre-helper escrow, binds it to the selected USB/CPU, saves
it durably before loading, and restores/verifies it at completion. No implicit
disposable-RAM path is supplied. Its reviewed
[2512 hardware entry](2512_PROGRAMMER_F_CD_ACCEPTANCE.md) passed the no-op and
occupied non-SNBT provisioning cases. Other platforms/layouts and interrupted
provisioning remain unqualified. The 0.3.0-rc1 kit includes the same tested
public entry; acceptance from its extraction remains pending.

The authorized [2512 BASE1 case](2512_BASE1_ACCEPTANCE.md) exercised this service
on real 65C02 hardware: independent full-bank CRC/SHA checks, full RAM/ZP
restoration and verified return to REC>. The later
[2512 WDC migration](2512_WDC_MIGRATION_ACCEPTANCE.md) also passed its real
integration and restoration path. Broader CPU/platform and remaining fault
paths retain their separate qualification limits. No CPU model ran.
