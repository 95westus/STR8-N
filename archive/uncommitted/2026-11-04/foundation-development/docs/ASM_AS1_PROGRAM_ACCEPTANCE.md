# 2512 AS/1 PROGRAM source persistence: passed

November 2, 2026. The owner-approved320-byte source-persistence trial passed
on2512/65C02 with the accepted resident ASM RAM packet, installed MON B g10
and the admitted SP/g3 provider. F remained golden. These are development
RAM tools; they are not installed in flash or included in published downloads.

The actual assembler saved AS1TRY to free PROGRAM slot4 at00140-0017F and
payload page00800-008FF. The66-byte AS/1 capsule contains58 packed source bytes,
an inner source CRC and the unchanged AS/1 header semantics. Independent reads
verified the exact capsule, committed SP directory entry, payload CRC and
unchanged payload-page tail. Existing CLK, CLOCK and NFCOPY records remained.

| Live check | Result |
| --- | --- |
| SAVE SRAM AS1TRY | Exact expected capsule, header and payload CRC passed |
| Fresh ASM-session LOAD | Source survived replacement of CPU application RAM; LIST and reassembly reproduced the program |
| Dirty LOAD cancellation | NO retained the edited source |
| CRC fault | A temporary one-byte payload change was refused before copying over the existing source |
| Repair | Restoring the byte allowed LOAD and assembly; native Dump independently verified all8 output bytes |
| Cleanup | All320 original SPI bytes and the entire576-byte primary/directory region were restored/read back exactly |

The restored source assembled to `A9 42 8D 00 18 4C 67 7E`: a marker write
followed by public HOLD. This trial independently checked the emitted bytes;
execution/HOLD had already passed in the initial ASM/DBG RAM trial.

Fresh owner RAM0200-66FF, ZP00-DF and borrowed cache7000-74FF were restored and
read back. Original BRK/HOLD hooks stayed unchanged; B3/F/images/settings/
boot-wear history matched their original readback. No test record remains.
There were zero flash/journal/F, WORKSPACE, EEPROM or RTC time/trim/ACK writes,
zero resets/power cuts and no other-board access. RTC collection completed
first; the trial then used its own lease. Host RTC admission passed after
cleanup without another board connection or a campaign/baseline change.

The accepted ASM packet is the same r6 binary used by the initial RAM trial:
`BUILD/asm-base1-g1-r6/ASM-BASE1-RAM.bin`, SHA-256
`b05b71cf95019fb860bce175302d24a39664676d54bb1ee8b21c742f556fe12b`.
The bounded737-byte restoration helper was built once for this exact five-block
scope. No assembler-candidate correction, F/MON rebuild or CPU simulation was
needed during the live trial. Published archives and earlier receipts remain
unchanged.

Private receipts, relative to the workspace root:

- `output/qualification/2512-AS1-PROGRAM-scope-20261102-r1/approval.json`
- `output/qualification/2512-AS1-PROGRAM-trial-20261102-r1/report.json`
- `output/qualification/2512-AS1-PROGRAM-closeout-20261102-r1/completion.json`

Final REC>,COM4 released, owner/SPI restoration guards clear and RTC eligible.
The allowance covers this completed temporary fixture, not future targets.

Remaining: the flash-source adapter; final ROM placement and normal MON/APPS/R
entry; reviewed flash installation; broader debugger guards/cleanup,816 and
a later extracted developer kit. The [initial RAM acceptance](ASM_DBG_2512_RAM_ACCEPTANCE.md)
retains the debugger and editor evidence and its exact limits.
