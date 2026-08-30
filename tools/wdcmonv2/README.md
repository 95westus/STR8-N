# WDCMONv2 Migration Tools: Provenance Boundary

These are independently authored STR8-N migration, archive, verification, and
host-bridge tools. They interoperate with WDCMONv2 through documented protocol,
memory-map, and hardware-interface facts. They do not contain or grant rights
to WDCMONv2 source or firmware.

The distributable migration kit must contain only allowlisted STR8-N source,
tools, documentation, and STR8-N artifacts. It must not contain a stock
WDCMONv2 binary, an assembled WDCMONv2 image, an owner-local bank dump, a dense
capture transcript, private WDC source, or private recovery material. Locally
created archives remain owner-local unless the relevant copyright owner gives
an express redistribution grant.

A source-level audit on 2026-08-30 found:

- no exact run of five or more assembly instructions shared with the privately
  supplied WDCMONv2 assembly source;
- no identical non-comment line of 30 or more characters shared between the
  Python host bridge and WDC's supplied Python uploader;
- no tracked WDCMONv2 firmware image or owner bank archive in STR8-N; and
- explicit package-manifest and verification gates declaring that WDCMONv2
  firmware and local archives are absent.

Generic W65C02 instruction idioms, hardware addresses, command values,
signatures, and wire framing are compatibility facts and are not evidence that
the WDC implementation was copied. This audit is a technical provenance record,
not legal advice. See
[`docs/WDCMONV2_MIGRATION_PROVENANCE.md`](../../docs/WDCMONV2_MIGRATION_PROVENANCE.md)
for the complete policy and release boundary.
