# Optional RTC/I2C phase 2 acceptance

Recorded 2026-10-06 America/Chicago. The integrated STR8-N 2.0b5 candidate,
generation 14, is installed on 2512, 2205 and 2609. It provides program clock
services and a shared I2C transaction service from a separate flash sector,
with 512 bytes of board RAM. This is a local candidate; no release is published.

## Installed layout and discovery

| Region | Ownership |
| --- | --- |
| B3 sector 8, `$8000-$8FFF` | Optional RTC/I2C component with full-sector CRC |
| B3 `$8000-$86DF` | 1760-byte provider including its entry-validation seal |
| B3 `$86E0-$88DF` | Serialized 512-byte gateway/state template |
| RAM `$6500-$66FF` | Protected gateway, shared state and request/results |
| B1 sectors 8/9 | Verified saved MAINT 1.6 record |
| B3 sector 9 | Erased, available for a later explicit allocation |
| B3 A/B | Monitor slots, generation 14, 3946 code bytes each |
| B3 C/D | Configuration/wear journals |
| B3 E | Launcher/kernel bootstrap, RST and help; existing entries retained |
| B3 F | Existing beta4 reset/recovery core, byte-identical |

The kernel verifies the complete E sector before calling its bootstrap. It
then verifies the entire optional component before copying executable gateway
bytes. Boot publishes discovery and reserves RAM without probing I2C.
The first program clock **or** bus request initializes the driver. It never
sets time, acknowledges an outage, scans devices, or accesses MCP chip memory
automatically. An absent EDU does not prevent the monitor from operating.

Programs first check the eight-byte kernel descriptor at `$7D04`:
`"SV",1,flags,gateway-LE16,last-program-RAM-LE16`. Bit 0 advertises clock,
bit 1 I2C. Installed bytes are `53 56 01 03 00 65 FF 64`; ordinary program
RAM ends at `$64FF`. Missing/corrupt optional software on a cold boot publishes
`53 56 01 00 00 00 FF 66`, allowing RAM through `$66FF`. Missing/untrusted E
does not publish the descriptor. Check its signature before reading fields.
An absent EDU board alone does **not** free the installed software's RAM:
user/program RAM still ends at `$64FF`, inclusive, and `$6500-$66FF` remains
reserved for RTC/I2C services. The `$66FF` user-RAM limit applies only when the
optional service software is absent or rejected on a cold boot. If the service
was already active, its reservation is retained until RESET even if later
validation fails. Programs must use the validated descriptor's RAM limit;
device presence or a failed clock read is not a RAM-allocation signal.
With E unavailable, memory display/recovery still work; existing E-dependent
commands refuse with `SR unavailable` rather than executing untrusted code.

Clock discovery at `$6500` is `RG`,1,4; JSR entries are READ `$6504`, STATUS
`$6507`, SET `$650A`, ACK `$650D`. Result base is `$66C0`; calendar is
`$66C2-$66C9`, raw registers `$66CB-$66D3`, current outage `$66D4-$66DB`,
capture-valid `$66DC`, SET request `$66E0-$66E7`, explicit intent key
`$66E9-$66EA`, and retained outage capture `$66F0-$66F7`. Field layouts and
explicit SET/ACK policy follow the [phase 1 API](../tools/v2-rtc/README.md).
The `I2`,1,1 descriptor is at `$6510`, with JSR transfer `$6514` and request
at `$6650`. See [the I2C ABI](../tools/v2-rtc/I2C_API.md) and
[the client fixture](../tools/v2-rtc/kernel-client.asm).

Gateway code occupies 326 bytes; private buffer thunks are at `$66B0/$66B4`.
Code verification is invalidated on monitor reentry. Initialized state and
outage capture survive ordinary HOLD/revalidation. An active RAM reservation
is retained until RESET even if software later fails validation. RESET clears
discovery and private state; an outage capture in RAM is not persistent storage.

Calls are foreground, single-master and nonreentrant. They preserve caller
bank PCR, I/decimal state, stack and documented VIA state. 816 calls require
emulation mode with D/DBR/PBR zero. Cross-bank calls require a RAM NMI handler
that preserves the bank; an unsupported flash handler returns `$82` before
remapping. IRQ is masked for the call. Native/interrupt-handler RTC calls are
outside this acceptance.

## Migration and hardware qualification

Fresh complete backups of every board were read twice before writing. Plans
were bound to all four preimage hashes, FTDI identities, payloads and installer
hashes. The linked RAM installer was modeled for each exact plan, checked for
stale preimage/corrupt-payload refusal, loaded and read back before execution.
It verified each sector on device, committed the new B1 MAINT label only after
both sectors verified, and removed the old B3 MAINT afterward. Each board was
physically RESET by the user after installation.

| Board | Port / CPU | EDU | READ in B0/B1/B2/B3 | Public I2C MCP read |
| --- | --- | --- | --- | --- |
| 2512 | COM4 / 65C02 | Absent | `$01` in every bank, bounded bus-unavailable result | `$01`, zero completed payload bytes |
| 2205 | COM3 / 65C02 | Fitted | `$00` in every bank, valid advancing time | `$00`, 1 written / 9 read |
| 2609 | COM8 / 65C816 emulation | Fitted | `$00` in every bank, valid advancing time | `$00`, 1 written / 9 read |

