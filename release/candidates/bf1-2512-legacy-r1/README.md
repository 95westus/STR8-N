# bf1 legacy migration candidate for 2512

This is a separate, offline-only converter candidate. It does not change the
generation-48 bf1 firmware set or the active 2604/2609 soak programs. Both
WDCMONV2-to-bf1 and published v2.0b4-to-bf1 require their own hardware acceptance
on 2512 before publication. Neither has hardware acceptance yet.

The candidate builds a 24-row RAM installer with an all-bank preflight and a
wear reservation before the first erase. Source staging, migration, restoration
of historical source, and restoration of the original beta35 payload each carry
forward conservative erase counts. No old clean journal or provisioning image
may reset that history. Current B0 and B1 user programs remain unchanged.

The WDC source is the exact owner-local 2512 captured diagnostic/monitor layout.
Its diagnostic code is source-owned and replaced during conversion; its private
preimage is retained. The current B0 is different and is never substituted for
that historical source or overwritten. The source-stage journal is an explicit
sidecar in otherwise unused C/D sectors; WDCMON itself does not maintain wear
history. This is not an admission of arbitrary vendor images.

The beta4 source uses the exact published generation-13 monitors, recovery E/F
and MAINT 1.5 record, with A generation 13 explicitly selected for this rehearsal.
Other beta4 source preferences are outside this checkpoint. Both bf1 destination
monitor slots are exercised. The migration includes provider-layout conversion.
Occupied destinations and altered source code must refuse. Source staging
temporarily uses the old B3 layout; current identity/policy/history bytes from
B3:9C00-9FFF are held in the hash-bound host backup and restored into the bf1
layout. EEPROM, retained SRAM, clocks and trims are not written.

Both routes change the recovery core. Fixed F is the last payload written;
durable selection follows. Interruption recovery tests resume from exact CPU
mutation preimages with new conservative wear reservations. These tests do not
promise a bootable board during every core erase/program interruption. Some
cut states need retained RAM execution or an external programmer. Hardware use
still needs explicit source/backup admission, verified transport, owner RESET
coordination and post-install preservation checks. There is no live launcher.

`bf1_2512_legacy_recovery.py` admits recovery only against a hash-bound CPU trace
certificate and an exact replayed cut preimage. A new unrelated byte, wrong cut
boundary or altered certificate refuses. The lower-level semantic planner's
cut-state option is not a hardware admission mechanism.

Build a fresh directory with `tools/build_bf1_2512_legacy_installer.py --out`;
qualify it with `tools/qualify_bf1_2512_legacy.py --build ... --out ...`.
Every output directory must be new. Preserve failed runs and original payloads.
The original four-board RTC baseline remains immutable. Native 816 application
testing, ACIA and crypto remain deferred.
