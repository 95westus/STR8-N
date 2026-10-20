# DBG1 v1g candidate r7: soak closed, promotion held

This packaging revision adds the verified owner-stopped **v1g R6 workload and final drift closeout** to the completed both-board hardware requalification. Firmware and installer bytes are unchanged. `r7` is a distribution revision; `v1g` remains the internal firmware build label, generation 50, displayed `2.0rc1`, ASM 0.5 and BRK ABI 1.

Scope is RAM debugging on **65C02 and 65C816 E=1**. Native applications/debugging remain excluded. No application RAM capacity is reserved for DBG1.

## Recorded qualification

| Board | CPU | Monitor slots | Registration scenarios | BRK $82/$84 checks | Breakpoint hits | Verified transfers |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 2604 | 65C02 | A and B, before/after rollback | 72 | 84 | 64 | 44 |
| 2609 | 65C816 E=1 | A and B, before/after rollback | 72 | 84 | 64 | 44 |
| Total | | | 144 | 168 | 128 | 88 |

Both boards passed automatic BRK entry, shared D/M/U, C/S/N, all eight persistent breakpoints, system/user registrations, MAINT and supported-app checks, plus rollback/reinstall. All four flash banks were checked after every transaction. Their original full 25,344-byte application RAM and original monitor preferences were restored at qualification closeout; RTC controls/trims were preserved. No hardware-test failure occurred. Two five-minute waits for physical RESET expired without writes and were resumed after the operator pressed the button; those waits are recorded separately.

The owner stopped the expanded v1g R6 continuation cleanly after **12,803.703 seconds (3 h 33 min 23.703 s) of monitored/active workload**. 2604 passed **61 cycles, 38,430 LED frames, 610 completed patterns and 976 breakpoint hits**; 2609 passed **60 cycles, 37,800 frames, 600 patterns and 960 hits**. Both original full 25,344-byte RAM images were restored and reread after final preserving drift; all four flash banks/settings were unchanged. No actual workload failure or snapshot retry occurred. The verified worker exited; no workload or RTC sampler was restarted. **Promotion remains held; native applications/debugging remain excluded.**

See [soak closeout and measurement limits](docs/rc1/DBG1_SOAK_CLOSEOUT.md) and the [machine-readable closeout](qualification/soak/summary.json). The 216.041609-second final safe closure is separate from workload time; total worker wall time was 13,019.862814 seconds. R6 had no periodic checkpoint: its owner stop preceded the next original-phase boundary. This is recorded scope, not a fixed four/eight-hour or full RTC-endurance pass.

The preceding v1f soak was safely stopped at the owner's request after 2 h 33 min 11.859 s; its restoration and drift snapshots passed. That partial run is not a six-hour pass and does not qualify v1g. Earlier v1e/v1f results remain separate historical evidence.

## Verify without accessing a board

Check the adjacent ZIP `.sha256`, extract into a new directory and run:

```text
python verify_package.py
```

The standard-library verifier opens no ports. It checks the inventory, exact firmware/kit, offline evidence, both-board hardware receipts, tested manual hashes and the source-bound clean soak/restoration/drift state. See [board results](docs/rc1/DEBUGGER_BOARD_RESULTS.md), [ASM/BRK results supplement](docs/rc1/ASM_DBG1_REQUALIFICATION.md), [debugger commands](docs/rc1/DEBUGGER_GUIDE.md) and [install/rollback](INSTALL_ROLLBACK.md).

## Image and package contents

Firmware SHA-256: `6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b`.

The `$82` fix rejects IDs outside `$C0-$FE` before lookup. The `$84` fix completes counted text before advancing beyond its last byte. Offline evidence retains 88 original edge checks, 7,256 expanded cases, 72 registration scenarios, 16 documented ASM example executions and 21 installer-model groups. Only B1:A000-AFFF differs from v1f: 3,975 code bytes plus two CRC bytes, 119 bytes free.

| Path | Contents |
| --- | --- |
| `install/` | Unchanged tested kit; nine firmware sectors, eleven transfers per transaction |
| `docs/rc1/` | RC1/debugger documentation and ASM/BRK requalification supplement |
| `qualification/offline/` | Original model, manual, edge, registration and installer evidence |
| `qualification/hardware/` | Both boards' actual initial/final checks and transaction/boot/restore receipts |
| `qualification/soak/` | Completed R6 workload, separate run history, offline/inherited scope, drift and receipt hashes |
| `diagnostics/led10/` | Four exact CPU-qualified ten-pattern ASM sources and case images |
| `qualification/history/` | Separately identified v1f safe-stop summary |
| `diagnostics/` | Known RAM test programs, registration/edge-case source and E=1 observer |
| `firmware/`, `source/debugger/` | Exact reference image, debugger component and matching source |
| `package-manifest.json`, `SHA256SUMS.txt` | Complete inventory and hashes |

The frozen install kit's preparation-time `hardware_qualified: false` remains unchanged so its hash stays valid. Current acceptance is in this package's [qualification summary](qualification/summary.json), bound to actual hardware receipts.

The reference BIN contains defaults and is **not** a preserving updater. The kit admits exact generation-49 sources; it cannot update a currently installed generation-50 candidate directly. Its rollback returns to the captured generation-49 source. The qualified R6 worker has exited with RAM restored. Installation still requires a separately authorized trial and fresh source-bound backups/plans.

Private RAM/flash captures, original application bytes, serial logs, board-specific plans and vendor/B0 firmware are excluded. Tested ASM/ABI manuals remain byte-identical; their new hardware results are in the supplement. Published rc1 generation 49 and previous candidate archives are unchanged. An explicit promotion/release decision is still required; packaging does not promote, publish or access a board.
