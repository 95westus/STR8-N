# Separate bf1 route helper

This offline-only RAM helper derives from the frozen beta35 prerelease
reservation helper. It is separate from the 2.0bf1 firmware payloads and from
the sealed beta35 generation-47 candidate. It does not allocate another
firmware generation or authorize a device installation.

The beta35 helper only accepts a reservation preference for fallback A. The
fresh 2604 route needs fallback B when replacing A after a coherent bf1 B
installation. This helper accepts only A0 or B0 and checks the reservation
generation against the corresponding A008 or B008 monitor generation. It
retains all-bank preflight, record hash/CRC, configuration checksum, erased
destination, prefix verification, last-byte commit and cleanup checks. The
offline planner also validates the exact fallback monitor CRC and all source
and candidate hashes before composing an image.

The linked helper is 585 bytes at 3000, below the separate wrapper at 3300.
Build with `tools/build_bf1_route_helper.py --out <fresh-short-directory>`.
The failed first assembly's short-branch diagnostic remains in `tmp/bfr1`;
the successful build is `tmp/bfr2`. Explicit branch expansions resolve the
longer validator without changing its conditions.

The original full route attempt is retained under
`output/qualification/bf1-2604-route-2026-10-17-r1`: B installation and
native/CLOCK BATCH passed, then A preparation was refused by the original
A-only helper before any modeled mutation. Its diagnostic is distinct from
a successful complete route. Read the current 2604 route checkpoint for the
completed new-helper evidence; an in-progress run is not a pass.

No serial launcher is provided. Physical/native/electrical acceptance and
installation permission remain false. Clocks/trims, 2512's preserving soak,
2205/2609 power state and ACIA/crypto deferrals remain protected.
