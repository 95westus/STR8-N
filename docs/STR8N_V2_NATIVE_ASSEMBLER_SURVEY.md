# Native assembler alternatives for STR8-N v2

Research date: 2026-09-27. Documentation/source survey; no candidate was ported,
built, benchmarked, or qualified on STR8-N during this survey.

## Conclusion

There are credible native alternatives. Krusader is the strongest verified
small-footprint reference; G-Pascal's assembler is a useful full-W65C02 source
candidate. Neither reviewed interface supplies the complete retained-dependency,
cross-bank, replaceable-service runtime we want. Compare extracted builds before
choosing either over a reduced ASM-F2. Under-4K absolute assembly is not a
measurement of a complete relocatable-object toolchain.

The live 6502.org tools/source pages failed to load through the research browser.
Its [published homebuilt directory source](https://github.com/6502org/6502.org/blob/main/app/views/Contents/homebuilt.html)
was accessible and points to native environments including DOS/65, both CP/M-65
projects, and S/O/S SyMON II. Primary project documentation was used below.

## Candidates

### Krusader 1.3 — small symbolic assembler/editor

The author documents an editor, single-pass symbolic assembler, disassembler,
and debugger in under 4K, with source and binaries supplied. Runs on 6502 and
has a 65C02-targeting variant. The original package has little platform-specific
code, making it a plausible extraction/port candidate.

The manual limits labels to six alphanumeric characters, 256 globals, 32 locals
per module, and 85 forward references. Forward references cannot use the low/high
byte extraction operators. Its 65C02 variant omits BBR/BBS/RMB/SMB and WAI/STP.
The fixed local/forward-reference tables occupy 1K, with additional global
symbols, source, and output RAM. Existing F000/high-RAM and zero-page placements
would need changing to coexist with v2.

Its documented module directive is not evidence of a relocatable object/import
format. We would need to add retained relocations, external dependencies, longer
service names or an external-name mapping, and the new runtime interface. Source
availability was verified; explicit reuse-license terms were not established by
this survey.

Sources: [author's project](https://thewessens.net/collection/apple1/Krusader.htm),
[author's manual](https://thewessens.net/collection/apple1/krusader13.pdf).

### G-Pascal assembler — full W65C02 coverage

Nick Gammon's on-board package supplies assembler, editor, and Tiny Pascal, with
MIT-licensed source. The project documents all W65C02 instruction/operand forms
and expression evaluation. Its assembler manual places generated code after
source by default and permits choosing an output address with ORG.

That ORG facility is assembly-time placement; it does not establish retained
relocation/import records for post-assembly linking. No assembler-only emitted
size was verified. Extract assembler plus expression/symbol/editor dependencies
before claiming a footprint advantage; the full Pascal package is not the
appropriate comparison.

Sources: [repository](https://github.com/nickgammon/G-Pascal),
[assembler manual](https://www.gammon.com.au/G-Pascal/assembler.htm).

### David Given's CP/M-65 assembler — native, but RAM-heavy for this use

The project includes a native assembler and relocatable system binaries. The
README states approximately 20kB is needed to run the assembler at all, increasing
with program size. It is written in C and customized for CP/M-65. This figure is
a runtime-memory requirement, not an assembler ROM-size measurement. System
relocation is not the same feature as dynamic service rebinding. Not the leading
choice for reducing our working-memory footprint.

Source: [project README](https://github.com/davidgiven/cpm65).

### Dietrich Lausberg's CPM-65 assembler — native source, OS integration needed

This separate project supplies a native 6502 assembler and its system/application
assembly sources. The project is linked by 6502.org. Useful as a native toolchain
reference, but assembler-only size, complete W65C02 coverage, and appropriate
linkable-object support remain unverified. Porting must replace its system/file
interfaces. Do not confuse it with David Given's project.

Source: [project repository](https://github.com/Dietrich-L/CPM-65).

### Tali Forth 2 / tasm65c02 — alternative interactive environment

Tali Forth runs on 65C02 and contains an assembler using SAN, with postfix operands
and explicit addressing-mode suffixes. Its assembler derives from tasm65c02.
Useful for the proposed interactive service/word model if a Forth environment is
desired. It brings a language/runtime choice, and no assembler-only footprint or
our required relocatable-module/rebinding format was verified here.

Source: [Tali Forth manual](https://github.com/scotws/TaliForth2/blob/master/docs/manual.md).

## Related object-format reference

XA is a cross-assembler, so it does not meet the on-board assembler requirement.
Its o65 format and included 6502 relocating loader are nevertheless worth studying
alongside AP v2 when defining our object/linker boundary. Do not assume either
format already encodes all bank-aware service replacement semantics.

Source: [XA README](https://github.com/fachat/xa65/blob/master/xa/README.1st).

## Proposed comparison before changing direction

Compare a reduced ASM-F2, Krusader-based core, and extracted G-Pascal assembler
using the same requirements:

1. Complete required W65C02 instruction forms and invalid-input handling.
2. Labels/expressions, including forward low/high-byte references.
3. External service imports and retained typed patch sites.
4. Load at two different addresses and call through bank-aware gates.
5. Rebind a provider without source reassembly.
6. Measure dependency-complete code/data and peak RAM for identical samples and
   declared symbol/fixup limits; show editor/debugger costs separately.

Recommendation: keep the layered runtime/linker proposal, but treat assembler
selection as open until these measurements. Krusader proves a very small native
interactive assembler is possible; it does not prove that adding our object and
linking requirements will preserve that size.
