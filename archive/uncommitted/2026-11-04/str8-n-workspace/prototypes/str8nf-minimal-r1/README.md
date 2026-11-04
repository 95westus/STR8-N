# STR8N-F minimal release candidate: MIN1 / PR05

The accepted layout gives opaque images **116 KiB** of the 128 KiB flash:

| Region | Role |
| --- | --- |
| B0, B1, B2:8-F | Opaque images |
| B3:8/9/A/B/E | Opaque images |
| B3:C/D | Boot settings and erase-accounting journal |
| B3:F | Exactly 4096 bytes of bootstrap/recovery |

No monitor, VERSION/EDU provider or SPI SRAM is required. Existing contents are
owner data until explicitly assigned and backed up; the layout does not erase
or populate user sectors. A/B are no longer reserved monitor slots in MIN1.

F is frozen at the preceding b15c1 / PR05 compaction checkpoint:
`ccb923340528a0764102fc270e39dd07c95a76569e19c4f60169e081712164d3`.
It has 483 usable tail bytes and is not rebuilt for the target-policy change.
The matching OPAQUE RAM tool and host serializer admit B3:A/B while preserving
the C/D/F exclusions. The optional legacy monitors and providers remain source
references; they are not installed by this minimal flow.

This is a development checkpoint, **not a published or hardware-qualified
release**. Published v0.2.0 remains unchanged. No device access is part of the
source/build work here.

## Release contents and status

- Frozen 4096-byte F BIN: present; no additional F optimization planned.
- MIN1 OPAQUE RAM tool: built once from the changed admission policy.
- CONFIG and DEMO RAM tools: reused without rebuilding.
- MIN1 READBACK: new fixed-range owner-RAM/ZP restore service and host client.
- Verbose WDCMONv2 RAM engine, read-only exporter, planner and live host CLI:
  built/prepared; explicitly gated as unqualified pending a hardware trial.
- C/D provisioning: required for factory/vendor-occupied C/D; CONFIG `I` is
  deliberately blank-only and is not a vendor-code conversion command.
- Physical migration/reset/recovery, normal/cancelled BIN loading, journal
  persistence, opaque write/readback/boot and preservation: pending acceptance.

See [the release contract](docs/MINIMAL_RELEASE.md), [layout.json](layout.json)
and [the MIN1 build](tools/build_minimal.py). The inherited full-system build,
profiles and old documents are reference material, not the MIN1 installation
procedure. The inherited release packager refuses this candidate.

## Incremental build policy

The F/worker/vector components remain frozen. A changed RAM utility is rebuilt
on its own. No routine CPU-model suite, reproduction build or board visit is
performed. The MIN1 policy build is:

```text
python tools/build_minimal.py --out build/fresh-policy-output
python tests/test_minimal_policy.py
```

Use a fresh output directory only when a source change requires a build. The
host tests check the exact writable sector set, packet CRCs and protected/malformed
targets; they do not execute a CPU or contact hardware.
