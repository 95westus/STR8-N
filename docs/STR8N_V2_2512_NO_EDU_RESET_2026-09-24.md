# Board 2512 reset and HOLD check without EDU

Date: 2026-09-24. The operator removed the EDU board. COM4 identified the
FT245 adapter as `A10MQFLCA`; the ACIA adapter was not present in the host
COM-port inventory. No flash or RAM writes were requested in this session.

With COM4 open across physical RESET, the board printed:

```text
STR8-N 2.0a19 B3 65C02
ABI 65C02 | 816E | 816N-VEC
C 01 01 V 20
S/Ctrl-C hold
```

An uncancelled reset continued through `RST H`, STR8-N 1.35, and HIMON in
Bank 1, consistent with the active Bank 1 vector autostart configuration.
On the next physical RESET, the host sent `S` immediately after the hold
message. The board printed `Canceled` and remained at `B3>`.

Read-only commands at that prompt returned:

| Command | Result |
| --- | --- |
| `C` | `C 01 01 V 20` |
| `D 7D01 7D02` | `02 00` (65C02 identity, FT245 selected) |
| `D F000 F003` | `53 4E 02 00` (`SN`, ABI 2, format 0) |

This accepts physical reset, Bank 1 autostart, and timed `S` cancellation
for this no-EDU setup. The ACIA receive and fallback console remain pending because the ACIA adapter was
absent and earlier physical receive tests failed. EDU LED observations cannot
be made with the EDU removed. No readback was made during this session; the
last exact full-bank readback remains the four-bank layout report.

## Cold power-on follow-up

The operator unplugged the board's USB power, waited approximately ten
seconds, and reconnected it while a receive-only COM4 capture was running.
The capture recorded a COM4 disconnect/reconnect, followed by `RST H`,
`STR8-N 1.35`, `BOOT WARM`, and `HIMON V 00.0916(1949)` at the `>` prompt.
This passes the observed cold-start path into the configured Bank 1 guest.
The initial Bank 3 alpha19 banner and autostart countdown were not captured:
Windows reopened COM4 after those bytes were emitted. The prior physical-reset
capture establishes that this configuration boots alpha19 and selects the
Bank 1 vector; the cold-power capture alone does not prove those early bytes.
The operator reported the EDU remained removed. The host transmitted no bytes
during the cold-power capture.

Append-only host captures are retained under
`output/qualification/board-2512-no-edu-2026-09-24/`. SHA-256 identities:

| Capture | SHA-256 |
| --- | --- |
| `reset-open.jsonl` | `2a8273f808e2d21ee69690b2bf55cdc77a467bc2259c2ab1814d1c987b212cfb` |
| `reset-hold-armed.jsonl` | `e9fa1503b5c85dbd81bcb04f30ed132bf66f2b81ca46651760fdeb7b6f2345` |
| `read-only.jsonl` | `ea3a6170fa3a293cd3aa4c525f346baba561380ae590d0c4283f56237d38e33f` |
| `cold-power.jsonl` | `ea434ad5cf011a8b4638a646af0419a382b7778146d9c4b64394711b68a2e6bc` |

The final observed prompt after the cold power-on was Bank 1 HIMON `>`.