The 2609 entry-state fixture independently confirmed E=1 and D/DBR/PBR=0.
Cold gateway state was uninitialized before the first client request on each
board. Subsequent clock calls preserved state across HOLD. Both EDU boards
retained latched power-fail evidence and captured it into RAM; these checks
issued no time SET or ACK and did not clear the evidence. Flags `$3F` include
continuity unknown; successful time reads do not certify battery health.

Normal M/G operations rejected protected RAM, and F/I rejected the component
sector. Relocated `R MAINT` ran 1.6, mapped the new flash/RAM ownership,
rejected component erasure and RAM-copy overlap before confirmation, then
returned safely. Caller-bank/VIA checks passed. A/B/A software RESET runs
passed both installed monitor slots and fresh discovery/first-request behavior.
Complete final flash reads and independent repeats matched the exact planned
four-bank images. The acceptance audit binds models, installer, reset, service
checks, slot checks, final hashes, retained settings and planned wear counters.

2512 required ten planned sector erases, including its alpha26 F upgrade;
2205/2609 required eight, leaving their beta4 F byte-identical. B0 and B2
were preserved on all boards. 2512's B1/B2 were already erased, as previously
confirmed with the user; B1 now holds MAINT. Its legacy settings could not be
recovered, so the plan uses safe defaults with autostart disabled and an unknown
prior-wear baseline. Beta4 board settings/wear were retained and accepted A/B
preferences retagged to generation 14. Journals preaccount the planned erase
attempts; interruption can therefore conservatively count attempts not reached.

The unchanged static MAINT 1.5 S19 still loads/runs/returns in the model, retaining
its public ABI. It predates service ownership; installed MAINT 1.6 provides the
new protection policy. Arbitrary program access to VIA/RAM/flash remains outside
the cooperative service guards.

## Reproduction and evidence

```text
python tools/build_v2_rtc.py
python tools/build_v2_rtc_split.py
python tools/test_v2_rtc_split.py
python tools/test_v2_i2c.py
python tools/build_v2_rtc_kernel.py
python tools/build_bank_maint_rtc.py
python tools/test_v2_rtc_kernel.py
python tools/build_v2_rtc_migrator.py
python tools/build_v2_rtc_kernel_client.py
```

Generated images and hash-bound reports are under `BUILD/v2-rtc-kernel`.
`prepare_v2_rtc_upgrade.py` creates a plan from a fresh verified complete
backup; `test_v2_rtc_upgrade.py` models that exact plan before
`install_v2_rtc_upgrade.py` opens its bound board. These are board-specific
migration tools, not a general unattended release installer.
`qualify_v2_rtc_kernel_board.py` exercises installed services and MAINT without
clock/flash writes; `qualify_v2_rtc_slots.py` checks both slots via software RESET.

| Integrated artifact | SHA256 |
| --- | --- |
| RTC/I2C sector | `1221e5a93607faffdefab03e91a784477726e42c31f37f18eb9f24f6a3fa0bc9` |
| Slot A | `44147fef17dbf97e292953d621b43b555eba75b3c6a1455e5ddb0cc7418c6ed9` |
| Slot B | `b429c58aaecc73ac745b343ce57901fcd037a15cc75482e091231d6d2819520a` |
| E | `dd066903d76563be920defaacffd5f670781ef7ba6532a054f8cbe1fdc84cfaa` |
| F | `be0c53e1700eb7f35daa556cd07a52f1ee037ff43bfd940d36c6e3a19bbe9962` |

Owner-local evidence is in
`output/qualification/rtc-phase2-kernel-2026-10-06/{2512,2205,2609}`:
`prior`, `upgrade`, `service-check`, `slot-check`, and `post-qualification`.
The root `acceptance.json` is generated by `audit_v2_rtc_qualification.py`.
Vendor firmware backups remain excluded from Git/release artifacts. The client
S19 entry-address error was rejected before loading; its correction changes
only the qualification artifact, with the refused log retained separately.

Host models additionally cover absent/corrupt optional software, no-EDU/stuck
bus, managed-write policy, bounded progress/errors, NMI profiles, and a second
I2C slave with RTC absent. Physical qualification covers the MCP as a public
I2C client; a second physical peripheral still needs its own test when provided.
SET/ACK refactor behavior is model-qualified, with original phase 1 hardware
tests retained; phase 2 hardware qualification deliberately preserves RTC data.

The subsequent user-requested [UTC synchronization and drift baseline](STR8N_V2_RTC_UTC_BASELINE_2026-10-06.md)
additionally qualifies explicit SET through the installed service on both EDU
boards, with pre-write evidence archive, retained outage capture, advancing
readback and preserved control/trim. ACK hardware scope remains as recorded above.

The later [CLOCK 1.0 application](STR8N_V2_CLOCK_1_0_2026-10-06.md) is saved in
previously erased B2 sector 8 on all three boards. It adds the `R CLOCK` workflow
without changing the integrated monitor/service images or current drift baselines.

SRAM/EEPROM drivers and allocation, alarms, saved-record timestamps and native
RTC calls remain deferred. No battery-removal test was repeated. Battery-removal
behavior on 2609 remains the user's requested assumption from 2205's phase 1
result, not a measured 2609 result.
