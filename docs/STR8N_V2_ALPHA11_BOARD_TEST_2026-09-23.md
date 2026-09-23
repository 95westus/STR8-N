# STR8-N v2-alpha11 board test — 2026-09-23

Status: passed on the battery-, cryptographic-chip-, and SPI-SRAM-equipped
board marked `2205`, using COM3 at 115200 baud. Alpha11 is installed in Bank 1.
Banks 0, 2, and 3 were not written. The board was left at alpha11's `B1> `
prompt with an erased/disabled configuration block, and COM3 was released.

## Firmware installation and readback

STR8-N 1.35 in Bank 3 installed alpha11 sectors E-F into Bank 1 and reported
`OK`. `J1` then displayed:

```text
STR8-N 2.0a11 B1
B1>
```

The `?` output contained the corrected proposed form:

```text
C [0|1 0-3 addr delay]
```

`C` reported `No config`. `D F000 F034` showed the `SN 02 00` signature,
sixteen public JMP entries, and the shared RTS at `$F034`.

The complete `$E000-$FFFF` display produced 512 unique rows and 8,192 bytes.
The parsed readback matched the candidate BIN exactly, with zero differing
bytes:

| Artifact | SHA-256 |
| --- | --- |
| Alpha11 S19 | `DDF05E86C9222BABCBAE746B414ED6739B21310E6ACEEDD3F3F0A8D92745ABAD` |
| Alpha11 BIN and board readback | `2C700B803DD172D30EC42A95C3CA317244FBB6F319E9D8C1CA3404B5F4E9625D` |

## RAM-only BRK/IRQ probe

The alpha11 build emits a 497-byte S19 probe at `$2000`. It was loaded through
`L`, which reported `Entry 2000`, and started with `G 2000`. The probe:

- installed temporary BRK and IRQ pointers at `$7E02-$7E05`;
- executed a real BRK through the resident hardware vector and v2 dispatcher;
- generated a real VIA1 Timer-1 IRQ through the resident hardware vector;
- checked BRK/IRQ separation through the saved B flag;
- checked A, X, Y, stack position, saved status, and RTI return;
- disabled and acknowledged Timer 1, restored ACR and timer latches;
- restored both handler pointers and returned through public HOLD `$F007`.

The board reported:

```text
V2 BRK / VIA1 IRQ / A-X-Y / STACK / RTI: PASS

STR8-N 2.0a11 B1
B1>
```

Afterward, `$7E00-$7E09` contained five identical default pointers to `$7E57`,
and `C` still reported `No config`. The probe performs no flash writes. Its
S19 SHA-256 is
`4F934153AD4B837CE597DEDCD584666D36E6902F9BEFA6E541331A64A329876E`.

The host model also passed the probe's success, IRQ-timeout failure, and
already-enabled-VIA refusal paths. The complete alpha11 host run contains six
suites and 34 test groups.

## RAM-only physical NMI probe

A separate 346-byte probe was loaded at `$2000`. It used the monitor's NMI
gate while installing and later restoring the two-byte handler pointer at
`$7E00`, printed `PRESS NMI`, and waited for the board's physical NMI button.
The first unattended window timed out safely and returned through HOLD. During
the second window the operator pressed NMI once, producing:

```text
V2 NMI / A-X-Y / STACK / RTI: PASS

STR8-N 2.0a11 B1
B1>
```

The probe verified dispatch through the resident NMI hardware vector and RAM
pointer, A/X/Y preservation, balanced stack state, hardware-interrupt B flag,
decimal state, and RTI return. It then restored the original pointer and
cleared the publication gate. `$7E00-$7E09` again contained five `$7E57`
default pointers, and `C` still reported `No config`. The NMI probe performs no
flash writes. Its S19 SHA-256 is
`CFC66BC46B45FD1E148A9F5268939BCE6081B51777AE4E36D39C468CF9AAFDCD`.

The host model passes NMI success, shortened timeout, and busy-gate refusal.

## Evidence and remaining coverage

Local generated evidence is under `BUILD/v2-alpha11`:

- `com3-2205-alpha11-install-active.raw` and its event log;
- `com3-2205-alpha11-e000-ffff-readback.bin` and
  `com3-2205-alpha11-readback-result.json`;
- `com3-2205-alpha11-interrupt-probe.raw` and its event log;
- `com3-2205-alpha11-nmi-probe.raw` and its event log.

These files are ignored build evidence, not committed source artifacts.
Flash-busy interrupt behavior, v2 `I`, injected flash failures, physical-reset
bank selection, and native-mode W65C816 paths remain to be qualified.
