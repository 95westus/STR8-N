# b15 VX1: minimal VERSION/capability candidate for 2609

Prepared and installed October 27, 2026. **52 offline groups/checks passed,
followed by the separately authorized hardware installation on 2609.** VX1 E
and both matching MONs are installed. VERSION, CAPS and the 224-byte INFO
record passed from each MON over USB. All four banks were read twice before
and twice after the MON checks. B0 and saved configuration are unchanged;
the board returned to `REC>` and the port is closed. This remains a candidate
interface, not a released/frozen v2.1 ABI.

[Hardware receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/receipt.md) ·
[Full console log](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/console-log.txt) ·
[Serial/postimage audit](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/audit.json).

The [preparation receipt](../output/qualification/2609-b15-onboarding-20261027T212009Z/step08-VERSION-ready/receipt.md)
contains hashes, test evidence and the proposed installer procedure. Simulated
[VERSION](../output/qualification/2609-b15-onboarding-20261027T212009Z/step08-VERSION-ready/simulated-VERSION.txt)
and [CAPS](../output/qualification/2609-b15-onboarding-20261027T212009Z/step08-VERSION-ready/simulated-CAPS.txt)
outputs are model captures. Actual hardware captures are
[A VERSION](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/MON-A-VERSION.txt),
[A CAPS](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/MON-A-CAPS.txt),
[B VERSION](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/MON-B-VERSION.txt) and
[B CAPS](../output/qualification/2609-b15-onboarding-20261027T212009Z/step09-VERSION-install/MON-B-CAPS.txt).

## Scope and files

| Prepared file | Purpose |
|---|---|
| `version-caps-e000.bin` | 4096-byte B3:E provider; structured information and VERSION/CAPS formatting |
| `monitor-a0-version-caps.bin` | 4096-byte MON A with narrow command/discovery hooks |
| `monitor-b0-version-caps.bin` | 4096-byte MON B with the same public interface |
| `version-caps-query-RAM.bin` | 417-byte RAM client at $0200; callable query veneer at $0203 |
| `2609-VERSION-CAPS-RAM.bin` | 15,480-byte bound RAM installer; executed and verified on 2609 |

F remains byte-identical to b15, SHA-256
`1a1db354d49d8a9a555be1100b74f3e4b0ed14d3156f3a333086853a845717b8`.
Its boot/recovery and existing public RAM entries are unchanged. The old
S/R/T, B29/provider and debugger gates remain disabled. The implementation adds
only exact `VERSION` and `CAPS` commands, a checked discovery entry, a read-only
query and build identity records. It allocates no new permanent RAM and does
not initialize RTC, I2C, SPI, timers or optional hardware.

This milestone uses a **B3 ROM locator**, not the future F-published resident
directory. It leaves that broader ABI and proposed RAM map deferred. The RAM
client permits bank-independent foreground use by selecting B3 temporarily and
restoring the caller's entire PCR. F recovery can load that client even if both
MONs are invalid, provided the E provider itself is valid. If E is absent or
invalid, the client returns unavailable and F recovery remains usable.

## Bootstrap/discovery contract

See [candidate public include](../prototypes/boot-record-v2/version-caps-public.inc).
Calls use SEI/CLD; 816 requires E=1, D=DBR=PBR=0. Native service calls,
interrupt calls, reentrancy and concurrent flash mutation are unsupported.

- B3:`$E000` begins `VX`, format 1, descriptor length 64.
- `$E004` is a JMP to structured QUERY; `$E007` is a JMP to command dispatch.
- Header bytes 13/14 are interface/flags, both 1; byte 15 is 224.
- Bytes 16/17 are the little-endian 4096-byte extent; byte 31 is commit 0.
- Entry targets must lie in `$E040–$EFBF`; header/footer targets are rejected.
- The complete 4096-byte sector has CRC16/CCITT residue zero, seed FFFF.
- In the matching MON facade, slot-base + `$00AE` is DISCOVER. With B3
  visible it returns C=1, A=1, X/Y=`$E000` when validated, or C=0/A=80 when
  unavailable. Its validator borrows the existing MON scratch E0/E1 and J_CRC.
  The only new bootstrap-private F dependency is the existing exact-b15 CRC
  helper binding, already imported by the MON; the E provider/client do not
  call private F/MON implementations.

MON hooks recognize exact command names, then check signature, format, interface,
flags, length, commit, entry bounds and CRC before executing E code. Failure
prints `VX1 unavailable` and returns to the ordinary MON prompt. Other commands
retain their previous dispatch. The RAM client performs equivalent checks
independently; callers do not jump into unchecked optional bytes.

## Structured QUERY

Inputs: A=running MON page A0/B0, or zero when unknown; X/Y=output pointer
low/high. The caller sets output byte 0 to its capacity, at least 224.

Valid output ranges are wholly within `$0200–$64FF`, or exactly `$6700` for
the provider's own transient frame. Invalid capacity, wrap/range or running-page
values fail before output writes. The $6700 frame is shared foreground scratch,
not application-owned durable state.

