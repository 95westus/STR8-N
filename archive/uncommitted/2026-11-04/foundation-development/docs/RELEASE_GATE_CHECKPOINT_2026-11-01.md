# Release gate checkpoint after the FLASH correction

Two additional development gates passed on2512 without new flash writes.
F remains the exact frozen STR8N-F0.3.0 g1 BASE1/PR05 image.2609 stays on hold;
2205/2604 and published downloads remain untouched by this work.

| Gate | Accepted evidence | Remaining limit |
|---|---|---|
| Saved EDU integrated startup/help in RAM | Nine live cases covering default/saved modes, conflicting records, missing/corrupt helper refusal, shared help and warm session retention; exact B3 and owner restoration | No real ED/1 record was saved; ROM packaging/install and reset persistence remain open |
| Development terminal RAM S19 protocol | Checked file admission, Ctrl-C, normal load and independent low/high RAM readback on2512; host error/cancel/acknowledgement tests and hidden Tk modified-key routing | Physical Shift-key acceptance and the next extracted kit remain open; sender refuses dense flash S19 |

The saved-EDU trial uses the linked gE RAM monitor, CPU-RAM fixtures and the
existing helper. It does not change the installed gD MON images. The initial
oversized host packet was rejected before sending; the original failure and
verified owner-restoration receipts remain. The compact retry retained the
existing admitted raw-BIN limit.

Terminal0.1.2 adds Shift+F2 to choose an ASCII S19 file and Shift+F3 to send
only at the RAM loader's observed prompt. F2/F3/F4 keep their BIN behavior.
S19 completion waits for board acceptance and a monitor prompt. Host completion,
board acceptance and independent readback remain separate facts. No S9 entry
is auto-run, and earlier complete records can remain after cancellation/error.

Both hardware trials finished at REC> with COM4 released, fresh owner RAM/ZP
restored/read back, and exact full B3 preservation. No metadata, boot/wear,
SPI SRAM/WORKSPACE or RTC-setting/trim/PF-history writes occurred. No reset or
power cut was needed. RTC host admission still passes; its scheduled catch-up
after the earlier STATUS repair was independently accepted from the17:15Z capture. No RTC
baseline, schedule or collector rewrite was made here.

The next feature work is confirmed saved EDU and named flash/PROGRAM transfers,
plus the remaining BOOT/CLOCK administrative and storage-manager return gates.
Any new persistent write or installation still needs an exact reviewed scope.
Factory execution deliberately replaces F and remains outside golden-F work.
ASM/DBG and reference-board rollout remain separate. See
`UNIFIED_ENVIRONMENT_REMAINING.md` for the broader release checklist.

Private receipts:

```text
output/qualification/2512-EDU-startup-RAM-20261101-r2/report.json
output/qualification/2512-EDU-startup-RAM-20261101-r1/owner-recovery/report.json
output/qualification/2512-console-S19-20261101-r1/report.json
BUILD/mon-gE-settings-RAM-integration-r1/manifest.json
```

Details: `EDU_SETTINGS_RAM_CHECKPOINT.md` and `SERIAL_CONSOLE.md`.
