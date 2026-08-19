# STR8-N v1.22 C/W Selector Hardware Proof — 2026-08-19

Status: board accepted by the operator for guarded top-sector update, final
`0-2 C W S` selector identity, automatic warm entry, selector `S`, prompt and
selector `W`, selector `C`, HIMON cold initialization, Bank-0/Bank-2 launch,
and the `J3` return to the Bank-3 RESET path.

The final installed candidate displayed `STR8-N 1.22`, `0-2 C W S:`, and
`I L C W J`. Selector timeout and both observed `W` paths reported `BOOT WARM`.
Selector `C` reported `BOOT COLD` and `RAM ZERO OK` under HIMON
`00.0818(1108)`.

The board received two guarded updates. The first replaced v1.21 with the
intermediate v1.22 warm-default image and reported old-sector receipt `$0372`.
The second backed up that intermediate image, reported receipt `$2FD5`, and
installed the final C/W selector image. Both updates reported `BACKUP VERIFIED`
before erase and `STR8-N 1.22 VERIFIED; RESET` afterward. These sums identify
the sectors being replaced; they are not hashes of the new image.

Host-built final candidate artifacts associated with this gate are:

```text
BUILD/v1.22/bin/str8n-v1.22-bank3-f000-ffff.bin
SHA-256 C26F86CC8BAA77DCEA9FCA59DDD79AED8415BFCFB106EFE90DEE03EE228F26A7

BUILD/v1.22/s19/str8n-v1.22-top-update-2000.s19
SHA-256 D02805D0907E644B9B6265B9F6F85A4381C57DCA62B8CEA92BE40499213C6F6C
```

Operator acceptance note: on 2026-08-19 the operator explicitly cleared the
uncaptured RAM canary, prompt `C`, installed-byte dumps, and uninterrupted
`J3`-to-timeout-warm sequence as acceptance blockers. The transcript remains
literal: `J3` reached the Bank-3 RESET path and live-selector `0` then diverted
execution to Bank 0, while the prescribed ROM dumps and the other cleared
observations are not present in the capture. Physical RESET events were not
separately annotated. These evidence distinctions do not leave the operator's
v1.22 acceptance partial.

The `LJ`, `ST`, incomplete `I`, and empty `L` attempts below are out-of-protocol
operator input and were safely rejected. Selecting Bank 1 entered the expected
older `0-2 H S` top-sector backup created by the second updater; its missing
compatible local HIMON target produced `NO`.

Exact retained terminal transcript:

```text
STR8
RUN STR8: BOOTLOADER @F000 K=03 ? y
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.21
0-2 H S: .S
I L H J
STR8-N>L
S19

STR8-N 1.22 TOP UPDATE
BACKUP B1:F; TARGET B3:F
TYPE BACKUP B1F> BACKUP B1F
BACKUP VERIFIED
SAFE PHY $0F000-$0FFFF; TARGET PHY $1F000-$1FFFF; SUM=$0372
TYPE STR8-N 1.22> STR8-N 1.22
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 1.22 VERIFIED; RESET
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 H S: ......
BOOT WARM

HIMON V 00.0818(1108)
>STR8
RUN STR8: BOOTLOADER @F000 K=03 ? y
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 H S: .S
I L H J
STR8-N>LJ
BAD
STR8-N>LJ
BAD
STR8-N>STSTR8-N>RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 H S: .S
I L H J
STR8-N>I
B0-3:
BAD
STR8-N>LJ
STR8-N 1.22 TOP UPDATE
BACKUP B1:F; TARGET B3:F
TYPE BACKUP B1F> BACKUP B1F
BACKUP VERIFIED
SAFE PHY $0F000-$0FFFF; TARGET PHY $1F000-$1FFFF; SUM=$2FD5
TYPE STR8-N 1.22> STR8-N 1.22
ERASING B3:F - NO RESET/NMI/POWER
STR8-N 1.22 VERIFIED; RESET
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 C W S: ......
BOOT WARM

HIMON V 00.0818(1108)
>STR8
RUN STR8: BOOTLOADER @F000 K=03 ? y
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 C W S: .S
I L C W J
STR8-N>I
B0-3:
BAD
STR8-N>L
S19

BAD
STR8-N>W
BOOT WARM

HIMON V 00.0818(1108)
>STR8
RUN STR8: BOOTLOADER @F000 K=03 ? y
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 C W S: .S
I L C W J
STR8-N>W
BOOT WARM

HIMON V 00.0818(1108)
>STR8
RUN STR8: BOOTLOADER @F000 K=03 ? y
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 C W S: .S
I L C W J
STR8-N>J3
J B3
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 C W S: ..0
J B0
3S

================================
  W65C02SXB + EDU Kit  Rev 1.0
  W65C02S @ 8 MHz  |  5V System
  I2C/SPI bit-banged via W65C22
================================
Initializing...
Scanning devices...
  OLED (SSD1306)     $3C  OK
  RTC  (MCP79411)    $6F  OK
  SPI SRAM           OK
  ADC  (ADS1015)     $48  not found
  CardKB             $5F  not found
Init complete.

--- W65C02SXB + EDU Kit ---
  T - Set Time   (HHMMSS)
  D - Set Date   (MMDDYY+DOW)
  P - Print Time/Date
  N - Set Name   (16 max)
  S - SRAM Test
  H/? - Help
> RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 C W S: .1
J B1
3S
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 H S: ......
NO
I L H J
STR8-N>RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 C W S: .2
J B2
3S

================================
  W65C02SXB + EDU Kit  Rev 1.0
  W65C02S @ 8 MHz  |  5V System
  I2C/SPI bit-banged via W65C22
================================
Initializing...
Scanning devices...
  OLED (SSD1306)     $3C  OK
  RTC  (MCP79411)    $6F  OK
  SPI SRAM           OK
  ADC  (ADS1015)     $48  not found
  CardKB             $5F  not found
Init complete.

--- W65C02SXB + EDU Kit ---
  T - Set Time   (HHMMSS)
  D - Set Date   (MMDDYY+DOW)
  P - Print Time/Date
  N - Set Name   (16 max)
  S - SRAM Test
  H/? - Help
> RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 C W S: .W
BOOT WARM

HIMON V 00.0818(1108)
>STR8
RUN STR8: BOOTLOADER @F000 K=03 ? y
RESET
WAIT... WAIT... WAIT... WAIT... WAIT... WAIT...
STR8-N 1.22
0-2 C W S: .C
BOOT COLD
RAM ZERO OK

HIMON V 00.0818(1108)
>
```
