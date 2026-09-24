# Board 2512 four-bank layout

Date: 2026-09-24. The operator requested Bank 0 retain WDCMONv2, Bank 1 hold
STR8-N v1.35 with HIMON and ASM-F2, Bank 2 be erased, and Bank 3 contain the
frozen STR8-N v2 alpha19 top sector above erased lower sectors. COM4 used FTDI
adapter `A10MQFLCA` at 115200 baud. Four complete 32 KiB readbacks were saved
before flash changes. No Bank 0 write was attempted.

Bank 1 was installed from the dense
`BUILD/v1.35/s19/ryors-v1.2-str8n-himon-asm-bank0-2-8-f.s19` image (SHA-256
`38fd193eef02fc0f98d2ac6cc99e4c2b7196d23dabf23c474721ebb5852e7f96`)
using the Bank 3 v1.35 installer, range `8-F`. The installer reported `OK`;
a read-only RAM archive then returned a complete, exact Bank 1 readback.

The v1.35 bank-maintenance tool erased and verified Bank 2 sectors `8-E` and
Bank 3 sectors `8-E`. Its map showed those sectors erased while Bank 2 F still
held the protected old-top backup and Bank 3 F still held v1.35. The frozen
alpha19 B3 updater refused the transition before any write because its
preflight requires an already-installed v2 signature. A separate owner-local
RAM bridge changed that preflight to require the live v1.35 `$F000` jump and
`$F00C-$F00D` `SR` signature. It retained the frozen candidate F-sector bytes,
backup/verify, recovery, and flash worker. A host flash-model run passed v1
preflight, exact Bank 2 F backup, v2 F install, and restoration of the old top.
The bridge source and S19 are retained with the session evidence; the v2
firmware image itself was not rebuilt.
The bridge source SHA-256 is
`fa7cb60b11d37f5b16c986ffe172a8bde674e4e2dc4b57aab83deb5aef7a62d3`;
its loadable S19 SHA-256 is
`c2bf53d27da9bbfc5dba473dbca99434889e9a49d27189dcdc45318e69ac32f4`.

On hardware, the bridge reported `BACKUP VERIFIED`, then
`STR8-N 2.0a19 VERIFIED; RESET`. Bank 3 booted to
`STR8-N 2.0a19 B3 65C02` and `B3>`. Its full-bank readback matched the frozen
alpha19 image exactly. The temporary Bank 2 F backup was then erased through
v2's `I F000 FFFF` using a dense all-`$FF` S19; the monitor reported `Done`.

| Bank | Final SHA-256 | Exact target |
| --- | --- | --- |
| 0, retained WDCMONv2 | `2f0000c74eceec809a814e31f822702977d7bfed5ee6f3bc4869627864ca59a8` | Yes; unchanged |
| 1, v1.35 + HIMON + ASM-F2 | `90b5cceecb008a586c8bf65567bee606aeadd9cd09851f0cbbe05e1d27232260` | Yes |
| 2, all `$FF` | `2d864c0b789a43214eee8524d3182075125e5ca2cd527f3582ec87ffd94076bc` | Yes |
| 3, frozen v2 alpha19 in F; `8-E` all `$FF` | `ca705a6ea2d7b06221be1087c46a23bbf5a0f81b96d7a80705f38ef36f75f528` | Yes |

Each final readback contained 2048 ordered 16-byte rows covering
`$8000-$FFFF` without gaps. A `J1` boot reached Bank 1 HIMON; `ASM NEW`
entered `ASM-F2 00.0916(1949)`. Bank 0 was verified by bytes, not booted in
this session. After the ASM-F2 check, physical RESET returned to `B3>`. A
subsequent `J3` printed `STR8-N 2.0a19 B3 65C02` and returned to `B3>`.

Owner-local before images, target images, transcripts, bridge source/transport,
test output, and final readbacks are under
`output/qualification/board-2512-layout-2026-09-24/`.
