# STR8-N v2 W65C816 native acceptance

The alpha16 build emits
`BUILD/v2-alpha16/str8n-v2-alpha16-native-probe-2000.s19`. It is a 479-byte,
RAM-only probe assembled by WDC816AS. It changes no flash.

The probe verifies the minimum native vector ABI needed before native board
code can rely on STR8-N:

- transition from emulation mode to native mode with 8-bit A/X/Y;
- native BRK dispatch through `$FFE6`, the RAM stub, and `$7E12-$7E13`;
- physical native NMI dispatch through `$FFEA`, the RAM stub, and
  `$7E16-$7E17`;
- A, X, Y, stack position, and program-bank byte at both handler entries;
- native `RTI` returning to the interrupted program;
- return to emulation mode before using STR8-N console and HOLD services;
- restoration of the original native BRK, ABORT, and NMI pointers.

The native NMI pointer is published and restored while the CPU is still in
emulation mode under the `$00F4` NMI gate. The probe does not add a common
interrupt-dispatch layer or claim native callable monitor services.

## Board procedure

Start alpha16 on a W65C816 board and confirm this header:

```text
STR8-N 2.0a16 Bn 65C816
ABI 65C02 | 816E | 816N-VEC
Bn>
```

Load the probe with `L`, send the generated S19, then execute `G 2000`. Wait
until the probe prints:

```text
816N: PRESS NMI
```

Press NMI exactly once. Success is:

```text
V2 816N BRK/NMI / A-X-Y / FRAME / RTI: PASS
```

The probe then returns to the STR8-N prompt. A timeout or frame/register error
prints `V2 816N BRK/NMI PROBE: FAIL/TIMEOUT`. If pointer publication is already
busy, it refuses to start without changing the table.

Native COP, ABORT, a real peripheral IRQ, 16-bit accumulator/index widths,
nonzero direct page/data bank, and handlers outside CPU bank `$00` remain later
hardware tests. They do not need to be part of the first-board acceptance.
