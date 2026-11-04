# Native TIME reads live trim

Installed and qualified on2512 and2609, October31,2026. Both A/B slots are gD,
default remains B/gD, and ports are released at B3>. Live nine-sample NTP
bursts on each board verified trim/control; the existing hourly collector now
uses these readings. All249 earlier campaign points, events and baselines are
retained. F, RTC settings and fresh owner RAM/ZP are preserved.

MON gD extends the native TIME snapshot from MCP79411 registers00-06 to00-08,
then rereads seconds for coherence. It retains the existing STATUS calendar
layout and the unchanged Foundation/PR05 interface.

```text
B3> TIME
RTCC: 2026-10-31 23:35:55 flags $28 trim $0C ctrl $80
```

`trim` is the raw OSCTRIM register; `ctrl` is the raw control register. The
collector decodes signed-magnitude trim and records the actual control mode.
For the current boards,2512's $0C is-12 steps and2609's $0E is-14 steps;
both have control$80, coarse OFF. The full CLOCK TRIM/STATUS commands remain
available for the signed display and detailed RTC information.

The shared `MON-UI1-GD-TIME-TRIM` collector reads these fields on all nine
TIME samples in every burst. It rejects missing fields or a trim/control change
within the burst. It records `trim_verified=true` and `control_verified=true`
only for fresh, audited observations. It never substitutes an immutable
baseline value for a current register read. Both REC> and B3> are admitted and
the original prompt is restored; active applications are left alone.

The collector and firmware do not set RTC time/trim/control, acknowledge
power-fail flags, scan/write EEPROM PF history, or touch SRAM/WORKSPACE.
Register-address-pointer writes and temporary VIA bus ownership are necessary
for I2C reads. Collection uploads no RAM helper. Older reader files, saved
points and verification flags remain unchanged; historical unverified samples
are not relabelled. The baseline and existing cadence continue.

Trim recommendations use the freshly observed setting. Fine-mode step-size
advice is withheld in coarse mode. Current-latch observation still does not
constitute a fresh EEPROM PF-history scan or proof of continuous power.
No automatic trim adjustment is introduced.

The gD ROM body is3957 bytes in each4096-byte MON slot. A/B retain identical
commands. F stays STR8N-F0.3.0 g1 / BASE1 / PR05, unchanged. MAINT/CLOCK/FLASH,
STATUS, PROGRAM, board names and local display offsets are unchanged.
Published downloads and release kit are separate from this board update.

The [approved flash/history review](MON_TIME_TRIM_SCOPE.md) details A/B
replacement, same-B generation binding and2609's native D rotation. Private
RAM, installed and NTP-admission receipts are under output/qualification,
with prefixes2512-MON-trim,2609-MON-trim andMON-trim-RTC-admission.
