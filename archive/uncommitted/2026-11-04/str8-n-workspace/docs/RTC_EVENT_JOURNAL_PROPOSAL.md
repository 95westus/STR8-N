# RTC event journal for a future version

Recorded October 26, 2026 at the owner's request. Backlog/design only;
implementation, format migration and deployment remain future work.

Record detected clock/calendar/weekday mismatches separately from corrections.
Record every attempted time SET and trim/control change, including no-op,
verified, failed and interrupted outcomes. A successful SET or trim change
starts a new drift-analysis segment; preserve earlier anchors and observations.

Each logical event needs a sequence, type, format version, timestamp quality,
old/new values, reason, operation result, integrity check and publication state.
Use trusted external UTC when available and also retain the RTC's own reading.
When the RTC is suspect or no reference exists, mark the timestamp uncertain;
do not present a guessed UTC time as measured. Retain reference uncertainty,
board/device identity and firmware/source provenance in the complete host log.

For a correction, durably record intent before the device write, then append
the observed/readback result. An interrupted intent must remain distinguishable
from a verified correction. Sequence ordering must remain usable if UTC moves
backward. Record a persistent mismatch once per state change, plus its resolution,
rather than writing EEPROM on every read or boot.

Keep a complete append-only host history. A compact onboard tail is desirable,
but the MCP79411's 128 ordinary EEPROM bytes are already owned by four 32-byte
PF records at 00-7F. Do not claim free space, reduce PF retention silently, or
use the protected factory EUI area. Specify a versioned allocation and preserving
migration, or allocate other nonvolatile storage, before adding onboard events.
Use the existing CRC/readback/commit-last discipline and bounded page writes;
qualify interrupted records, rotation, full storage, failed readback and migration.

For the 2609 observation, distinguish the October 26 mismatch detection from
the earliest supporting bad weekday in the October 18 UTC recovery receipt.
The time-setting cause is unconfirmed; do not log an inferred cause as fact.
Archive its current PF and raw RTC evidence before the separately authorized
weekday correction. The correction does not authorize changing UTC or trim.

References: [current EEPROM allocation](../src/current/include/journal-eq.inc),
[trim and EEPROM policy](STR8N_V2_TRIM_EEPROM_POLICY_2026-10-07.md),
[NTP boundary synchronization proposal](RTC_NTP_BOUNDARY_SYNC_PROPOSAL.md).
