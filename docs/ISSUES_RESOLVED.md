# BASE1 closeout and remaining boundaries

The component work and reviewed 2512/65C02/FT245 cases are closed. The
[status matrix](RELEASE_STATUS.md) and individual receipts are authoritative.

Resolved/implemented:

- Frozen F name/version/generation and identity descriptor; OS/service status separate.
- Matching BASE1 RAM tools/host markers and size/SHA bindings.
- RAM MAP M1/M2/M3, WDC resident recognition, and C/D/F-only reserved layout.
- Persistent bank enable/entry/default and conservative erase-attempt journal.
- Python terminal F1-F12, native dialogs, initial Ctrl-C, normal BIN transfers
  and disconnect deferral; tested console code is unchanged.
- Known-b15 SNBT-preserving F upgrade, verbose WDC migration and programmer-F
  C/D provisioning, each with its own tested 2512 scope.
- Source-bound chip-idle C/D recovery lab cases and independently verified
  image/settings/RAM restoration. Lab packets are not a generic repair utility.
- Candidate packaging now includes the terminal, provisioning/upgrade hosts,
  prebuilt engines and wrapper dependency under the same paths as tested.

Remaining:

1. **Test migration and operator use from the exact extracted 0.3.0-rc1 ZIP.**
   Archive construction/integrity checks do not qualify that live route.
2. Other CPUs/adapters/hosts, occupied layouts, legacy image execution and
   vendor startup/peripheral effects beyond the recorded 2512 cases.
3. Interrupted provisioning, arbitrary damaged/conflicting records and
   electrical mid-pulse behavior. No further deliberate power cuts are planned.
4. Public release/tag/upload after the chosen release gates close.

Normal recovery assumes golden F. Interrupted-F runtime testing is excluded
by the owner's scope decision, not represented as a hardware pass. The
source migration commands retain --allow-unqualified for broader limits.
Older kit ZIPs and 2205 remain untouched by current packaging.
