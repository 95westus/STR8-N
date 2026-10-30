# Shared MON/tool return modes

October 30, 2026. MON g0000000A / WB2 g8 / services g6 and native tools are
[installed on 2512](2512_NATIVE_UTILITIES_ACCEPTANCE.md). Frozen
Foundation v0.3.0 BASE1/PR05 and its public HOLD remain byte-identical.

## Meaning

| Mode | Session state | Display | Entry |
| --- | --- | --- | --- |
| HOLD / CLEAR | Initialize the active monitor's session state | Normal identity/status | Existing public HOLD, unchanged: Foundation launches the normal MON entry |
| HOLD / RETAIN | Keep monitor session, selected data bank and last RTC sample | Normal identity/status | Optional MON UI/1 retain entry |
| HOLD / BYPASS | Keep the same state as RETAIN | Go directly to Bx>; omit banner/status | Optional MON UI/1 quiet entry; chosen for workbench Q |

CLEAR is not a RAM erase or a boot-setting reset. These modes never imply
clearing owner RAM/ZP, programs, persistent configuration or journal history.
A retained RTC value is the last sample and remains labelled as a sample;
TIME requests a fresh observation. Return does not set the clock.

BYPASS means **quiet monitor return**, as selected by the owner. It does not
mean enter REC>, run another image, change the default or skip validation.
MON Q remains the deliberate path to REC>.

Existing applications continue to use public HOLD with its existing register
contract. A value in A is not reinterpreted as a mode flag. Explicit additional
entries sit above F; this is not a new Foundation ABI or a PR05 replacement.

## Shared command behavior

The posted g8 transcript exposed two connected defects: workbench rejected
V/TIME, and its public-HOLD exit reentered M_START, clearing the monitor's
6A00 session cache. New matching components use one MON identity and RTC
implementation:

```text
B3> VERSION          monitor/Foundation identity and current sampled status
B3> TIME             one fresh RTCC line
B3> MAINT            matching workbench; preserves selected data bank
WORKBENCH> VERSION   same MON identity/status, plus workbench identity
WORKBENCH> V         exact alias
WORKBENCH> TIME      the same RTC read and cache as MON
WORKBENCH> Q
B3>                 quiet return, cached sample retained
```

Workbench TIME shares the monitor reader/cache. The full native CLOCK app now
uses its b35-derived driver/gateway and its own samples; VERSION uses the common
monitor identity. Returning preserves the monitor's last labelled sample, not
an implicit new RTC read. Native app/BOOT acceptance and remaining write/parity
gates are in the [operator manual](NATIVE_UTILITIES_MANUAL.md).

## Private UI/1 interface and admission

The MI image's reserved, CRC-covered area holds descriptor `UI 01 count PR05`
at offset48 hex and a vector table at20 hex. Operations0..5 are VERSION,
TIME, retain/status return, RTC sample, RTC display and bypass/quiet return.
An older caller accepts a compatible descriptor with at least its required
vector count. New operations must not change existing operation meanings.

The tool validates active A/B identity, PR05, payload length, the complete MI
CRC, descriptor/version/count, and target bounds before indirect execution.
There are no owner ZP allocations or new permanent RAM regions. The existing
MON6A00 and explicitly borrowed workbench RAM remain their owners. Calls are
foreground only, B3 visible, E=1 with D/DBR/PBR=0, SEI/CLD and system scratch
E0-FF clobbered. Return callers reset their console/stack; Q passes the chosen
data bank back to MON before entering the quiet path.

An intact older MI without UI/1 can use legacy HOLD for Q. A failed MI/CRC
admission returns to golden recovery instead of jumping into an unadmitted
monitor. Shared VERSION/TIME calls report a matching-module error rather than
using an unchecked pointer. The shipping installer must admit a matching stack.

The workbench has a CRC-covered WG/generation marker. Services g5 validates
it in addition to the MW2 header and CRC, preventing a valid older cache from
silently supplying an obsolete command set. The loader executable and PROGRAM
provider were reused; the bundle generation field advances with the new bundle.

## Historical UI/1 build checkpoint

MON g0000000A built once: each slot has 4 bytes free after its128-byte header/
reservation. WB2 g7 has 224 free code bytes; services g5 r2 has 58 free bytes.
One workbench assembly attempt failed because WDC disallowed a relocatable
EQU alias. Replacing it with a real label required one corrective build.
That initial build-only checkpoint involved no CPU model, board access, flash
write, RTC write or published-asset change. Later native acceptance is separate. The failed build log is retained privately, not disguised as a pass.

Required live cases include global VERSION/TIME in each prompt, exact-name
refusal, CLOCK refresh/cache, bank retention, quiet Q, explicit legacy CLEAR,
retained/status return, corrupted MI/descriptor/vector refusal, and stale-cache
reload. Use fresh owner escrow and reviewed write targets. Build/CRC evidence
does not replace these operator workflows or complete the unified release.

Services r2 also rechecks the freshly loaded module. The initial successful
services build lacked this second guard; that required one corrective build.
The corrected [candidate](../monitors/candidates/services-g00000005-ui1-r2/README.md)
is the current build-only artifact. Mode names describe private return entries,
not new console commands.
