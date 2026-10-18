# rc1 power-fail UTC board update — October 18, 2026 (CDT)

Both 2604 and 2609 now run **v2.0rc1, generation 49, package revision 2**.
The installed RTC/banner sector is from the published complete release ZIP;
the original release tag and ZIP were not changed by this hardware update.
Both boards printed `[power-fail UTC]` directly from verified flash and
returned to a usable monitor. MON A/B remain valid; apps and monitor images
were not replaced. No additional physical RESET was needed on the final path.

| Board | Observed CPU/runtime | Retained preference | RTC control | Trim register | B3:8 erase count (decimal) |
|---|---|---|---|---|---|
| 2604 | 65C02 | B | `$00` | `$0C` | 9 → 10 |
| 2609 | 65C816 E=1 | A | `$80` | `$0E` | 20 → 21 |

All other 31 erase counters remained unchanged on each board. Both used the
same RAM updater and the same published banner payload. The update used the
existing rc1 wear-accounted worker to advance the actual journal before the
single B3:8 erase, program the sector and compare every byte. On-device
fingerprints also pinned the executable source, resident worker and staged
payload. The printed UTC heading was read from the installed flash.

Read-only C/P, VERSION, APPS/T, TIME and CLOCK STATUS checks passed; both monitor
slots remained valid. Configuration/preferences, RTC control, trim, oscillator
start and backup-enable state matched before/after. The 816 observer confirmed
E=1 with zero DBR/PBR/direct page and no native-mode application execution.
Saved application-RAM archives were loaded with acknowledgment; extra host
memory readbacks were disabled. This is not a claim of fresh host RAM verification.

## Source-guard diagnosis and retained evidence

An initial full-bank plan refused before any sector transfer. Its read-only
diagnostic identified B3 but failed to return; the owner supplied RESET and
the failed source/logs were retained. A narrower attempt refused safely and
returned normally. Sector fingerprints then isolated the difference to the
persistent binding/name/offset tail at B3:9C00-9FFF; the sealed 9000-9BFF
executable and other firmware sectors matched. The tail had incorrectly been
pinned to a historical image. It is now preserved as mutable board metadata,
while executable bytes remain pinned. Actual C/D journals are validated and
updated by the unchanged firmware rather than reconstructed on the host.

Six final instruction-model cases passed: updates on both exact board images
with changed journals/settings, plus bad executable, bad RAM payload, bad worker
and missing-journal refusals. Success/refusal paths returned to a usable prompt.
The boot-menu's pure delay loop was accelerated; this was not a timing test.
Prior refused attempts were not relabeled as passes. Their borrowed RAM is
covered by the final acknowledged archive restoration; no restore is pending.

The maintenance harnesses under `tools` require owner-local fixtures/receipts;
they are not generic customer migration launchers. Private banks, device data,
serial logs and evidence stay outside Git and the public release ZIP.

Both boards remain powered on and idle. 2205/2512 remain off. Soaks and RTC
sampling stay stopped; the original RTC baseline is unchanged. RTC qualification,
native 816 applications/tests, ACIA and crypto remain deferred. v2.1 ABI/metadata
organization and LED/timer discovery remain future development.
