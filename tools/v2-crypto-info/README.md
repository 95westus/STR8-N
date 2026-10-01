# ATECC608 informational RAM probe

This diagnostic reads chip metadata without provisioning, writing nonvolatile
memory, creating keys, locking zones, or incrementing counters. It is separate
from the firmware startup inventory.

## Build and run

```text
python tools/build_v2_crypto_info.py
python tools/test_v2_crypto_info.py
python tools/run_v2_crypto_info.py
```

The runner targets board 2205, FT245 serial `A10MPUPNA`, on COM3. Disconnect
any terminal holding that port first. It requires the alpha31 65C02 banner
and EDU detection, loads the probe at `$2000`, verifies every loaded RAM byte
using the monitor dump command, then executes it. No flash installation occurs.
The 1,160-byte image occupies `$2000-$2487`; this RAM is overwritten.

## Reads

The fixed 69-command table contains:

- Info revision, volatile state, and persistent-latch read (Param2 zero).
- Info KeyValid for all 16 slots, returning metadata only.
- All 128 configuration bytes, as 32 four-byte Read commands.
- Both monotonic counters in read mode zero.
- All 64 OTP bytes, as 16 four-byte Read commands.

Data/key slot contents are outside this metadata probe. OTP/counter/KeyValid
requests may return an error on an unlocked or differently configured device.
Those replies are retained; they are not treated as successful data reads.
No GPIO-setting Info mode, latch write, Counter increment, Write, Lock,
UpdateExtra, GenKey, Random, Nonce, or cryptographic operation is issued.

The bus uses VIA1 PA0/PA7, open-drain emulation, and the default ATECC
7-bit I2C address `$60`. A device configured at another address will not be
found. Every command gets a wake pulse and a verified four-byte wake reply,
then a fixed approximately 41 ms execution delay at 8 MHz. Reply counts are
bounded to four or seven bytes. Each transaction ends with Sleep before
printing. This changes transient wake/session state, not provisioning.

VIA DDRA and driven pin levels are restored. As in the RTC diagnostic,
previous hidden latch values on input pins cannot be recovered by reading
the VIA. Do not run alongside another handler using the I2C pins.

## Evidence and validation

Each run creates a timestamped directory under `BUILD/v2-crypto-info` with
serial TX/RX evidence, raw replies, and decoded results. The host checks every
reply CRC; configuration and summaries are produced only after all 69 replies
pass. `summary.json` includes serial number, revision, address, lock status,
raw slot/key policies, counters, and unavailable-command status bytes.

Host tests execute the assembled image and verify exact transmitted command
bytes, wake/count rejection, absent/stuck bus return, and VIA restoration.
They do not simulate electrical timing. Board 2205 passed a live run on 2026-09-30 after the terminal released COM3.
All 69 replies had valid CRCs; all 128 configuration bytes were read. The 16
OTP requests returned device status `$0F`. See the
[board report](../../docs/STR8N_V2_CRYPTO_INFO_2205_2026-09-30.md).

## Protocol references

- [Microchip command definitions](https://github.com/MicrochipTech/cryptoauthlib/blob/main/lib/calib/calib_command.h)
- [Microchip Read command implementation](https://github.com/MicrochipTech/cryptoauthlib/blob/main/lib/calib/calib_read.c)
- [Microchip Info implementation](https://github.com/MicrochipTech/cryptoauthlib/blob/main/lib/calib/calib_info.c)
- [ATECC608A configuration and command documentation](https://www.microchip.com/en-us/product/atecc608a)
