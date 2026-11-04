# STR8N-F F compaction checkpoint r1

Unpublished **b15c1 / PR05** candidate, derived from the v0.2.0 source release.
Current binaries: `firmware/payload/`. Single-build output and listings:
`build/fcompact-r1/`.

| F layout | Released b15 / PR04 | Candidate b15c1 / PR05 |
| --- | ---: | ---: |
| Linked body, including embedded worker/vectors | 3669 bytes | 3581 bytes |
| First unused tail address | FE55 | FDFD |
| Usable contiguous tail through FFDF | 395 bytes | 483 bytes |

**88 bytes recovered.** Fixed F03C-F03F and FFE0-FFFF remain reserved. F is
still exactly 4096 bytes. Public ROM/RAM entries, worker/vector bytes, receive
timers, first-byte Ctrl-C handling and the C/D boot-record format are preserved.

Private F routines move. Use matching **PR05** CONFIG, OPAQUE, READBACK,
monitors and other supplied utilities. Old PR04 private callers are
incompatible; PR05 F refuses PR04 monitor slots. Public-ABI-only user programs
remain compatible. Generation 8000000F is retained so existing monitor-default
records match the rebuilt monitor generations.

No boards were accessed or flashed. No CPU simulations or second firmware
build were run. This checkpoint has static layout/dependency checks and **has
not been execution-qualified or released**. Published v0.2.0 is unchanged.

See [CANDIDATE.md](CANDIDATE.md) for component bindings and the later hardware
checkpoint. Inherited operator documents describe the v0.2.0 baseline.

## Check or rebuild

```text
python tools/check_fcompact.py
```

That checks existing files only. For a later source change requiring a build:

```text
python tools/build_system.py --candidate --out build/changed-source
```

Use a fresh output directory. There is no automatic second build, simulation,
serial access or publication. The inherited release packager refuses this
unqualified candidate. Historical evidence is retained under
`validation/v0.2.0-reference/`; it does not qualify the new firmware.
