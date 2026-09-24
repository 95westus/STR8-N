# STR8-N V2 alpha16 RAM ABI board test — 2026-09-23

Alpha16 was installed in board 2205 Bank 3 through the guarded V2-to-V2
updater on COM3. The updater copied and verified the old B3 top sector in
B2:F before it erased B3:F, programmed the candidate from RAM, verified the
new sector, and reset into:

```text
STR8-N 2.0a16 B3 65C02
ABI 65C02 | 816E | 816N-VEC
B3>
```

The RAM-only hardware probe selected every flash overlay and called PUTC
without remapping the resident monitor:

```text
G 2000
B0 B1 B2 B3 RAM ABI: PASS

STR8-N 2.0a16 B3 65C02
ABI 65C02 | 816E | 816N-VEC
B3>
```

This proves the `$7E60` RAM table executes with B0, B1, B2, or B3 visible,
each tested PUTC call preserves the caller's bank, and RAM HOLD restores the
stored resident bank. A live dump showed the descriptor `52 41 01 0D` and all
thirteen JMP entries at `$7E60-$7E8A`.

The temporary B2:F recovery copy was then erased. Readback samples at B2
`$8000`, `$E000`, and `$F000` were all `$FF`. B3 `$F035-$F038` read
`43 41 01 17`, and B3 `$FF00-$FF1F` remained erased. B0 `$8000` still began
`57 44 43 00`, identifying the preserved WDCMONv2 payload.

B1 was launched with `J1`. STR8-N 1.35 reached its selector and HIMON
V00.0915(2324), then its `STR8` command and `J3` returned to alpha16 B3. This
physically verifies that the preserved R-YORS/HIMON bank still operates after
the update.

| Artifact | SHA-256 |
| --- | --- |
| Alpha16 E-F image | `08AFF780574D1282F8B5BDC6030F3CDA5C95E589BD593962B2ECCF16DE84697B` |
| Guarded B3 updater | `E0B114CA3FFBF7A086781138B39FD142C208794AF17131379FEA380732D449E2` |
| Cross-bank RAM ABI probe | `3546FD7D8E172A644C9AB7036DE75DA50C1CF7214D150EF91567D14F630C7C82` |
| B2 erase image | `8672CE88FCA2642A18807D87F0F860971C63BE82485A2F8313F8AA4BA8BCC7CE` |

The complete host `make v2-check` suite also passed. It exercises every
returning RAM service in all sixteen resident-bank/caller-bank combinations,
both console transports, reset/HOLD behavior, flash operations, configuration,
cancellation, interrupts, and the guarded migration path. The unchanged v1.35
top updater retained SHA-256
`F9C18E424A8689C0F1C1CADDDCB585852EEF2F3A77E46A7F58928CD7AD30E846`.

Board 2205 now contains WDCMONv2 in B0, R-YORS/HIMON and STR8-N 1.35 in B1,
an erased B2, and STR8-N 2.0a16 in B3. Its previously observed ACIA receive
fault remains a board-specific hardware limitation; ACIA transmit worked in
the earlier alpha13 direct test.
