# Board 2205 crypto information read — 2026-09-30

The RAM diagnostic completed on board 2205 (COM3, FT245 `A10MPUPNA`), under
STR8-N 2.0a31 on the 65C02. The loaded 1,160-byte image at `$2000-$2487`
matched its complete monitor RAM readback before execution. It returned to
`B3>` with the existing RTC and EEPROM settings display intact.

## Observed information

| Field | Read result |
|---|---|
| Responding I2C address | `$60` (7-bit) |
| Info silicon revision | `00 00 60 03` |
| Configuration revision | `00 00 60 03` |
| Unique serial number | `01231454D6545F9FEE` |
| Configuration LockConfig byte | `$55`: unlocked |
| Data/OTP LockValue byte | `$55`: unlocked |
| SlotLocked bitmap | `$FFFF`: no individual slot lock bits cleared |
| Counter 0 / Counter 1 | `0` / `0` |
| Info state | `00 00 00 00` |
| Persistent latch read | `00 00 00 00` |
| KeyValid queries, slots 0–15 | Each returned `00 00 00 00` |
| Configuration | All 128 bytes read successfully |
| OTP | All 16 four-byte requests returned status `$0F` |

The response identifies the ATECC608 family; this report preserves the raw
revision rather than asserting a package/order-code suffix from it. Unlocked
flags establish the present lock state, not the complete provisioning history.
KeyValid responses are status metadata, not a dump of key material.

OTP read failure is consistent with the data/OTP zone still being unlocked.
The chip was left unlocked; no setup was performed to make these reads succeed.
All 69 response packets, including the 16 error responses, passed CRC checks.

## Scope and evidence

The fixed command list uses Info modes 0, 1, 2, and 4 with read-only parameters;
Read for configuration/OTP; and Counter mode 0. Wake and Sleep change transient
session state. No NVM write, lock, provisioning, key generation, counter
increment, or flash programming command was issued.

- [Decoded summary](evidence/board-2205-crypto-info-20260930/summary.json)
- [All command responses](evidence/board-2205-crypto-info-20260930/responses.json)
- [Raw 128-byte configuration](evidence/board-2205-crypto-info-20260930/config.bin)
- [Board output](evidence/board-2205-crypto-info-20260930/output.txt)
- [Full TX/RX transcript, including RAM readback](evidence/board-2205-crypto-info-20260930/serial.jsonl)
- [Artifact hashes](evidence/board-2205-crypto-info-20260930/hashes.json)
- [Build and usage](../tools/v2-crypto-info/README.md)

Host checks verified assembled command traffic, malformed wake/count handling,
absent/stuck bus exits, bounded execution, and VIA restoration. This live run
qualifies the probe on this board; other boards and CPU modes remain untested.
