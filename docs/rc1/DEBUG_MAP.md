# DEBUG identity in sector maps — offline candidate

The dated reproduction commands below now live in the
[history archive](../../archive/README.md). Current firmware includes this
source through [the authoritative build](../../src/current/README.md).

B1:A (`$A000–$AFFF`) belongs to **DEBUG (DBG1)** in generation50.
It is not untagged owner storage. Existing installed MAINT may still show it
as untagged until a separately qualified future update is installed.

The local candidate uses the existing `F` firmware grid classification and
adds `B1:A F = DEBUG (DBG1)` to the grid legend. Both range and wear maps
show `DEBUG (DBG1) A000-AFFF` with the firmware `reserved` access label.
The renderer validates bank 1, sector A, the `DG`,1,1 header and the CRC of
all 4,096 bytes before assigning the identity. Corrupt or absent debugger
images retain the ordinary unknown/erased classification.

`tools/build_rc1_debug_map.py` copies the local v1g utility build sources into
`BUILD/rc1-debug-map` and patches only that separate candidate. Run it after
the v1g build, then run `tools/test_rc1_debug_map.py` with Python and py65
available in the existing local test-dependency directory.

Offline validation: WDC assembly/link succeeded within the `$8000–$D7FF`
utility domain. Linked 65C02 execution passed valid recognition, corrupt CRC,
corrupt header, resealed wrong header, erased sector and wrong-location
refusals, plus the DEBUG description check. Complete UI and bank-gate
integration, 816 execution and hardware qualification remain pending.

This is source and an unsealed linked utility component, not a complete
firmware image or preserving updater. Published release sources, packages
and firmware remain unchanged. No board was accessed or flashed.
