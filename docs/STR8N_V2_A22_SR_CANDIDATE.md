# STR8-N 2.0a22 S/R/T candidate

This is a source and scoped COM3 board-tested candidate, not a full release.
The first installed F image failed the operator's cold USB start check and
required physical RESET. The repaired F image installed on COM3 gives enabled
autostart a headless path with its configured hold window, independent of USB.
Monitor boot prints dots once FT245 is ready. A physical USB power off/on
check, with no RESET pressed, reached the Bank 1 HIMON prompt. The configured
hold interval was checked in the host timing model, since COM3 appears only
after USB enumeration. A later source refinement adds nonblocking dots during
enabled autostart; that matched E/F build is installed on COM3 and its warm
restart and S/R/T checks passed. A subsequent receive-only capture recorded
148 dots and Bank 0 startup after USB power was turned off and back on
without pressing RESET. The scoped cold USB power-on check passed.
The frozen 2.0a21 source and outputs are unchanged. Build with
`python tools/build_v2_a22.py`; the artifacts are under `BUILD/v2-alpha22/`.
The [COM3 installation report](STR8N_V2_A22_COM3_INSTALL_2026-09-26.md)
records the physical installation and its limits.
The [COM3 regression sweep](STR8N_V2_A22_REGRESSION_2026-09-26.md) records
the full host gates and the scoped W65C02 board checks.

## Placement and recovery boundary

The existing monitor remains in Bank 3 `$F000-$FFFF`. Its reset path does not
read or execute the extension. `S`, `R`, and `T` dispatch only when Bank 3 is
resident and the `$E800` descriptor has `SR` and ABI version 1; otherwise they
report `SR unavailable`. Ordinary Bank 3 `F` and `I` operations reject the E
sector. `C` still stages the entire E sector from its current contents before
updating configuration.

The extension begins at `$E800` and must end by `$EEFF`. `$E000-$E7FF` stays
erased in this candidate. `$EF00-$EFFF` remains the configuration reservation,
including the existing 16-byte pocket at `$EFF0-$EFFF`. The build currently
measures 1,208 extension bytes and 4,064 F-sector resident bytes; F ends at
`$FFE0`, immediately before vectors. The RAM worker remains 759 bytes.

On enabled autostart, the current source probes FT245 once per configured
tenth-second tick. It prints one dot when the transmit FIFO is ready, including
when USB becomes ready after reset. It skips dots while USB is unavailable or
the FIFO is full, and still hands off when the hold window expires. It never
initializes ACIA on this path. The monitor path keeps its 160-dot readiness
wait. This refinement's F SHA-256 is
`1bae74704dd5c66ca34fa8d3b1bdfa9f2cf65ffab72a724a8eba87888420a439`;
its E extension code SHA-256 is
`fcb0a253fa802c5e44ce48bba22c4b004a49b6dfe8b6563a9d8891ea75875401`.
E calls private F addresses, so both sectors must be updated as a matched
pair before board testing this refinement.

## Console commands

```text
S <bank 0-3> <flash address> <RAM start> <RAM end> [label]
R <bank 0-3> <flash address>
T <bank 0-3>
```

Numeric fields are hexadecimal except the bank digit. The RAM end is
inclusive. For example, `S 3 8FF0 2000 201F TEST` writes a 24-byte header at
`$8FF0` followed by 32 bytes of RAM from `$2000-$201F`; `R 3 8FF0` restores
those bytes without executing them. `T 3` lists recognized Bank 3 records as
`FLASH RAMSTART-RAMEND LENGTH C|P LABEL`, with `C` complete and `P` pending.
The label is optional, at most 16 non-space printable ASCII characters. The
line input limit is 40 characters to accommodate the complete command.

Storage is `$8000-$DFFF` in the selected bank. The *whole* header and payload
must fit; byte addresses and sector crossings are allowed. Save validates the
RAM source within `$0200-$68FF`, then checks that **every byte of the proposed
record** is `$FF` before any write. It snapshots each affected sector into the
existing `$6900-$78FF` buffer, changes only record bytes, and uses the
existing `$7900-$7BFE` RAM worker to program and verify without erasing.
Other bytes in those sectors are preserved. There is no automatic placement.

Restore validates the signature, version, complete state, nonzero length,
storage extent, label encoding, and original RAM destination before copying.
It does not check for overlap with other application code and does not start
the restored program. The format has no payload checksum: successful flash
programming is verified at save time, but later payload corruption is not
detected by `R` or `T`.

## Record format and interrupted saves

All words are little endian. The payload starts immediately after byte 23.

| Offset | Size | Meaning |
| --- | ---: | --- |
| 0 | 2 | ASCII `SR` |
| 2 | 1 | Format version 1 |
| 3 | 1 | `$7F` pending, programmed to `$3F` complete after payload verification |
| 4 | 2 | Original RAM start |
| 6 | 2 | Payload length, excluding header |
| 8 | 16 | Label, zero padded; all zero means unnamed |

