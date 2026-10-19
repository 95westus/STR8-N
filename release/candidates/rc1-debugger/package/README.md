# STR8-N rc1 DBG1 tested candidate — distribution r2

This package contains the **tested generation-50 DBG1 candidate** and its
matching install/rollback tools, updated rc1/ASM manuals and board results.
It is a separate candidate distribution. The published generation-49 rc1
release, tag and ZIP are unchanged.

Scope: **RAM debugging on 65C02 and 65C816 emulation mode (E=1)**. Native
applications and native debugging are excluded. The existing startup CPU
detector is unchanged. No debugger workspace is taken from application RAM.

## Start here

1. Check the ZIP against its adjacent `.sha256` file, extract into a new folder,
   then run `python verify_package.py` from that folder.
2. Read [install/rollback instructions](INSTALL_ROLLBACK.md). Hardware transport
   uses Windows, Python 3.10+ and the pinned pyserial dependency. Verification
   and plan creation do not open serial ports.
3. Use fresh private backups for a future installation. **2604 and 2609 already
   have generation 50 installed**; the generation-49 install route will refuse
   a board already running this candidate.

## Contents

| Path | Contents |
| --- | --- |
| `install/` | Exact original hash-bound board-test kit: seven target/baseline sectors, standalone RAM transaction engine, planner, explicit-port transport and smoke programs |
| `docs/rc1/` | Updated rc1 and ASM manuals, debugger guide, BRK registration ABI and board result summary |
| `qualification/boards/` | Public result summaries for 2604 and 2609, including both slots and hashes of the original local receipts |
| `qualification/soak/` | Eight-hour board summaries and final drift offsets, uncertainty and source hashes |
| `qualification/offline/` | Original model reports plus the later manual-example checks |
| `qualification/summary.json` | Combined qualification scope and evidence identities |
| `diagnostics/emulation/` | Exact RAM-only CPU/ABI observer used on 2609; no native-mode entry |
| `firmware/` | Exact tested 96 KiB development reference image and sealed debugger component |
| `release/rc1-uchess/` | Complete credited uChess source and redistribution notice |
| `package-manifest.json`, `SHA256SUMS.txt` | File inventory, scope and SHA-256 checksums |

Use `install/board_link.py` and a freshly derived plan for preserving updates.
The development reference BIN has generic provisioning defaults; it must not
replace an existing board's full banks/settings/wear history. B0 and vendor
firmware are not distributed. Private board captures, RAM archives, serial
logs and board-specific install/rollback plans are not in this archive.

The original `install/board-test-manifest.json` and every listed kit file are
unchanged from the hardware trials. Its preparation-time flags describe the
kit before board testing; the subsequent bounded results are in
[the summary](qualification/summary.json) and
[board results](docs/rc1/DEBUGGER_BOARD_RESULTS.md).

## Manuals and results

- [Debugger: C/S/N, shared D/M/U and eight persistent breakpoints](docs/rc1/DEBUGGER_GUIDE.md)
- [ASM BRK operands and worked examples](docs/rc1/ASM_GUIDE.md#debugging-ram-programs-with-dbg1)
- [BRK services and separate system/user registrations](docs/rc1/ABI_REFERENCE.md#dbg1-brk-functions-and-registrations)
- [Both board trials and hardware/offline limits](docs/rc1/DEBUGGER_BOARD_RESULTS.md)
- [All rc1 manuals](docs/rc1/README.md)

Both MON A/B passed on both CPUs: BRK entry, C/S/N, shared D/M/U, eight
breakpoints twice per slot, ninth refusal, clears, X/HOLD cleanup and BRK 80
query. This is 64 verified breakpoint hits. Each board's original RAM and
monitor preference were restored and verified. RTC controls/trim were retained.

System/user callback registration is covered offline; the hardware smoke
checked query 80. Rollback plans were prepared and verified offline, not
executed on hardware. Native mode, interrupted-write recovery, general
occupied-bank upgrades, electrical timing and full endurance/RTC qualification
remain outside this checkpoint.

Base rc1 migration/provisioning guides retain their generation-49 scope.
Repository build/model commands in the manuals require the source checkout
and its dependencies. The archive-relative candidate upgrade procedure is
[INSTALL_ROLLBACK.md](INSTALL_ROLLBACK.md).

## Eight-hour soak and drift results

Both boards passed 431 cycles and 6,896 breakpoint hits each over
8h 00m 23.703s, without failures (2604 MON B; 2609 MON A, E=1).
Original application RAM was restored and verified again after the snapshot;
all four flash banks, settings, wear history and RTC trims were unchanged.
Final RTC offsets versus NIST were +0.950532s (2604) and +0.545367s (2609).
These are current offsets, not eight-hour drift increments. See
[measurement bounds and comparison segments](docs/rc1/DEBUGGER_BOARD_RESULTS.md#eight-hour-rc1asmdbg1-soak-and-final-rtc-snapshot),
[portable soak evidence](qualification/soak/summary.json) and
[drift evidence](qualification/soak/drift.json). The original baseline and
2609 recovery segment are retained. This bounded soak does not qualify native
mode, hardware callback registrations, full RTC accuracy or endurance.
