# OIP1 opaque sector protocol

This describes the matching `STR8N-F-OPAQUE-RAM.bin`. The supplied Python packet helper is offline: it builds files and opens no port. It is not an automatic flashing client.

Load the RAM tool through `REC>` / `L`. At `INSTALLER I Q>`, `I` begins a transaction and `Q` restarts through F. Wait for `SEND OIP1 HEADER` before sending a 20-byte header. For a write, wait for `SEND 4096` before sending the 4096 payload bytes. Do not concatenate a header and payload into one unpaced terminal send.

| Header offset | Bytes | Meaning |
|---|---:|---|
| 0 | 4 | ASCII `OIP1` |
| 4 | 1 | Version 1 |
| 5 | 1 | Operation: 0 read, 1 replace |
| 6 | 1 | Bank 0–3 |
| 7 | 1 | Sector high byte: 80,90,A0,B0,C0,D0,E0,F0 hex |
| 8 | 2 | Length 4096, little endian |
| 10 | 2 | Expected preimage CRC for replace; zero for read |
| 12 | 2 | Payload CRC for replace; zero for read |
| 14 | 4 | Reserved zeros |
| 18 | 2 | Header CRC over bytes 0–17 |

All CRCs are CRC-16/CCITT with polynomial $1021, initial $FFFF, no reflection/final XOR; multi-byte values are little endian. The preimage CRC detects an unexpected target before erasing. It is not a cryptographic image identity: retain SHA-256 and a verified full backup independently.

Read success returns `READ SECTOR+CRC` plus CR/LF, 4096 raw bytes, a two-byte CRC, then CR/LF and `OK: read` before the prompt. Capture binary bytes without terminal decoding. Replace success reports `OK: verified sector`; an identical payload reports `OK: identical; no erase`. The guarded writer records the attempted erase durably before beginning it. A refused/malformed protected target may lock the tool and require RESET; do not resend arbitrary bytes after an error.

Prepare a read header:

```text
python tools/oip.py read --bank 1 --sector 9000 --out build/read-b1-9
```

After obtaining and verifying `before.bin` and preparing exactly one `after.bin` sector:

```text
python tools/oip.py replace --bank 1 --sector 9000 --before before.bin --image after.bin --out build/write-b1-9
```

The output includes `header.bin`, a manifest and, for replace, `payload.bin`. Header/payload are deliberately separate files. A new output directory is required. Both the helper and device reject protected B3:A/B/C/D/F targets. B0 is allowed by the protocol, so an owner WDC backup in B0 must be preserved by choosing another target.

The 0.2.0 helper prepares packets; it is not an automatic live installer.
Use the explicit paced procedure above with independent preimage/payload
verification and binary capture for reads. The matching
[READBACK RAM service](READBACK.md) exports complete banks with CRC. Preserve
owner RAM before loading tools. A general automated admission/escrow/transfer
client remains future work.
