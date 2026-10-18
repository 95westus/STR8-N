> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# 2512 beta32 soak stop and RAM restoration

The owner requested stopping the soak before v2.1 alpha work. Inspection found
it had already exited on a Windows serial-access failure at 2026-10-16
19:49:29 UTC (14:49:29 CDT), after 9 hours 52 minutes elapsed, 69 complete
cycles and 1,888 passed units. The interrupted RAM unit is not counted as a pass.

Windows reported ClearCommError/WriteFile access denied during the CPU RAM
pattern test. Its finally-path restoration encountered the same serial failure.
This is a failed transport/restoration attempt, not evidence of a flash or SRAM
integrity mismatch, and it does not establish a completed 24-hour soak.

The durable restoration record retained the original 256 bytes at $0200-$02FF.
The board was initially absent over USB. After the owner reconnected 2512, its
FTDI identity resolved to COM4; the saved bytes were restored and exactly read
back. No flash, SPI SRAM, EEPROM, RTC or trim write was performed for restoration.
The soak was not restarted, and a STOP marker prevents an unintended continuation.

Evidence remains local under
`output/qualification/beta32-enhanced-soak-2512-2026-10-16`: original status,
stderr, `001888-ram/restore-state.json`, and
`requested-stop-restoration-02/report.json` plus serial transcript. The original
failure record remains unchanged. The former worker PID had been reused by an
unrelated process, which was not terminated.
