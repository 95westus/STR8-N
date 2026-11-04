# CPU-RAM device fault fixtures

These files are qualification tools, not installed firmware or release payloads.
`tools/build_clock_fault_ram.py` at the workspace root links the normal RTC
decision/encoding code, private EEPROM/trim validation and journal in CPU RAM.
It replaces the physical device transport with RAM registers and a RAM EEPROM
mirror. The existing CLOCK binary is reused with its journal pointer relocated
and its four flash-write calls redirected to a denial stub.

`clock-fault-transport.inc` records every attempted shadow write and captures
the EEPROM mirror before the first RTC write. It does not enforce the desired
archive ordering: the host must verify it. Fault modes inject EEPROM data or
commit NACK, corrupt readback, write protection, RTC SET/ACK NACK, and trim
write/readback failures. The injected weekday response deliberately clears live
timestamps to expose a missing archive-before-clear step.

These tests execute on the real CPU. They establish software behavior under
the stated responses. They do not establish physical bus/write behavior,
calibration accuracy, electrical fault handling, or flash/EEPROM endurance.
The real clock, trim, outage records, SPI data and Foundation remain untouched.
Fresh owner CPU RAM/ZP and borrowed discovery bytes must be restored afterward.

The host driver is `tools/trial_clock_fault_ram_2512.py` at the workspace root.
It checks the shared RTC-priority lease and collection window before COM4 use.
No other board may be selected by this driver. A partial test is not acceptance;
its report must show all cases, exact restoration, and physical-data preservation.
