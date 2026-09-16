# Load HIMON and ASM-F2 after STR8-N

The WDCMONv2 migration is complete when physical RESET reaches `STR8-N 1.34`
and the retained stock monitor starts through `J0`. It does not install
HIMON or ASM-F2. Physical RESET returns from the retained factory system to
STR8-N.

## Obtain the separate releases

Extract the HIMON and ASM-F2 release ZIPs from the
[R-YORS release distribution](https://github.com/95westus/R-YORS/releases).
Each ZIP includes its firmware, manuals, application sources, manifest, and
verification instructions. The STR8-N ZIP does not contain their firmware.
Use matching releases and verify both packages before installing.

The payloads are under `FIRMWARE/` in those separate archives:

| Payload | Bank 3 range | S9 meaning |
| --- | --- | --- |
| `ryors-v1.2-himon-bank3-c-e.s19` | `C-E` | Establish/retain entry `$C000` |
| `ryors-v1.2-asm-bank3-8-b.s19` | `8-B` | `$FFFF`: retain the existing entry |
| `ryors-v1.2-himon-asm-bank3-8-e.s19` | `8-E` | Combined first install, entry `$C000` |

Both component releases include the combined `8-E` image. Check its hash
against the supplying release. Do not substitute a full Bank-0/1/2 `8-F`
image: the resident installer cannot write protected Bank-3 sector F.
Keep the owner-local programmer backup and retained WDCMONv2 archive.

## First installation

The combined `8-E` image installs HIMON and ASM-F2 in one transaction.
At `STR8-N>` enter `I`, choose bank `3` and range `8-E`. For a new directory
row, enter the chosen TYPE and five-character DESC; existing complete rows
retain their identity and do not prompt for these fields. Confirm the printed
bank/range with `Y`, then send the complete combined S19 when `S19` appears.

Require six receive-time sector dots, `COMMIT? Y:`, then the final sector dot
and `OK` after confirming `Y`. Installation returns to the STR8 prompt; it
does not execute the S9 address. Enter `C` for a fresh HIMON cold start, then
`ASM NEW` from HIMON to enter ASM-F2. Record both visible release identities.

## Separate component installation or update

Install HIMON first when Bank 3 has no enrolled entry:

```text
STR8-N>I
B0-3: 3
RANGE: C-E
TYPE: 5A
DESC: RYORS
I B3 C-E WRITE? Y: Y
S19
..COMMIT? Y: Y.
OK
STR8-N>C
```

Send `FIRMWARE/ryors-v1.2-himon-bank3-c-e.s19` from the HIMON release.
TYPE/DESC above are illustrative first-enrollment values; omit those steps
when the board does not ask for them. Require the installed HIMON identity.
Return with HIMON `STR8` and its confirmation, then select `S` at the selector.

To install ASM-F2 in the already enrolled Bank 3:

```text
STR8-N>I
B0-3: 3
RANGE: 8-B
I B3 8-B WRITE? Y: Y
S19
...COMMIT? Y: Y.
OK
STR8-N>C
```

Send `FIRMWARE/ryors-v1.2-asm-bank3-8-b.s19` from the ASM-F2 release.
Its S9 `$FFFF` preserves the established `$C000` entry; it cannot be the
first image in an empty Bank-3 directory. At HIMON, enter `ASM NEW` and
require the release identity. A fresh cold entry avoids resuming RAM state
left by an older firmware build.

These are flash `I` payloads. STR8 `L` only accepts RAM `$2000-$7AFF` and
cannot load either flash component. Both install paths preserve sector F.

## Verify the resulting board

1. Press physical RESET, select `C`, and check the HIMON identity.
2. Enter `ASM NEW`, check the ASM-F2 identity, and run its documented smoke test.
3. Return to STR8, enter `J0`, and check the retained WDCMONv2 board identity.
4. Press physical RESET and require `STR8-N 1.34` again.

This is an optional component-installation procedure after factory migration.
It is not part of the migration transaction or a claim of new board testing.
