RAM-only reset/FF isolation probe
===============================

This probe is a diagnostic for the authorized 2512 RAM-only session. It does
not update firmware. The host owns fresh application-RAM escrow, loading,
capture, admission, restoration and all physical interaction. Boards 2604 and
2609 are outside this experiment.

The qualified candidate is `BUILD/reset-ff-ram-probe-r5`. Build and qualification:

```
python prototypes/reset-ff-ram/build.py --out BUILD/reset-ff-ram-probe-r5
python prototypes/reset-ff-ram/test_probe.py --probe BUILD/reset-ff-ram-probe-r5
```

The builder requires a fresh output directory. Its manifest pins the exact
b07 F/MON components, runtime symbols, probe and builder sources, all binary
variants and S19 streams, and the first 16 bytes of private MON B prompt
`$B160`. The code occupies `$2000–$2330` inclusive, with entry `$2000`.
The fixed public console PUTC veneer is `$F00D`. Successful software cases
jump directly to the pinned prompt, avoiding console reinitialization.

Cases and interpretation
------------------------

| ID | Operation |
|---|---|
| 00 | Snapshot and safe high-preload cleanup |
| 01 | Exact CON_INIT console writes: CTRL=0C, DDRB=0C, DDRA=00 |
| 02 | Release WR only; settle; preload WR high; enable WR output high |
| 03 | Drive A5 and perform a valid WR falling strobe |
| 04 | Drive 00 and perform a valid WR falling strobe |
| 05 | Raise WR; release WR and settle; preload low; enable low while DATA is undriven |
| 08 | Emit READY, then halt with WR low and DATA input |
| 09 | Emit READY, then halt with WR high and DATA input |
| 0A | Emit READY, then halt with WR input and DATA input |
| 0B | Emit READY, then halt with WR high and DATA output driving A5 |

Case 05 deliberately supplies an undriven falling edge. Its observed byte is
not required to be FF: released DATA bias and bus keeper state are physical
variables. A released WR pin can remain at its previous level or move to an
external level. The offline model tests released WR at both static levels
and supplies FF for released DATA; those assumptions are explicit in its
receipt. No software case establishes the physical reset assertion edge or
the internal reset order of the installed VIA.

Normal cleanup leaves CTRL=0C, DDRB=0C, DDRA=00. It preserves WR high until
MON drives the first prompt character before its ordinary falling strobe.
Restoring a prior WR-low latch while DATA is undriven could itself create a
diagnostic byte, so this is intentionally not a claim of restoring hidden
ORB/ORA latches.

Arms emit exactly `\r\nRFP1 ARM XX\r\n`, with XX equal to the two-digit
uppercase case ID. They then set the final pin state, settle for 11,262 CPU
cycles (about 1.408 ms at nominal 8 MHz after branch expansion), snapshot,
commit ARMED, and enter a quiet RAM self-loop.
No text, hardware polling, console access or further capsule write follows
the commit. The host must receive the exact marker and wait for the final
stub to settle before asking the owner to press physical RESET. A marker
alone is not a readback of the final capsule. No reset should be requested
after a timeout or incomplete marker. Software cases should be observed
before choosing any physical arm.

Admission and preservation
--------------------------

Before console mutation the probe requires IER readback 80 (all enables
off), DDRA=00, DDRB=0C, PCR masked EE equal EE, ACR=00, RD high, FT-only
console mask 01, binary mode 00, TXE low, a nonzero nonce and a valid case.
Each READY character also checks TXE immediately before the public PUTC.
The host additionally pins the complete expected board state and readbacks.
An asynchronous TXE change can invalidate an output observation; an exact
host-captured marker remains mandatory.

The probe never writes flash, VIA PCR/ACR/IER, RTC, PIA or LEDs. It changes
only console CTRL/DDRA/DDRB/DATA, borrowed capsule RAM, the CPU stack and
existing NMI_HOLD at F4. Public PUTC uses existing monitor scratch ED.
Owner zero page 00–DF and all other application RAM are preserved by the
probe. Normal completion restores the entry NMI_HOLD byte. Armed/refused
halts retain NMI_HOLD=1 until reset.

The host's separately qualified 13-byte FTDI-selection shim runs through
ordinary monitor G, and bank readback uses ordinary B commands. Those
monitor paths can change transient LED and bank-PCR state. This differs
from the probe's own store restrictions. The host restores its borrowed
RAM, verifies full RAM repeatedly, then checks an ordinary BOTH startup;
it has no flash, persistent configuration or RTC setter path.

Snapshot rows read IFR and IER before ORB and ORA(no-handshake, 7FEF), then
read IFR and IER again. ORB/ORA accesses may acknowledge interrupt flags;
this side effect is deliberately exposed and admitted only with interrupts
disabled. The probe never reads FT DATA 7FE1, never drives RD low and never
polls/consumes pending input. Input-readback bytes do not recover latent
output latches. A failed admission commits REFUSED and halts quietly; it
does not try to print through a console whose preconditions failed.

Fresh capsule contract
----------------------

The host must clear all 256 bytes at 6400 and install a fresh, nonzero
16-byte nonce at 64F0 before **every** G2000. It must read back that
initialization. The probe preserves the nonce. No prior capsule is accepted
as evidence for the next invocation. The capsule survives BOOT_RESET's RAM
initialization, but its contents still require matching the fresh nonce,
case, checksum and commit.

| Offset | Value |
|---|---|
| 00–03 | ASCII RFP1 |
| 04 | Format 01 |
| 05 | Case ID |
| 06 | Snapshot row count (maximum observed 6) |
| 07 | Status: 01 done, 02 armed, 80 refused |
| 08 | Refusal reason, zero on success |
| 09 | Entry NMI_HOLD |
| 0A/0B | Case/status XOR FF |
| 0C/0D | Phase/phase XOR FF |
| 0E | XOR8 checksum: all 256 bytes excluding commit offset 0F XOR to zero |
| 0F | A5 commit, written last |
| 10 onward | 16-byte snapshot rows |
| F0–FF | Host nonce, unchanged |

Rows contain stage, DDRA, DDRB, IFR-before, IER-before, PCR, ACR,
ORB physical readback, ORA no-handshake readback, IFR-after, IER-after,
and five zero reserved bytes. Final DONE phase is F0. Final ARMED phase
is A0 OR case. REFUSED phase is E0. Reasons are 1 IER, 2 DDR,
3 PCR, 4 ACR, 5 RD, 6 console/binary, 7 nonce, 8 case, 9 TXE.

Offline evidence
----------------

`probe-cpu-tests.json` records 64 groups: 40 positive executions (two CPUs,
ten variants, two released-WR assumptions), 22 admission refusals and two
mid-READY blocked-output refusals. Each actual linked execution checks all
stores, unrelated RAM/flash, owner zero page, pending input, IFR-read order,
final pin state, every observed capsule-write prefix, and rejection of
all 256 individual one-bit byte corruptions. Quiet halts execute another
100 instructions with no I/O or RAM writes. Normal cases stop on arrival
at the pinned prompt before its ordinary output.

The checker uses the frozen reset-edge pin model and existing CPU models;
it executes every probe and console opcode. Two known cycle-table errors
are corrected locally after actual execution (BRA +1 and DEC absolute +3)
using the already qualified startup helper. This is a digital functional
model, not electrical reset timing, analog thresholds, bus keeper or
oscillator qualification. Physical findings must be reported separately.
