# STR8-N alpha20 installation on board 2512

Date: 2026-09-24. The operator approved flashing the new frozen alpha20
candidate on board 2512. The EDU board was removed. COM4 was the FT245 port.
This report records successful guarded installation, boot, and independent
post-install readback. A subsequent cold USB reconnect did not capture the
alpha20 banner.

Before mutation, an exact 4096-byte `D F000 FFFF` readback of Bank 3 F had
SHA-256 `4df7dbd19b4891dfe5d381600e3edba185578aea1969df798c50cbb606814e91`,
matching the prior alpha19 layout readback. Bank 2 F was read independently
and every byte was `$FF` (SHA-256
`f47a8ec3e9aff2318d896942282ad4fe37d6391c82914f54a5da8a37de1300c6`).

The host loaded the frozen
`str8n-v2-alpha20-b3-top-update-2000.s19` (SHA-256
`bb5c3aa2f165ca9d920814fc2ead3e133a07110b393e69cc18b4e28868721353`)
through alpha19 `L`, which reported `Entry 2000`. `G 2000` started the guarded
updater. After the exact backup confirmation, it reported `BACKUP VERIFIED`,
identified safe physical range `$17000-$17FFF`, target range
`$1F000-$1FFFF`, and old-top sum `$8925`. The exact `STR8-N 2.0A20`
confirmation then produced `STR8-N 2.0a20 VERIFIED; RESET`.

The first reset printed:

```text
STR8-N 2.0a20 B3 65C02
ABI 65C02 | 816E | 816N-VEC
C 01 01 V 20
S/Ctrl-C hold
```

In the serial log, `VERIFIED; RESET` completed at approximately
1790280439.517 UTC seconds and the first byte of the alpha20 banner arrived
at approximately 1790280444.471, a 4.954-second interval. This is direct
hardware evidence of the new startup wait plus reset/console overhead; it
does not itself prove a cold USB reconnect captured the banner.

The configured handoff subsequently reached Bank 1 HIMON. A physical reset
with `S` during the hold window returned to `B3>`. A complete independent
`D F000 FFFF` readback matched the frozen alpha20 top sector byte for byte;
SHA-256 `10b74fc4188a1cbe822eb931697794cc7acd22460d5a16eb03d9d621e3e5ac8e`.
A complete Bank 2 F readback matched the pre-update alpha19 top byte for byte;
SHA-256 `4df7dbd19b4891dfe5d381600e3edba185578aea1969df798c50cbb606814e91`.
The recovery copy remains in Bank 2 F.

The operator then unplugged USB power, waited approximately ten seconds, and
reconnected it while a receive-only COM4 capture was armed. COM4 disconnected
and reopened. The first received board output was `RST H` / STR8-N 1.35, then
`BOOT WARM` and HIMON. The alpha20 Bank 3 banner was still missed. This fails
the specific cold-reconnect banner capture goal. One plausible cause is that
`CON_INIT` sampled PWE# before the USB host configured FT245, selected ACIA,
and only then executed the delay; the capture does not prove that cause. A
follow-up candidate should delay before console selection and test that
sequence on hardware.

Owner-local JSONL transcripts and the two pre-install BIN files are under
`output/qualification/board-2512-alpha20-install-2026-09-24/`. Principal
transcript SHA-256 identities:

| Capture | SHA-256 |
| --- | --- |
| `b3-top-before.jsonl` | `32745d2a9ad3c93b14ab4c03d3b99a040f42d50fbeaac3e3a816d603e8027f82` |
| `b2-top-before.jsonl` | `fbfa77ecd14d61f661a701168f180f6fa7c79511dce34aa1dd51cdf99c262313` |
| `updater-load.jsonl` | `6dfe49fd8df4d07c7645ffb5c341311521ddbd0d0c9e1d9dd95a80249d03af7b8` |
| `backup.jsonl` | `6e68c6af1e8f6d76101d1f2b1cdc36826d081f4d0f2e869989f165422b867296` |
| `commit.jsonl` | `508f556c48f92f5f960d851658ec45a207344901ddb6c71dcf238cc917d20096` |
| `alpha20-readback-reset-2.jsonl` | `6addeccd5d53f1b52ad73c993f5afd7640e7341760dc312e6d35158919dd8646` |
| `b3-top-after.jsonl` | `ee46d135ca58c4fb933dc573aaa519a15c9c0dd68cba4a3b106a6ad469e70022` |
| `b2-top-after.jsonl` | `11ce2cf1baf203da084cc256bb65cf71dccb002c6d2de3c76d1a0699b5a8871a` |
| `cold-power-alpha20.jsonl` | `5c7ab21ada00e15276df50c9fb41e5d23125140ea9c46da990bf5a7f25fa020f` |