An interrupted save can leave a pending or incomplete header and programmed
payload cells. `R` refuses anything other than a complete valid header. `T`
shows a pending record only when enough metadata is intact to validate its
extent. The first version never automatically reuses such space. A future
allocator must treat unidentified programmed bytes conservatively.

## Separate extension ABI

The a21 core ABI and its published RAM entries retain their addresses and
behavior. At `$E800`, the extension has an eight-byte descriptor (`SR`, ABI
version `$01`, feature byte `$01`, header size `$18`, three reserved bytes)
followed by three-byte `JMP` slots:

| Entry | Function |
| --- | --- |
| `$E808` | Console `S` |
| `$E80B` | Console `R` |
| `$E80E` | Console `T` |
| `$E811` | Application `SAVE` |
| `$E814` | Application `RESTORE` |

For application calls, A/X hold the low/high byte of a 23-byte request block
in application RAM. Its bytes are `bank[1], flash[2], RAM start[2], RAM
end[2], label[16]`. `RESTORE` uses only bank and flash. `SAVE` copies the
request before modifying flash; `RESTORE` copies it before modifying RAM.
Success returns carry set and A=`$00`. Failure returns carry clear and A=`$01`
for invalid arguments, `$02` for occupied flash, `$03` for flash failure, or
`$04` for an invalid/incomplete record. X, Y, and monitor scratch are clobbered.
The selected-bank setting is restored on return; the physical resident Bank 3
is visible on entry and exit. IRQ is disabled and decimal mode clear. On an
816, calls use emulation mode, DBR=0, and PBR=0. Calls are not reentrant. A
caller of `RESTORE` must execute outside the destination RAM range.

The extension's private scratch is `$7D90-$7DCA`; applications must respect
the monitor RAM map. Applications must not call the private RAM flash worker.

## Installation and qualification

The build emits an E-only image/S19 and a matching F-sector image, as well as
the dense E-F image and the existing style of guarded F-top updater. The
host-only `tools/prepare_v2_a22_sr_upgrade.py` accepts a complete Bank-3 E/F
or full-bank raw readback, requires a supported exact alpha21 F identity and
an erased `$E800-$EEFF`,
then emits a full E-sector S19 that changes only `$E800-$EEFF`. It preserves
the read-back `$E000-$E7FF` and `$EF00-$EFFF` bytes and records hashes in a
manifest. This is preparation, not a board installer.

The a22 F-top updater embeds the exact source-built alpha21 F image and
rejects a different old F before offering either write confirmation. It
backs up old B3:F in B2:F before changing B3:F. The COM3 sequence installed
E first, verified it byte for byte, then installed F; final B3 E/F and B2
readbacks passed exact comparisons. The updater is matched to the
source-built alpha21 variant, not the other supported preparation identity.
A later F relink changed private monitor entry addresses called by the E
extension. Its F-only repair left S/R/T incompatible until a matching E
repair was installed. Treat E and F as a matched build for every update;
the F repair builder now rejects a changed E image unless a paired E repair
is explicitly specified. Complete COM3 readback and `T`/`R` confirmed the
repaired pair. A configuration update then enabled Bank 1 autostart and
preserved all E extension and F code bytes.
A raw dense E-F image would overwrite live configuration bytes. The two
sector writes are not atomic; other boards and interruption cases require
their own recovery qualification.

`python tools/test_v2_a22_sr.py`, `python tools/test_v2_a22_e_install.py`,
`python tools/test_v2_a22_e_repair.py`, and
`python tools/test_v2_a22_top_update.py` run the candidate and installation
paths in the banked flash model.
It covers byte-offset and crossing-sector saves, exact restore, occupied-range
rejection without mutation, a 16-character label, embedded `SR` bytes in a
payload, pending records, the storage/RAM endpoint, Bank 3 E protection, and
boot with the extension missing, configuration updates preserving E code, and
direct application ABI calls. The COM3 run adds one physical S/R/T and update
qualification and a Bank 1 cold USB power-on check for the previously
installed image. The later dot refinement has host-model coverage, a scoped
COM3 warm-restart check, and a capture of dots followed by Bank 0 startup.
The operator confirmed this capture followed a power cycle without RESET.
This does not establish a full release across boards, consoles, or other
reset/power-cycle conditions.

## Later expansion

Name lookup, automatic placement, payload checksums, and broader storage
devices require new feature/format versions. `T` provides the initial scanner
for name lookup and listing. An allocator also needs an S/R-only allocation
area or explicit ownership map; an `$FF` run inside an existing record's
payload is not free. `$E000-$E7FF` remains available for later search/fill or
other small recovery utilities after their fit is measured.
