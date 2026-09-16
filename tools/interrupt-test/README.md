# v1.34 hardware IRQ probe

Build with `make irq-test`. Run `python tools/test_irq_probe.py` to check the
linked probe's simulated IRQ, timeout, and busy-refusal paths, including its
S9 entry, cleanup, and absence of flash/bank-latch writes. It uses the existing
optional py65 test dependency.

Load `BUILD/v1.34/s19/str8n-v1.34-irq-test-2000.s19` through STR8-N `L`.
The probe refuses an already enabled VIA1 interrupt source. Otherwise it
temporarily installs a RAM IRQ handler and enables one Timer 1 interrupt.
The hardware IRQ traverses STR8-N's `$FFFE` vector and relocated dispatcher.
The probe checks A/X/Y before and after the handler, stack balance, a stacked
status with B/D/I clear, the timer interrupt flags, and successful RTI.
It restores the prior IRQ vector, ACR, and timer latches, disables its timer
interrupt, prints PASS/FAIL, and enters RESET. Timer phase is not preserved.

This probe performs no flash mutation. Physical NMI is tested separately at
the HIMON prompt with an operator action and a captured `NMI PC=...` report.
Do not combine interrupt testing with flash program/erase operations.

Register references: the [W65C02SXB memory map](https://www.westerndesigncenter.com/wdc/documentation/W65C02SXB.pdf)
and [W65C22 Timer 1, IFR, and IER definitions](https://www.westerndesigncenter.com/wdc/documentation/w65c22.pdf).

The separate v1.34 LED/worker probe now targets erased **B2:9**, preserving
the board's AP image in B2:8. `make board-probe-check` builds both probes and
runs their modeled tests. The worker probe requires two `Y` confirmations,
checks the entire scratch sector is erased, programs/verifies a 4 KB `$A5`
pattern, erases/verifies it back to `$FF`, then tests an invalid record write.
It halts for physical RESET after reporting its result.
