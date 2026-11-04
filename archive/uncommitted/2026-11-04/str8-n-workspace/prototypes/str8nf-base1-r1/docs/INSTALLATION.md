# Installation routes and preservation

Use the complete 0.3.0 operator ZIP, including its Python terminal, hosts,
prebuilt engines, manifests and guides. Reviewed source paths passed on
2512/65C02/FT245, and the unchanged rc1 existing-SNBT package route passed on
2609/65C816 emulation/FT245. Final-package live trials and packaged WDC/
programmer-F provisioning remain untested; see [release status](RELEASE_STATUS.md).

## Preserve first

Inventory CPU, bank layout, entries, resident firmware and current journal.
Retain agreeing independent complete-bank reads and original owner RAM/ZP
escrow before helpers overwrite it. Preserve attached owner storage separately.
Do not assume erased sectors or B0 are disposable. WDC firmware is backed up
from the owner's board and is not distributed in this kit.

## Select the route

| Current state | Procedure |
| --- | --- |
| WDCMONv2, blank/unrecognized C/D | [WDC capture/migrate](../migration-host/README.md): archive, admit, F if needed, then D/C |
| Byte-identical BASE1 F installed | [Live C/D provisioning](LIVE_CD_PROVISIONING.md): original escrow, fresh capture, D then C only |
| Supported b15 F with valid SNBT | [Existing-journal upgrade](JOURNAL_F_UPGRADE.md): append reservation, replace F only |
| Valid SNBT and identical BASE1 F | Keep settings/history; public provisioning is a no-op |
| Damaged/conflicting/legacy or mixed recognized history | Stop for inspected handling; first provisioning refuses conversion |

Use an explicit port and fresh private plans. Disconnect the terminal before
a CLI takes its port. No board or B0 backup destination is selected automatically.

## The 4K programmer file

firmware/payload/STR8N-F-BOOT-4096.bin is exactly **4096 bytes**, for
**B3:$F000-$FFFF**, reset entry $F004. Under standard linear 128 KiB
B0/B1/B2/B3 ordering its device offsets are **$1F000-$1FFFF**. Verify actual
programmer/device mapping. This is neither a complete bank nor a whole chip.
A preserving update must not silently erase the chip.

Verify programmed bytes, physically RESET, observe the BASE1 identity and
select S/recovery. F-only installation leaves occupied C/D unchanged.
F is golden after successful installation. Automatic recovery from erased
or interrupted F installation is outside the runtime contract.

## Journals and wear

F reads boot records but does not create/mutate the journal. Recovery and
DEMO can run without one. Saved defaults and normal opaque erase accounting
need compatible C/D records.

CONFIG I requires both C/D completely blank and never erases them. It creates
S/recovery, disabled banks, entries all 8000, zero tracked counts and unknown
prior history. Zero means no tracked erases, not unused flash.

First provisioning erases D then C and counts those attempts. WDC migration
also counts F when it changes. Programmer-installed identical F does not
manufacture a recorded F erase. Import only source-bound owner evidence.
External programmer erases are not automatically discoverable, even on a new
chip. Attempts are reserved before erasing and are not rolled back on failure.

The [2512 trial](2512_PROGRAMMER_F_CD_ACCEPTANCE.md) explicitly archived/replaced
its raw journal and imported latest counts. It does not authorize clearing
another owner's history.

## Owner images and completion

B0-B2 and B3:8/9/A/B/E are owner space. Optional monitor-shaped images may
occupy A/B, but are not required. Retained b15 MON/FLASH execution under BASE1
remains unqualified. This release supplies no mandatory MON image. Mona remains planned.

Install/verify an image before enabling it with CONFIG. OPAQUE protects C/D/F.
Keep recovery as default while replacing a boot image; save the intended
default separately. See [quick start](QUICK_START.md) and [opaque host](OPAQUE_HOST.md).

Preservation requires independent final bank comparison, original RAM/ZP
restoration and readback, REC>, and released serial ownership. An engine
message alone is insufficient. On failure retain power, backups and logs;
no blind retry, automatic rollback or extra erase is implied. 2205 stays excluded.
