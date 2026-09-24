# STR8-N alpha21 installation and cold USB capture on board 2512

Date: 2026-09-24. The operator approved installation of the
[frozen alpha21 candidate](STR8N_V2_ALPHA21_FREEZE.md) on board 2512 with
the EDU removed. COM4 identified the FT245 adapter as `A10MQFLCA`.

## Preflight and installation

With alpha20 at `B3>`, complete read-only F-sector dumps established:

| Sector | Pre-install SHA-256 | Exact identity |
| --- | --- | --- |
| Bank 3 F | `10b74fc4188a1cbe822eb931697794cc7acd22460d5a16eb03d9d621e3e5ac8e` | Frozen alpha20 top |
| Bank 2 F | `4df7dbd19b4891dfe5d381600e3edba185578aea1969df798c50cbb606814e91` | Retained alpha19 top |

The frozen `str8n-v2-alpha21-b3-top-update-2000.s19` had SHA-256
`b397287a364428040bcc3d592b542dc6f7c48489331195e4f40ee6e5d4f9fd97`.
Alpha20 `L` reported `Entry 2000`, and `G 2000` started the guarded updater.
After exact `BACKUP B2F` confirmation, the updater reported `BACKUP VERIFIED`,
safe physical range `$17000-$17FFF`, target `$1F000-$1FFFF`, and old-top sum
`$80DA`. Exact `STR8-N 2.0A21` confirmation produced
`STR8-N 2.0a21 VERIFIED; RESET` and the alpha21 Bank 3 banner.

A later physical reset with timed `S` remained at `B3>`. Independent complete
F-sector readbacks then passed byte-for-byte comparisons:

| Sector | Post-install SHA-256 | Exact identity |
| --- | --- | --- |
| Bank 3 F | `3738eab501c50ef0470e9a81ef573b563da7dc656cc18a83573d16c9bd2e6e49` | Frozen alpha21 top |
| Bank 2 F | `10b74fc4188a1cbe822eb931697794cc7acd22460d5a16eb03d9d621e3e5ac8e` | Pre-install alpha20 top recovery copy |

The Bank 2 recovery copy remains installed. No cleanup erase was performed.

## Cold USB power-on

The first receive-only capture expired before the operator power cycle. In
the retry, the operator unplugged USB power, waited approximately ten seconds,
and reconnected it. The capture recorded COM4 disconnecting and reopening at
Unix time `1790281950.862`. The complete alpha21 Bank 3 banner arrived at
`1790281955.889`, about 5.03 seconds after COM4 reopened:

```text
STR8-N 2.0a21 B3 65C02
ABI 65C02 | 816E | 816N-VEC
C 01 01 V 20
S/Ctrl-C hold
```

The configured handoff then printed `RST H`, STR8-N 1.35, `BOOT WARM`, and
`HIMON V 00.0916(1949)`. This accepts cold USB reconnect banner capture and
the configured Bank 1 startup path on board 2512. It does not resolve ACIA
receive/fallback, W65C816 execution, or the remaining release qualification
matrix. The final observed prompt was Bank 1 HIMON `>`.

Owner-local readback BINs and append-only JSONL transcripts are retained in
`output/qualification/board-2512-alpha21-install-2026-09-24/`. Key transcript
SHA-256 identities:

| Capture | SHA-256 |
| --- | --- |
| `b3-top-before.jsonl` | `cb19f6316060edcbae48ec1360c62aac292fb9609dd66e611fe47ccfde36d8f4` |
| `b2-top-before.jsonl` | `a35908e5a0fb8038f3240e60e871965c71cda14827d35980b60fc3ba6ed7157c` |
| `updater-load.jsonl` | `7cfa9de321a98f880824457606c47533a8a3048e4a2955f42cc23868f39c1f67` |
| `backup.jsonl` | `9995abd5e908d1f92a1bf7421ff9589c1c05b0975838276739bd91744a588247` |
| `commit.jsonl` | `aaf41562c6bfec0df7800fa3530b125bfbe6238af990f59ac6ff506fe48a671e` |
| `b3-top-after.jsonl` | `d72470fd9f253d0131bfb719263767704c8ac2f29b6e0400178737d96cdd81b7` |
| `b2-top-after.jsonl` | `64dbd61156847f710ec0b1809f026969fbd48766d3de25e98be8a56d2684c09c` |
| `cold-power-alpha21-retry.jsonl` | `5e1d9340626a1980b497a591ad7f5480832edce2823698ec122fd1ee8187d57c` |
