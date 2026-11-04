# BASE1 OPAQUE host helper

`tools/nf_opaque.py` talks only to the already loaded **OPAQUE BASE1 / PR05**
RAM tool. It does not upload RAM, reset the board, initialize journals, select
a default boot image or start an application. This host helper and the new
target policy have host-only checks; hardware qualification is still pending.

The permitted destinations are B0/B1/B2:8-F and B3:8/9/A/B/E. B3:C/D are the
boot/wear journal and B3:F is recovery; all three remain protected. A usable
destination can still contain an owned application, monitor or provider.
Choose the exact target deliberately.

## Prepare the board

Use a supported USB/FT245 board with matching PR05 F, a valid C/D journal and
the new BASE1 OPAQUE RAM BIN. Keep an owner RAM backup before loading any RAM
tool. The public RAM RESET entry returns through startup choices; it is not a
MON HOLD return. If replacing an automatically booted image, select recovery
as the default beforehand so an interrupted replacement is not started on
reset. This helper does not make that configuration change for you.

From `REC>`, use `L` and send the matching OPAQUE BIN as binary. Wait for:

```text
OPAQUE BASE1 / PR05 I Q>
```

Disconnect the terminal before the helper opens the same port. Because the
terminal may have consumed that prompt, use `--request-prompt` only after you
have loaded and seen the matching tool. This explicitly sends **ESC+CR** to
cancel a pending line and request a fresh prompt. It sends no installation
command until the exact BASE1/PR05 prompt is received. Without that option the
helper passively waits for a fresh prompt. There is no automatic reset or
probing of other command interfaces.

Python requires `pyserial` for a real serial invocation. No vendor firmware is
included or required by this helper. Examples below use COM4 only as an example;
select the actual port and an explicitly assigned target.

## Read or replace one 4096-byte sector

```text
python tools/nf_opaque.py read --port COM4 --bank 3 --sector A000 --request-prompt --out owner-backups/read-b3-a
python tools/nf_opaque.py replace --port COM4 --bank 3 --sector A000 --image MY-IMAGE-4096.bin --request-prompt --out owner-backups/replace-b3-a
```

Each run requires a new output directory. A read saves `before.bin` only after
the device's 4096-byte reply and CRC match; the local file is flushed and read
back before it is accepted. A replacement first performs that same read and
durable backup, derives the preimage CRC from those bytes, waits for the
device's header/payload readiness, and sends paced binary blocks. The RAM tool
must reserve the erase attempt durably in C/D before issuing an erase. An
identical image causes no replacement command or erase request.

After programming, the helper issues a separate read request and compares all
4096 bytes with the requested image. `after.bin` and `receipt.json` record the
result. The receipt distinguishes a completed read, an identical no-write
operation, a verified replacement and an unaccepted/possibly changed target.
Serial bytes are recorded in the adjacent `RUN-NAME-serial.jsonl` file. These
files contain owner data and stay owner-local.

The helper reports each phase, payload progress, CRC/SHA results and backup
locations. It does not treat console text inside a binary sector as a command
or an error. SHA-256 identifies local files; the OIP1 device protocol uses
CRC16 for transfer/preimage checks.

## Failure behavior

A refusal, timeout, CRC mismatch, unexpected prompt, short transfer or differing
readback stops the run. There are **no automatic retries, reset, boot command
or boot-setting changes**. Keep the backup, log and receipt and inspect the
device state. A failed replacement may have changed its target; the receipt
keeps that uncertainty rather than marking it verified. A framing failure in
the RAM tool locks its input until RESET. Restore a target only through a new,
explicitly reviewed operation using its current preimage.

This helper leaves the OPAQUE tool running in RAM. It does not restore borrowed
owner RAM or prove power-loss recovery. Those are separate migration/release
acceptance steps.
