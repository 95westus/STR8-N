# Public R-YORS on STR8-N v2: next-layer boundary

This records the interface work for the public HIMON/ASM-F2 `00.0915(2324)`
release. It does not change the STR8-N v1.35 branch, publish a pull request,
install R-YORS into flash, or expand the RC1 hardware claim. The reference
artifacts are the separate HIMON and ASM-F2 release ZIPs under
`C:/SRC/R-YORS/RELEASE/`.

STR8-N v2 owns board selection, flash installation, and recovery. A guest
owns its own RAM, console use, and application behavior after handoff. The
public R-YORS images were built for STR8-N v1.34, so the boundary needs an
explicit adapter before claiming full v2 compatibility.

## Interface map

| Public R-YORS behavior | V2 boundary | Next-layer action |
| --- | --- | --- |
| HIMON clears `$0100-$7EFF` and zero page at cold entry. | This clears v2's worker, RAM call table at `$7E60-$7E8A`, state, and vector code. | Treat HIMON as the active owner; enter v2 through full RESET at `$F004` after selecting its bank. Do not call v2 RAM entries or HOLD from HIMON. |
| HIMON `STR8` writes v1 restart cells and jumps `$F000`. | V2 stores `SN 02 00` at `$F000`; its RESET entry is `$F004`. | Add version-aware HIMON return code in a separate R-YORS v2 adapter. Preserve the v1 return path for v1 boards. |
| HIMON `L` requires the v1 `SR` record service. | V2 deliberately does not expose that parser service. | Keep HIMON `L` unavailable on v2 until a HIMON-owned S19 parser is supplied and checked. Use STR8-N v2 `L` before guest handoff. |
| HIMON/ASM/AP flash and bank tools use v1 directory, WORK, backup, and AP placement policy. | V2 has no directory or journal and reserves its configuration in resident `$EFF0-$EFFF`. | Keep persistent AP/flash operations out of the first compatibility pass. Design explicit destination and recovery policy before enabling them. |
| HIMON publishes `RY` service vectors at `$7E02-$7E1C`; ASM-F2 consumes them. | This is a guest-owned HIMON/ASM ABI, not a v2 ABI. | Keep ASM and RAM-only AP use inside the HIMON session; validate with the public release image and a board transcript. |
| R-YORS combined `8-E` image is intended for Bank 3 on v1. | V2 `I` protects the resident configuration window. The public combined S19 has all `$FF` at `$EFF0-$EFFF`, so its image data does not require that window. | Host-verify the exact release S19, then separately authorize and qualify any Bank 3 `8-E` installation. |

The current RC1 `.a` carriers use only ASM-F2's `ORG`/`DB` input format. The
Bank 3 identity utility uses direct FT245 I/O, restores the prior overlay,
and returns to HIMON. The guarded updater leaves HIMON and reenters v2 RESET
at `$F004` on pre-erase cancellation; an intact v2 RAM ABI is not assumed.
These focused paths do not establish general HIMON/ASM/AP compatibility.

## Ordered next proof

1. Preserve the public HIMON/ASM-F2 ZIP identities and validate their combined
   `8-E` S19 record checksums, dense range, S9 entry, and erased
   `$EFF0-$EFFF` reservation. Do this on the host before a board write.
2. Prepare a separate R-YORS v2 adapter for `STR8` return and HIMON `L`.
   Refuse incompatible v1 calls rather than interpreting v2 bytes as v1.
3. On a deliberately chosen W65C02SXB with recovery already read back,
   record the selected bank and exact flash ranges before any `I` operation.
   Keep the board's existing recovery sector until another recovery path is
   proven.
4. Qualify HIMON cold entry, ASM-F2 `ASM NEW`, RAM-only `.a` ingestion and
   `G 2000`, and return to v2 through full RESET. Capture the banner and
   the Bank 3 F readback after the session.
5. Qualify AP RAM load/link separately. Enable persistent AP install or guest
   flash writes only after their v2 bank and recovery policy is explicit.
6. Treat W65C816 and EDU runs as separate physical qualification. The public
   R-YORS release is a W65C02 baseline.

No change in this plan merges v2 into `main` or alters the v1.34/v1.35
release line.
