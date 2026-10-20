# DBG1 v1g candidate r5: hardware passed, promotion held

This packaging revision adds the completed **2604 and 2609 hardware requalification** to the unchanged v1g firmware and installer. `r5` is a distribution revision; `v1g` remains the internal firmware build label, generation 50, displayed `2.0rc1`, ASM 0.5 and BRK ABI 1.

Scope is RAM debugging on **65C02 and 65C816 E=1**. Native applications/debugging remain excluded. No application RAM capacity is reserved for DBG1.

## Recorded qualification

| Board | CPU | Monitor slots | Registration scenarios | BRK $82/$84 checks | Breakpoint hits | Verified transfers |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 2604 | 65C02 | A and B, before/after rollback | 72 | 84 | 64 | 44 |
| 2609 | 65C816 E=1 | A and B, before/after rollback | 72 | 84 | 64 | 44 |
| Total | | | 144 | 168 | 128 | 88 |

Both boards passed automatic BRK entry, shared D/M/U, C/S/N, all eight persistent breakpoints, system/user registrations, MAINT and supported-app checks, plus rollback/reinstall. All four flash banks were checked after every transaction. Their original full 25,344-byte application RAM and original monitor preferences were restored at qualification closeout; RTC controls/trims were preserved. No hardware-test failure occurred. Two five-minute waits for physical RESET expired without writes and were resumed after the operator pressed the button; those waits are recorded separately.

The **separately authorized three-hour v1g soak is running** as of this archive's status snapshot. Its completion and final drift review remain pending. The boards' RAM is in use by that runner and will be restored by it after the workload. This archive does not acquire later results automatically. **Promotion remains held.**

The preceding v1f soak was safely stopped at the owner's request after 2 h 33 min 11.859 s; its restoration and drift snapshots passed. That partial run is not a six-hour pass and does not qualify v1g. Earlier v1e/v1f results remain separate historical evidence.

## Verify without accessing a board

Check the adjacent ZIP `.sha256`, extract into a new directory and run:

```text
python verify_package.py
```

The standard-library verifier opens no ports. It checks the inventory, exact firmware/kit, offline evidence, both-board hardware receipts, tested manual hashes and the unqualified soak/drift state. See [board results](docs/rc1/DEBUGGER_BOARD_RESULTS.md), [ASM/BRK results supplement](docs/rc1/ASM_DBG1_REQUALIFICATION.md), [debugger commands](docs/rc1/DEBUGGER_GUIDE.md) and [install/rollback](INSTALL_ROLLBACK.md).

## Image and package contents

Firmware SHA-256: `6a64a5d0d1c50c732dcfc2e9a2919ea697b95f03b7a9cf9aead7c9e6b88f8b6b`.

The `$82` fix rejects IDs outside `$C0-$FE` before lookup. The `$84` fix completes counted text before advancing beyond its last byte. Offline evidence retains 88 original edge checks, 7,256 expanded cases, 72 registration scenarios, 16 documented ASM example executions and 21 installer-model groups. Only B1:A000-AFFF differs from v1f: 3,975 code bytes plus two CRC bytes, 119 bytes free.

| Path | Contents |
| --- | --- |
| `install/` | Unchanged tested kit; nine firmware sectors, eleven transfers per transaction |
| `docs/rc1/` | RC1/debugger documentation and ASM/BRK requalification supplement |
| `qualification/offline/` | Original model, manual, edge, registration and installer evidence |
| `qualification/hardware/` | Both boards' actual initial/final checks and transaction/boot/restore receipts |
| `qualification/soak/pending.json` | Timestamped running snapshot; no completion or final drift claim |
| `qualification/history/` | Separately identified v1f safe-stop summary |
| `diagnostics/` | Known RAM test programs, registration/edge-case source and E=1 observer |
| `firmware/`, `source/debugger/` | Exact reference image, debugger component and matching source |
| `package-manifest.json`, `SHA256SUMS.txt` | Complete inventory and hashes |

The frozen install kit's preparation-time `hardware_qualified: false` remains unchanged so its hash stays valid. Current acceptance is in this package's [qualification summary](qualification/summary.json), bound to actual hardware receipts.

The reference BIN contains defaults and is **not** a preserving updater. The kit admits exact generation-49 sources; it cannot update a currently installed generation-50 candidate directly. Its rollback returns to the captured generation-49 source. Do not operate either board while the current soak owns its port.

Private RAM/flash captures, original application bytes, serial logs, board-specific plans and vendor/B0 firmware are excluded. Tested ASM/ABI manuals remain byte-identical; their new hardware results are in the supplement. Published rc1 generation 49 and previous candidate archives are unchanged. An explicit release decision is still required after the soak and drift review.
