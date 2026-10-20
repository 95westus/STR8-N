# ASM and BRK hardware requalification supplement

This supplement adds physical-board results for the unchanged v1g image to the tested [ASM examples](ASM_GUIDE.md#debugging-ram-programs-with-dbg1) and [BRK ABI](ABI_REFERENCE.md#dbg1-brk-functions-and-registrations). Those manuals remain byte-identical to the sources executed by the offline qualification. No board command is executed by this documentation.

Both **2604 (65C02)** and **2609 (65C816 E=1)** passed in MON A and MON B before and after v1g rollback/reinstall. The 816 observer verified E=1 before and after each slot, zero PBR/DBR/direct page, IRQ masked and decimal clear. Native applications/debugging were excluded.

| Feature | Recorded result |
| --- | --- |
| Onboard ASM | ASM 0.5 assembled/exported S19 and executed the verified eight-byte RAM program through the public put-character/HOLD entries |
| `BRK xx` | Automatic debugger entry, two-byte signatures and the `$80` query passed |
| `C` / `S` / `N` | Continue, single step and JSR step-over passed |
| Shared `D` / `M`, `U` | Dump, RAM edit and disassembly passed |
| Persistent breakpoints | All eight hit twice per slot pass; ninth-entry refusal, clear, X/HOLD cleanup and unchanged program bytes passed |
| System/user registrations | Four system entries and sixteen user entries; separate capacity, callback arguments/results, missing/duplicate/protected-ID refusals and nested-BRK protection passed |
| `$82` unregister | `$00` refusal in uninitialized, empty, partial, system-only and full tables; invalid IDs and C0/FE boundaries passed |
| `$84` counted text | Actual `$64FF` endpoint, final one/two bytes, both carry states, zero count, crossing rejection and ordinary page crossing passed |
| Supported apps | MAINT, ASM, UCHESS, SRAM, WORK, EDU and CLOCK checks passed |

Across both boards and initial/final passes: **144 original registration scenarios, 168 focused `$82/$84` cases and 128 persistent breakpoint hits**. All 88 transaction transfers verified, with full-bank verification and original RAM restoration after each transaction. RAM capacity is unchanged; full original 25,344-byte application archives were verified at hardware closeout.

System IDs remain `$A0-$BF`, registered through the protected system entry; user IDs remain `$C0-$FE`, registered by `$81` and removed by `$82`. The four system slots use 16 existing reserved bytes and the sixteen user slots use 64; they do not consume application RAM. Unknown signatures stop for inspection. Built-in service semantics are unchanged except for the two documented fixes.

The optional released `$66FF` RAM limit was exercised offline. Physical-board endpoint cases used the boards' actual `$64FF` descriptor, without changing optional-service ownership.

The owner-stopped expanded R6 workload and final restoration/drift passed in their recorded scope. Both boards covered all 40 rotating ASM sources, all built-in BRK `$80-$84` each cycle, targeted registrations/edges and full debugger smoke. See [soak closeout](DBG1_SOAK_CLOSEOUT.md). Promotion remains held. See [complete board results](DEBUGGER_BOARD_RESULTS.md) and the [machine-readable summary](../../qualification/summary.json).
