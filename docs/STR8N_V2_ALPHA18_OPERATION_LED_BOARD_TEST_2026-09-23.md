# STR8-N V2 alpha18 operation LED board test — 2026-09-23

Alpha18 adds operation-level EDU LED activity without adding a public LED ABI
or changing the public ROM and RAM ABI addresses. Complete checksum-valid
S-records toggle the green RX bit between `$01` and `$05`. Flash unlock uses
`$F0` on even 256-byte pages and `$F1` on odd pages, so all four red LEDs remain
asserted throughout flash mutation. The prompt restores `$01`; application
handoff remains `$00`. Public console calls remain LED-neutral.

The change costs 17 resident bytes. The resident is 3806 bytes and ends at
`$FEDD`; `$FEDE-$FFDF` is erased, including the fixed `$FF00-$FFDF` expansion
reserve. The RAM worker is 748 bytes and ends at `$7BEB`, leaving 20 bytes in
its fixed allocation. The vector/RAM ABI image remains 196 bytes.

`make v2-check` passed every boot, ACIA, migration, monitor, S19 load, flash,
configuration, timing, interrupt, and native static check. New execution tests
verify each accepted S-record transition, prompt restoration, rejection without
an activity toggle, even/odd flash-page phases, the all-red safety invariant,
and updater page phases.

Alpha18 was installed on board 2205 through the guarded B2:F backup path. The
updater verified the backup and target and booted:

```text
STR8-N 2.0a18 B3 65C02
ABI 65C02 | 816E | 816N-VEC
B3>
```

The physical RAM-only probe passed:

```text
B0 B1 B2 B3 RAM ABI: PASS

STR8-N 2.0a18 B3 65C02
ABI 65C02 | 816E | 816N-VEC
B3>
```

The temporary B2:F backup was erased with the established all-`FF` install
payload and read back as `$FF`. B3 readback showed code through `$FEDD`, erased
bytes starting at `$FEDE`, and erased `$FF00-$FF0F`. B1 retained its `SR 02 03`
STR8-N 1.35 signature, and B0 retained its `57 44 43 00` WDCMONv2 header.

The serial transcript proves the guarded update, boot, probe, erase, and
readback. LED transition values are established by executing host hardware
models; the serial interface does not observe the physical LEDs.

| Artifact | SHA-256 |
| --- | --- |
| Alpha18 E-F image | `7C4F3DC72F20045200653BDD6757B439B7A57BD245A7F401A9D6244B37FF4323` |
| Guarded B3 updater | `DA571A74F3CB38480D1B24B2B1AB202C54A5063845D7A9000E4FE8995506B992` |
| Cross-bank RAM ABI probe | `4D6CF16AB5D62FB73205BB3BABCE8ABB455301A01730E9F7FEDC9D425AE5E648` |
| B2:F all-FF cleanup payload | `8672CE88FCA2642A18807D87F0F860971C63BE82485A2F8313F8AA4BA8BCC7CE` |

Board 2205 now contains WDCMONv2 in B0, R-YORS/HIMON and STR8-N 1.35 in B1,
an erased B2, and STR8-N 2.0a18 in B3.
