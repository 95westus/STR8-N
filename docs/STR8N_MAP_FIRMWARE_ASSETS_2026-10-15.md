> Historical prerequisite for the beta35/bf1/rc1 source checkpoint.
> Current soaks/RTC sampling are stopped; 2205/2512 remain off.

# MAINT 2.1 firmware-asset map labels

The owner requested replacing the unexplained B2:D/E `U` map entries and
flashing 2609 only. `tools/build_v2_map_assets.py` builds the isolated
`BUILD/v2-map-assets` candidate from the installed VERSION baseline.

The M1 grid now labels B2:D and B2:E `F` (firmware assets). Its legend names
the status formatter at B2:C800-D1FF and the local/board plus VERSION assets
in B2:E. B2:C retains `+`, because a saved WORK record continues into it.
The status formatter also starts in that sector, which the legend explains.
M2/M3 descriptions give the asset names and exact ranges. Recognized asset
sectors are described as reserved; this does not add a flash write guard.

Recognition is limited to the assigned bank/ranges and checks all four header
bytes plus the complete CRC seal. B2:D requires the status asset to validate;
B2:E requires both the local/board asset and VERSION asset to validate.
Invalid, absent or unrelated data retains the previous untagged/erased
classification. No firmware code in the mapped assets is executed. The map
uses RAM-resident validation code and performs no RTC/SPI operations or writes.

MAINT's program grows from 10,651 to 10,979 bytes and becomes version 2.1. Its
saved record remains in B1:8000-AFFF. Other saved programs, boot/status/local
assets, VERSION, CLOCK 1.7, monitor slots and recovery retain their binaries.
Installation rewrites MAINT's three sectors and B3:C wear metadata, preserving
configuration values and committing the MAINT record header last.

`tools/test_v2_map_assets.py` executes all three views from the planned saved
record, preserving flash/device snapshots and the editor buffer. Fault cases
cover absent/corrupt-header/corrupt-CRC status, local and VERSION assets, and
matching bytes placed in an unrelated bank. The exact installer is rehearsed
against a fresh, twice-compared complete backup before hardware execution.

Deployment tool: `tools/deploy_v2_map_assets.py`. Evidence:
`output/qualification/map-assets-2609-2026-10-15/`.
Installation completed on 2609 only. After the owner pressed physical RESET,
all four flash banks (131,072 bytes) matched the planned image exactly. The
live M1 grid showed `B2 . . S S + F F .`; M2 and M3 displayed the firmware
asset names/ranges and reserved status. VERSION still reported monitor B,
generation 00000025. The tool returned to B3 and released COM8.

The physical map transcripts, successful post-reset report and four complete
flash readbacks are in `upgrade/` under the evidence directory. B0 and B2
remain byte-identical to the fresh backup; only MAINT's B1 allocation and
the B3:C configuration/wear journal changed. Configuration values are retained.
