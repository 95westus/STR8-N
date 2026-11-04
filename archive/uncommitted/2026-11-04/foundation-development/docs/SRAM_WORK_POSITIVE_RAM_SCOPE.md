# SRAM/WORK positive RAM trial

November 1, 2026. Continue the owner-requested b35 feature qualification on
2512 first. Use the already built and read-only-qualified g1 RAM candidate
from `BUILD/sram-work-g1-ram-r2`; no firmware rebuild or flash installation.

Before any SPI write, capture fresh CPU RAM/ZP, admit current MON and golden
F, and read all 131,072 SPI SRAM bytes through the CRC-framed PB reader
retargeted to the current PROGRAM provider (WRITE refused, empty write
allowance). Compare its first header read with the installed read-only path
before continuing. Admit only the existing SS1/64 KiB layout, available directory
slots and payload pages within the test allowance. Never infer that erased
or unused memory is disposable.

Temporary mutations are bounded to four KiB:

| SPI addresses | Purpose |
|---|---|
| $00000–$007FF | Layout, directory and WORK allocation metadata |
| $00800–$00BFF | Two short named PROGRAM versions |
| $10000–$103FF | A temporary WORK allocation and 64-byte I/O pattern |

Exercise normal UNLOCK/YES/LOCK confirmation, then controlled API calls for
Store/latest Restore/delete/reclaim/format; WORK upgrade, claim/release,
read/write, owner and bounds refusal, resize/conflict, fallback/repair and
format protection. The API harness deliberately grants the volatile write
capability immediately before each mutating call. This does not claim that
all console spellings or interactive error paths have been tested.

Restore and read back every admitted test block between the PROGRAM and
WORK phases and on every exit after mutation. Compare the entire SRAM with
the fresh original capture using that independent reader. Restore
and read back owner CPU RAM/ZP, incoming EDU selection and monitor context.
Retain private captures and receipts; do not put owner data in release kits.

The shared serial lease gives NIST/RTCC collection priority. A request before
mutation yields immediately after restoring borrowed CPU RAM. A request
during mutation first restores the bounded SPI fixture, then owner CPU RAM
and releases the port. Full post-trial comparison can defer to a later
collection-free window; a deferred verification is not a passed trial.

Zero flash/F/journal, RTC-setting, trim or power-fail acknowledgement writes;
no reset or power cut. Boot choices, history and images remain unchanged.
2205/2604 and published downloads are outside this trial. Installed R SRAM
and R WORK remain unchanged until a later placement review and installation.
