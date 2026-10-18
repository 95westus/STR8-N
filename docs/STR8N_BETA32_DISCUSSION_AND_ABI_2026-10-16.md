> Historical release-work checkpoint. Current v2.0rc1 firmware is installed
> on 2604/2609; 2205/2512 are off. Soaks and RTC sampling are stopped.
> RTC qualification, native 816 apps/tests, ACIA and crypto remain deferred.
> Operating instructions below describe their recorded historical stage.

# Beta32 discussion record and ABI inventory

Recorded from the owner's conversation on 2026-10-16. This page collects the
decisions and explanations from that chat; the linked installation records
hold the detailed qualification evidence. The ABI inventory describes beta32,
not a newly published interface or an authorization to flash another board.

## Decisions and implementation records

| Topic | Result / authoritative record |
|---|---|
| Coin-cell backup reminders | Battery age/policy reminders, with unknown condition explicitly distinguished from voltage measurement or remaining-capacity prediction. See [battery policy](STR8N_V2_BATTERY_2026-10-15.md). |
| Flash wear | Tracked per-sector erase attempts; warning/high thresholds 50,000/80,000 against the discussed 100,000-cycle assumption. Prior/direct programming outside tracking remains unknown. See [wear policy](STR8N_V2_FLASH_WEAR_2026-10-15.md) and [beta26](STR8N_V2_BETA26_2026-10-15.md). |
| Freeing B1 | The three MAINT sectors moved into B2 with the other reserved assets shifted. See [beta27](STR8N_V2_BETA27_2026-10-15.md). |
| Utilities mostly in flash | MAINT, SRAM, WORK and EDU execute their main code/constants from flash, retaining RAM buffers, state and necessary workers. See [beta28 sizing/design](STR8N_V2_BETA28_CANDIDATE_2026-10-15.md). |
| BATCH | Semicolon-separated command queue, error stopping, ESC cancellation, and real-input confirmation prompts. See [beta29](STR8N_V2_BETA29_CANDIDATE_2026-10-15.md). |
| Bare utility names | MAINT/SRAM/WORK/EDU launch without R, including inside BATCH. No CMD prefix was adopted. R retains saved-RAM-program restore/run semantics. See [beta30](STR8N_V2_BETA30_CANDIDATE_2026-10-16.md). |
| Boot wear status | Beta31 added the status; beta32 added the highest tracked decimal count and bank/sector. See [beta31](STR8N_V2_BETA31_CANDIDATE_2026-10-16.md) and [beta32](STR8N_V2_BETA32_CANDIDATE_2026-10-16.md). |
| 2609 initial upgrade | Beta32 initially used slot A and its retained F31B recovery profile; beta27 remained in B. Saved CLK stayed CLOCK 1.8 until separately updated. See [initial installation and CLK upgrade](STR8N_V2_BETA32_2609_2026-10-16.md). |
| 2609 matching 2512 | Later explicitly requested and completed: identical STR8-N code images, beta32 B, beta28 A, F30D recovery/services, utilities and saved CLOCK 1.9. Board-specific settings/data and banks 0/1 were preserved. See [common-code qualification](STR8N_V2_BETA32_COMMON_CODE_2609_2026-10-16.md). |

The final matched utility versions are MAINT 2.4, SRAM/WORK/EDU 1.4 and
CLOCK 1.9. Both monitor boots, full flash readback and
`BATCH SRAM;G CLK;Q` were verified on 2609. RTC settings, trim -14, history,
identity, EEPROM and workspace were preserved. J3 is the owner's preferred
software restart when the monitor is available; a halted installer cannot
accept it.

CLOCK-as-a-flash-APP was discussed only. No such conversion was performed.
The installed CLK remains a saved program copied from SPI SRAM into CPU RAM
for execution. Updating monitor firmware alone does not update a saved CLK.
CLOCK 1.8 lacks the BATCH integration marker/hooks and was refused inside a
queue with SRAM error 4A; CLOCK 1.9 supports the verified sequence.

The chat's intermediate soak status was 9 hours 45 minutes, 69 cycles and
1,864 passed units, still running at that observation. This is historical:
the [later stop/restoration record](STR8N_V2_BETA32_SOAK_STOP_2026-10-16.md)
records exit on Windows serial-access failure at 9 hours 52 minutes,
69 complete cycles and 1,888 passed units, followed by verified CPU RAM
restoration. It was not restarted. See the [coverage and limits](STR8N_V2_BETA32_SOAK_2512_2026-10-16.md).

## Public beta32 interfaces, by category

Public means a documented application contract, including its discovery,
calling convention, ownership and availability rules. A fixed address alone
does not make an internal routine public. Firmware/utility version numbers
and interface-format versions are separate.