Returns C=1/A=0 on success, C=0/A=81 for incompatible core/RA, C=0/A=82 for bad
request/buffer. The validated RAM bootstrap client additionally returns C=0/A=80
for missing/incompatible provider metadata. X/Y, SP and D0–DF are preserved.
Flags NZ/C reflect status; callers retain the required I=1/D=0 mode. The
provider does not change banks or device registers. The RAM wrapper changes
only PCR temporarily and restores it on success and failure.

Scratch ownership: `$D0–$DF` saved/restored on stack; `$6700–$67FF` transient;
the validated caller buffer. No application RAM limit is reduced. Raw-L display
entry at $0200 owns its loaded prefix and $6000–$60DF result buffer for that
tool's lifetime; it prints VERSION and returns through the public RAM RESET.
The callable client veneer at $0203 uses a caller-selected buffer instead.

| Record offset | Meaning |
|---|---|
| 0–3 | `VI`, format 1, length 224 |
| 4 | Unchanged legacy compiled capability flags, currently 17 hex |
| 5 | Available SYSTEM-information service flag, 1 |
| 6–7 | CPU identity 02/16; shared foreground 65C02/816-emulation profile 1 |
| 8 | Explicit caller-supplied running page; 0 means unavailable/unknown |
| 9–11 | F/A/B state: bit 0 valid component, bit 1 build metadata available |
| 12–23 | F/A/B generations, three little-endian 32-bit values |
| 24–119 | F/A/B build IDs, three 32-byte SHA-256 values |
| 120–167 | F/A/B release strings, three 16-byte NUL-terminated fields |
| 168–199 | E extension normalized SHA-256 build ID |
| 200–215 | E extension release string |
| 216–219 | Legacy CAPS format/descriptor length and BOARD format/flags |
| 220–223 | Reserved FF |

Unavailable identity/release/generation bytes remain FF; validity flags distinguish
them. A valid older MON without the new metadata footer retains its generation
but reports its exact build ID/release unavailable. Bad CRC/entry metadata cannot
hide the independently valid F identity. F is recognized using the exact source
CRC and the build manifest's full SHA-256, rather than interpreting legacy
private boot fields.

`VERSION` renders this public record; it does not use private boot selection,
board-name or provider tables. `CAPS` reports VX1 interface information alongside
the unchanged legacy CAPS and CPU identity. The old RC1 VERSION package is not
modified: VERSION was unavailable in the installed b15 bench MON before this
candidate, so this is new b15 output rather than a claim of full RC1 restoration.

## Build identity and integrity

MON and E have independent 64-byte metadata footers at sector offset FC0. Format
and normalization version are 1; release fields are printable and NUL-terminated.
MON footer generation must match its MI header. Existing slot validation still
uses the original MI signature, slot page, length/entry bounds, commit and CRC.

Build ID is SHA-256 of the whole 4096-byte component with these exclusions:

- Own ID bytes FDC–FFB are zeroed.
- MON CRC bytes 18–19 are zeroed; E CRC bytes FFE–FFF are zeroed.
- Commit byte 31 is normalized to zero.

All remaining header, body, footer and padding bytes contribute. F has no new
footer and uses its unchanged complete-byte SHA-256. Runtime checks use CRC;
the IDs are build identities, not signatures or a claim of cryptographic ROM
authentication. Tests shifted private E implementations by 32 bytes and verified
that unchanged MON public callers still worked and the E build ID changed.

## Completed install and wear accounting

Verified tracked counts are **A=51, B=54, C=78, D=47, E=43, F=30**. The
installer reserved and performed E 42→43, A 50→51, B 53→54, in that order.
Each reservation is committed before its corresponding erase. New records are
C300/C400/C500, sequences 1018/1019/1020. No C/D erase or F write occurred;
existing C000/C100/C200/D000 records remain byte-identical. Default S, disabled
opaque banks, legacy configuration body and unknown-lifetime mask FFFFFFFF
are retained. B0–B2 and B3:8/9/F matched before and after the real MON queries.
All prior counts retain their lower-bound meaning; earlier lifetime wear is unknown.

E is first so an old MON ignores it until a new MON is committed. A new MON
never activates the old E/B2 dispatchers. The exact-source guard refuses changed,
interrupted or completed source states. The live run captured every source bank
twice and durably saved its host wear reservation before the install confirmation.
The complete raw TX audit bound both RAM uploads, all readbacks and both MON
VERSION/CAPS/INFO checks. There was no saved-configuration command or TX after
the final `REC>`. The original preparation evidence remains archived separately.

Live wrapper: [board_version_caps_2609.py](../prototypes/boot-record-v2/board_version_caps_2609.py).
File-only audit: [audit_version_caps_2609.py](../prototypes/boot-record-v2/audit_version_caps_2609.py).
Operator keystrokes are in the [F-up guide](STR8N_B15_FROM_F_GUIDE.md#versioncaps-extension-hardware-step).

The current B0 WDCMONV2 backup is still
`1398d9551f7072ff36203307f55b7e41204f2579ce667515920a2703845eef94`.
ACIA and electrical power-interruption behavior remain unqualified by this work.
