# Beta35 expanded local review kit

**STR8-N 2.0b35 generation 47, CLOCK 1.10, ASM 0.5; FT245/F30D.**
This is an offline source, payload, manual and planning review. It is not
release-qualified or permitted for installation. ACIA and crypto are deferred.

Start with [the four guides](docs/beta35/README.md) and
[remaining gates](REMAINING_GATES.md). The original source/payload review kit
is preserved byte for byte under `release/beta35/`, including its original
manifest and historical README. Outer notes describe the newer manual audit;
they do not rewrite that sealed source package.

The owner selected **bounded B-target maintenance routes only** for beta35.
See the [scope and physical acceptance plan](docs/STR8N_V2_BETA35_SCOPED_ACCEPTANCE.md)
and [machine-readable policy](release/beta35-prerelease/beta35-route-scope.json).
Broader upgrades and the A35 BATCH fix are deferred to a separate candidate.
This scope decision is not hardware qualification or installation permission.

Verify this extraction from its root:

```powershell
python -B verify_review.py .
```

Verification checks the exact allowlist, sizes/hashes, nested payload/source
seals, local manual links, and import/refusal behavior of the included stdlib
offline tools. The adjacent archive receipt supplies its SHA256. A matching
local manifest is integrity evidence, not publisher authentication.

The unchanged firmware source can be rebuilt with separately installed WDC
WDC02AS/WDCLN tools, using a new short output path:

```powershell
python release/beta35/build.py --out C:\tmp\b35build
```

The 26-link/18-payload clean reproduction was already passed on these exact
source bytes; its receipt is explicitly reused, not relabeled a fresh build.
Review summaries identify the old ZIP and source/payload identity. New manual,
example and tool packaging checks are separate. This archive contains no
board images, board backups, private measurement/transcript evidence, vendor
firmware, emulator dependencies or v2.1 source.

## Examples and tools

`examples/asm-print-a.numbered.txt` is the exact board-ASM editor example.
`examples/asm-print-a.s19` and `.bin` are its checked ten-byte output, not an
installer. In an authorized idle initialized monitor, use `ASM`, enter the
numbered source, `ASM`, then `QUIT` and `G 0200`. It prints `A` and returns via
HOLD. Loading/assembling replaces application RAM. Do not use it on a board
owned by a soak campaign.

The included tools are stdlib-only, local-file tools:

- `tools/inspect_beta35_source.py`: fingerprint/CRC inspection of an existing
  private four-bank archive, with explicit source active slot where applicable.
- `tools/plan_beta35_offline.py`: verified offline backup files and conditional
  logical B-target payload planning. It does not generate or run an installer.
- `tools/plan_beta35_journal_transaction.py`: semantic transaction functions
  for code review, not a CLI or hardware launcher.

Use each CLI's `--help`. Example planning requires an owner-supplied archive,
not included here, and `--payload-dir release/beta35/payload`. Keep outputs
outside this extraction so the exact-file verifier continues to pass.
Proposed images are not installation payloads. Receipt-bound model restoration
and private-fixture harnesses are deliberately not shipped as portable recovery
commands. No tool here authorizes serial access, resets or persistent-device
writes. See the [migration matrix](docs/STR8N_V2_BETA35_MIGRATION_MATRIX.md).