| Category | Published operations / addresses | Discovery or condition |
|---|---|---|
| Monitor control | RESET $7E64; HOLD $7E67; neither returns | Validate `RA`,1,13 at $7E60 |
| Console | INIT $7E6A, PUTC $7E6D, GETC $7E70, RAW_POLL $7E73, CHECK_CANCEL $7E76, RX_RESET $7E79 | Initialized RA interface |
| Formatting/parsing | HEX_OUT $7E7C, NEWLINE $7E7F, HEX_NIBBLE $7E82 | Initialized RA interface; not the private command parser |
| Capabilities/board | CAPS_QUERY $7E85, BOARD_QUERY $7E88 | Reports supported profiles, detected CPU and console flags |
| Interrupt vectors | Emulation pointers $7E00-$7E08; native pointers $7E10-$7E18 | Data pointers, not callable services; obey handler/publication rules |
| Optional-service discovery | `SV` descriptor $7D04-$7D0B | Format, capability flags, gateway pointer and application RAM limit |
| RTC | READ $6504, STATUS $6507, SET $650A, ACK_POWER $650D | Valid SV RTC capability, then `RG`,1,4 at $6500; explicit intent keys for mutations |
| I2C | TRANSFER $6514 | Valid SV I2C capability, then `I2`,1,1 at $6510; device/range policy applies |
| External SPI | TRANSFER $664A | Valid SV SPI capability, then `SP`,1,1 at $6646; permitted profile only |
| Raw SPI SRAM | TRANSFER $66A6: probe/read/write request operations | Valid SV SRAM capability, then `SM`,1,1 at $66A2; public managed writes are denied by normal policy |
| WORK allocation | Request $5003: query, claim/release, bounded read/verified write and administration | Install WORK bootstrap; validate `WK`,1,2 at $5006 and respect buffers/handles |
| Configuration inspection | Read current 16-byte snapshot at $7D80 | Data, not a persistent flash pocket; use supported commands to save |

The ROM compatibility facade has signature `SN`,2,0 at $F000, RESET at
$F004, HOLD at $F007 and corresponding public console/query entries.
It requires the resident flash bank visible. Applications normally use the
bank-independent initialized RAM table. The reserved ROM line-editing slot
does not publish a general application line editor.

Calls are foreground and non-reentrant, with IRQ disabled and decimal clear.
On W65C816 the qualified service-call profile is E=1, D=DBR=PBR=0.
Native interrupt-vector support does not publish native-mode service calls.
Rediscover optional services after reset/reentry and check each call's result;
a valid descriptor does not establish device presence, battery health or write
permission. Do not inspect optional gateway RAM before validating SV/capability.

Sources: [public monitor definitions](../src/v2-beta4/str8n-v2-public.inc),
[RTC definitions](../tools/v2-rtc/kernel-rtc-api.inc),
[I2C definitions](../tools/v2-rtc/i2c-api.inc),
[SPI/SRAM definitions](../tools/v2-spi/spi-api.inc),
[technical contracts](STR8N_V2_BETA23_TECHNICAL_GUIDE.md), and the
[flash WORK compatibility layout](STR8N_V2_BETA28_CANDIDATE_2026-10-15.md).
Some source comments describe their original development checkpoint; the
installed build and later qualification records establish current deployment.
The old standalone RTC prototype at $3000 is not the installed service ABI.

## Private or build-paired interfaces, by category

| Category | Internal contract |
|---|---|
| Recovery | Slot validation, boot selection, monitor promotion, compatibility checks; F30D/F31B were private validator addresses, not alternative public ABIs |
| Flash and wear | RAM erase/program/poll/verify workers, wear/config journal mutations and recovery update entries; no general public flash erase/write application ABI in beta32 |
| Monitor internals | Command line editing/parsing, confirmation/messages, S/R/T dispatch and internal helper stubs |
| Flash utility execution | UX bundle dispatch, loaders, cross-bank gateways, streaming hooks and scratch; WORK's documented $5003 entry is the public exception |
| Named SRAM storage | Internal save/restore/delete/reclaim requests, directory publication and transfer hooks; command syntax does not publish those linked addresses |
| RTC administration | Durable history transactions, EEPROM journal internals, EUI binding, trim, local offset and battery policy implementation |
| BATCH integration | Queue/provider state and error/cancel/command-boundary hooks; the `BT`,1,1 marker is a paired-program integration check, not a general public command-execution API |

Public calls may be implemented by private workers; applications call the
public facade, not the workers' linked addresses. Code alignment on 2609
removed its recovery-profile difference from 2512 but did not promote private
routines into public interfaces.

S19, saved flash-program records, SRAM directory/layout packets, workspace
handles, monitor-slot headers and config/wear journals are data-format
contracts. Recognizing a signature does not authorize executing or modifying
the structure. APPS listings and BATCH command strings are user interfaces,
distinct from machine-call entry points.

## Discovery discussion and later work

A bounded scan for a distinctive, validated ABI descriptor is reasonable as
a fallback. Searching for instruction patterns or merely a JMP is fragile.
Any scan must define the memory range and selected flash bank, avoid hardware
register reads, and validate format, bounds and integrity before using results.

The preferred direction discussed was one stable discovery anchor or pointer
to a versioned service directory, allowing implementation addresses to move.
Beta32 already has RA, SV and individual service signatures, but no unified
public service directory. The chat did not add one to installed beta32.

Subsequent repository work is separately documented in the
v2.1 alpha goals (owner-local/repository reference: `STR8N_V2_1_ALPHA_ABI_GOALS.md`) and
offline ABI foundation (owner-local/repository reference: `STR8N_V2_1_ALPHA_ABI_FOUNDATION.md`). That foundation
must not be confused with boot-integrated or hardware-installed beta32 support.
