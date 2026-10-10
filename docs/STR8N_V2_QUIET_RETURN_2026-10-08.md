# Quiet monitor return: beta19 candidate

`python tools/build_v2_quiet_return.py` builds `BUILD/v2-quiet-return`
separately from the beta18 image pinned for October 9 at 1 a.m. Central.
No board access or schedule change is performed by this builder.

The first monitor entry after reset prints the CPU/ABI and complete status
block, including when the boot selector chooses A or B. Later public HOLD
returns, including M1's MAINT return, restore the monitor console and service
discovery and then print only the prompt. TIME remains an explicit status
request. The reset-cleared EDU mode latch is captured on the stack before
service discovery determines the mode; it distinguishes first entry from
software return independently of autostart. The existing leading CR/LF
separates the cold banner from the selector. An unnecessary jump to the
immediately following delay label is removed to meet the slot limit.

Both monitor payloads are 3,967 bytes within their 3,968-byte limits. The
fixed recovery core, RTC component and journal remain byte-identical to the
scheduled beta18 candidate. No additional persistent RAM is reserved.

Run the following with `STR8_RTC_BUILD=BUILD/v2-quiet-return`:

```text
python tools/test_v2_quiet_return.py
python tools/test_v2_rtc_kernel.py
python tools/test_v2_trim_display.py
```

The focused return test covers A/B cold selection, EDU ON/OFF, actual M1,
public HOLD from all four banks, application RAM preservation on HOLD,
hardware preservation and absence of RTC/SPI transactions during HOLD.
It also checks that the scheduled beta18 build metadata hash is unchanged.
All three suites passed on this candidate, including the kernel's recovery,
protection, outage-capture and legacy application-return checks and all 256
signed trim register encodings. The existing beta18 candidate audit also passed.
MAINT intentionally loads into application RAM, so M1 is not claimed to
preserve application RAM.

The existing 1 a.m. automation remains bound to the beta18 manifest at
`output/qualification/trim-display-2026-10-08/flash-schedule.json` and will
not install this candidate. Including beta19 requires preparing and testing
new per-board plans and updating the scheduled manifest explicitly.
Weekday display is a proposed separate change and is not implemented here.
