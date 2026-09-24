# STR8-N V2 alpha17 optimization board test — 2026-09-23

Alpha17 reduces the alpha16 implementation without changing the public ROM or
RAM ABI. The fixed signatures remain `SN 02 00`, `RA 01 0D`, and `CA 01 17`.
All public entry addresses remain unchanged.

The changes are mechanical:

- place the eight-byte CAPS_QUERY body in the alignment gap immediately before
  the fixed `$7E60` RAM signature;
- store the shared `; press Y to soft reset` suffix once;
- let the public RESET entry establish IRQ, decimal, stack, and CPU state;
- test the selected 0/1 console byte directly during initialization;
- use A for the ACIA delay outer counter while continuing to preserve X/Y.

| Area | Alpha16 | Alpha17 | Saved |
| --- | ---: | ---: | ---: |
| Resident image | 3820 bytes | 3789 bytes | 31 bytes |
| RAM worker | 767 bytes | 744 bytes | 23 bytes |
| Vector/RAM ABI image | 204 bytes | 196 bytes | 8 bytes |

The resident now ends at `$FECC`. `$FECD-$FFDF` is erased, including the full
reserved `$FF00-$FFDF` expansion page. The RAM worker has 24 bytes free in its
fixed `$7900-$7BFF` allocation, and `$7EE4-$7EFF` provides 28 reserved bytes in
the vector/public-entry page.

`make v2-check` passed all boot, all-bank RAM ABI, ACIA, migration, monitor,
load, flash, configuration, timing, interrupt, and native static checks. The
tests include both self-edit result strings and their software-reset path.

Alpha17 was then installed on board 2205 through the guarded B2:F backup path.
The updater verified its backup and target, then booted:

```text
STR8-N 2.0a17 B3 65C02
ABI 65C02 | 816E | 816N-VEC
B3>
```

The physical RAM-only probe passed:

```text
B0 B1 B2 B3 RAM ABI: PASS

STR8-N 2.0a17 B3 65C02
ABI 65C02 | 816E | 816N-VEC
B3>
```

The temporary B2:F backup was erased and read back as `$FF`. B3 readback
showed executable bytes through `$FECC`, erased bytes beginning at `$FECD`, and
an erased `$FF00-$FF0F` sample. B1 retained its `SR 02 03` STR8-N 1.35
signature, and B0 retained its `57 44 43 00` WDCMONv2 header.

| Artifact | SHA-256 |
| --- | --- |
| Alpha17 E-F image | `7A4C3B13638793C9B14426100E8A478B7559088C23C9F6B22293C29AB12EB1DA` |
| Guarded B3 updater | `5402C49F899127612D56E0DC7AA785B9F6BA29D05D6F98B4059B20BA57A4FF8D` |
| Cross-bank RAM ABI probe | `73EA969EB79F2A592EF9791CEDEB1720305D66C221C8B2379851A749AFBFD409` |

Board 2205 now contains WDCMONv2 in B0, R-YORS/HIMON and STR8-N 1.35 in B1,
an erased B2, and STR8-N 2.0a17 in B3.
