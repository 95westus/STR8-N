# Minimal N/F release contract

Accepted direction: 2026-10-28. The reviewed 2512 cases now passed; see
[closeout status](RELEASE_STATUS.md). This contract does not expand their scope.
The 0.3.0 release includes the Python serial terminal and unchanged migration
hosts. The rc1 existing-SNBT ZIP route passed on 2609; final-package live trials
and other packaged routes remain untested. Mona is a planned optional image,
not a new F dependency or ABI change.

> 4KB of firmware. One board. Up to four boot environments.

Compatible, user-supplied images run one at a time on shared CPU/RAM/peripherals.
Exact loader and
owner-RAM preservation ranges remain defined by their separate protocols.

## Golden-F recovery boundary

Owner direction: "stay in rec>" and "we assume f is golden." The installed,
verified frozen F is the recovery anchor for BASE1 runtime. Normal recovery
procedures leave B3:F intact and use REC> to load matching RAM tools. Recovery
qualification concerns RAM transfers, opaque images and the C/D journal.

Deliberately erasing or partly programming F is outside this runtime contract.
Interrupted-F fault tests remain NOT RUN; their runtime gate is closed by this
explicit scope assumption, not by a hardware pass. This changes no F bytes,
generation, ABI or hardware write protection. See the
[current B3 scope](GOLDEN_F_RECOVERY_SCOPE.md).

Initial programmer/WDC installation must verify F and reach REC> before this
assumption applies. A failure while first installing or explicitly upgrading F
still needs a separately admitted repair path; automatic recovery from that
failure has not been qualified. The installation and upgrade tools remain
separate from ordinary recovery with golden F.

## Persistent footprint

Only B3:F and the C/D journal belong to N/F. B0-B2 and B3:8/9/A/B/E are user
image space. The minimum installation writes no MON, FLASH example, provider,
menu, language, RTC configuration, EEPROM or external SRAM. Those are optional
later images. Journaled operation means persistent boot settings and durable
erase-attempt accounting; it is not an image catalogue or automatic image rollback.

The current F still has optional A/B monitor-selection compatibility code. A/B
monitor-shaped images are optional occupants of user sectors, not mandatory
system reservations. An opaque image at B3:A or B boots through bank `3` and its
configured entry, rather than through the monitor-selection letters `A`/`B`.

## Two installation routes

1. Programmer: program the exact 4096-byte F BIN at B3:F, verify the bytes and
   reset to recovery. Under standard linear 128 KiB bank ordering the offset
   is 1F000; the operator must match their programmer/device wiring. This is not
   a whole-device image. Provision C/D through a RAM tool afterward.
2. WDCMONv2: upload and independently read back a RAM migrator, then perform a
   preimage-bound, verbose F/C/D conversion. No existing N/F ROM routine is
   assumed. A shared engine can provision C/D when F is already identical.

For a factory conversion, original complete bank images and affected owner RAM
must be saved privately before uploading. Original WDC firmware is captured
from that owner's device and is not included in the release. No automatic B0
copy consumes user space.

## Journal policy

Classify C/D before writing: blank; compatible valid SNBT; vendor/other occupied;
or damaged/ambiguous journal. Preserve compatible owner records and their
history. Never silently convert a damaged/ambiguous journal or reset owner
counts. An unsupported upgrade path must stop with a specific explanation.

Explicit factory provisioning creates recovery default `S`, enabled-bank mask
00, and unknown prior lifetime history. It counts this run's own erase
attempts. The host saves an erase-intent receipt before permitting each erase.
F is programmed/verified first, then D and C; journal commit bytes are last.
The procedure must distinguish a prepared image, an attempted erase, a verified
sector and a physically observed recovery boot. They are different milestones.

The same journal engine must be usable after programmer installation. Sending
CONFIG `I` against nonblank factory C/D is not a substitute for provisioning.

## Operator output

The migration log names the CPU/route, source hashes, private backup paths,
4096-byte F identity, exact destinations, each receive/erase/program/readback
phase, journal record/commit status, unchanged regions, and the next recovery
action on failure. Print progress between bounded operations; verbose output
must not be inserted into a binary transfer frame.

Do not report preservation complete until readback and promised owner-RAM
restoration are complete. Do not report a physical RESET pass from a software
jump. A failed/incomplete operation retains its receipt and does not retry or
replay automatically.

## Ordinary opaque use

Load the matching BASE1 RAM installer at 0200 through recovery `L`. Raw L waits
indefinitely for its first byte; initial Ctrl-C cancels. After data starts,
three seconds of idle runs the received prefix. It has no transfer length or
CRC; the matching host/procedure must state that boundary accurately.

The OIP1 host selects an explicit target, saves and verifies its preimage,
transfers a CRC-protected sector, and independently reads the result back.
The device reserves its erase attempt in the journal before issuing the erase.
B3:C/D/F remain inadmissible to ordinary OPAQUE reads/writes. CONFIG separately
saves bank enablement, entry and default; installing bytes does not select a
default. Before replacing a default boot image, select recovery and retain it
until the replacement has passed verification.

Example for an installed opaque image at B3:A000:

```text
RAM CONFIG ? B C I W Q> B 3 A000
RAM CONFIG ? B C I W Q> C 3
RAM CONFIG ? B C I W Q> Q
```

The commands above each require Enter and save immediately. `C S` returns
the default to recovery. User images
may call the fixed RAM RESET entry to reopen the startup chooser; HOLD resumes
an admitted monitor and is not the minimum F-only return contract.
