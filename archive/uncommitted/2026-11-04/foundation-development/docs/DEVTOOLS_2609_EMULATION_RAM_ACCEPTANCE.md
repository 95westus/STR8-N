# 2609 ASM/DBG: 816 emulation RAM acceptance

**Passed November 2, 2026: thirteen groups on2609/65C816 emulation.**
This closes the [RAM qualification scope](DEVTOOLS_2609_EMULATION_RAM_SCOPE.md).
It does not install developer images or qualify native16-bit operation.
The subsequent [reviewed installation and installed checks](2609_DEVTOOLS_INSTALLED_ACCEPTANCE.md)
also passed; the receipts below retain this earlier RAM-only scope.

The exact candidate2 archive was freshly extracted and verified:
`BUILD/devtools-g2-candidate2-20261102-r2/STR8N-DEVTOOLS-g2-candidate2.zip`.
SHA-256: `7cdf5b00322426ad00a8e456bc236d34294dfe8a7f876732113c3ac0362e69d2`.
All eight application BIN transfers used its extracted console backend:
ASM twice and DBG six times. No application binary was patched or rebuilt.

## Results

| Group | Observed result |
| --- | --- |
| Admission/preservation | Fresh owner escrow and four bank hashes matched; F was golden |
| Hardware context | Before/after E=1, eight-bit registers, D/DBR/PBR zero |
| Packaged ASM example | Assembly, LST/DUMP/S19, physical output readback, run and HOLD passed |
| ASM common subset | EQU/local labels, diagnostics, PHX/PLX/PHY/PLY, BRA and STZ executed correctly |
| Real emulation BRK | Registers, S/N, JSR/RTS, breakpoint hit and HOLD passed |
| CPU-specific refusal | All32 reassigned x7/xF bytes and17 additional unsupported816 opcodes displayed .BYTE and refused S/N without execution |
| Logical control flow | Conditional/indirect flow, JSR/RTS/RTI stack, atomic invalid-call and IRQ-mask guards passed |
| Breakpoints | All eight real breakpoint hits restored original opcodes |
| Public calls | PUTC N step-over printed its marker and returned through HOLD |
| Software services | Built-in BRK query, registration, callback register edits and nested-BRK frame passed |
| Exit/cancellation | X published stopped ZP edits; Ctrl-C, BC and hook/byte restoration passed |
| Final context | E/D/DBR/PBR contract retained |
| Final readback | Every byte of all four flash banks matched the pre-trial capture |

The assembler remains a65C02 cross-assembler. It can emit RMB/BBR opcodes
on an816; the trial checked that output without executing it. Running the
common subset is not a claim of an816 instruction encoder or native debugger.
The shared debugger deliberately refuses those reassigned opcodes. Free-running
C is not a sandbox; user fixtures must keep IRQ masked and return through HOLD.
Processor-mode assumptions are tied to the [WDC W65C816S datasheet](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf)
and confirmed by the recorded hardware probe and real BRK tests.

## Preservation and boundary

There were zero flash/journal, SPI-data/WORKSPACE or RTC-setting writes,
resets, power cuts or firmware rebuilds. WDC B0, installed utilities, MON A/B,
boot choices, board metadata, all27 journal records at sequence1089 and golden
F remain exact. B3:C/D/E/F tracked counts remain80/49/49/31. No other board
was accessed and published files were unchanged. RTC collection completed
first; its shared lease/window and priority were respected.

Fresh owner RAM0200-66FF, ZP00-DF, full6B00-77FF cache and original BRK/HOLD
hooks were restored and verified. Final state REC>, COM8 released, RTC eligible.

There is no permanent ASM/DBG installation on2609 from this trial. AP/02
installation, positive source-storage writes, physical GUI keys, source-only
rebuilding and native16-bit debugging were not tested here. Any later flash
installation or persistent fixture needs its own reviewed scope. The existing
2512 installation/persistence receipts remain separate.

Workspace evidence:

- `output/qualification/2609-devtools-g2-emulation-RAM-20261102-r1/report.json`
- `output/qualification/2609-devtools-g2-emulation-RAM-20261102-r1/completion.json`
- `BUILD/devtools-g2-candidate2-20261102-r2/ACCEPTANCE-2609-RAM.json`

The sidecar receipt binds this RAM acceptance to the unchanged ZIP. Its internal
pre-test qualification metadata is historical. Private owner/bank captures and
wire traces remain outside the kit.
