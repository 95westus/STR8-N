# R-YORS Integration Boundary

STR8-N owns its source, worker, payload tools, 4K protected-sector layout, and
ABI documentation. R-YORS consumes an exact external artifact and must not
compile a second live STR8-N source copy.

STR8-N publishes:

```text
BUILD/bin/str8n-bank3-f000-ffff.bin
BUILD/s19/str8n-worker-0200.s19
BUILD/str8n-manifest.json
```

R-YORS's `STR8N.lock.json` records the required repository commit, top-sector
SHA-256, worker SHA-256, worker RAM span, and record-service version. Its build
verifies those values plus the protected layout, retired gates, fixed service
addresses, and vectors before constructing Bank 3.

The normal two-folder workspace is:

```text
parent/
  R-YORS/
  STR8-N Refactor/
```

From R-YORS, `STR8N_HOME` may name a differently located checkout. A release
build requires the exact locked commit and a clean STR8-N worktree.

```text
make -C SRC str8n-external-check
make all STR8N_HOME="C:/path/to/STR8-N"
```

The Bank-3 ownership boundary is:

```text
$8000-$BFFF  ASM-F2, built by R-YORS
$C000-$EFFF  HIMON, built by R-YORS
$F000-$FFFF  STR8-N, verified external 4096-byte BIN
```

R-YORS code that calls STR8-N binds only to the published interfaces in the
[Technical Guide](TECHNICAL_GUIDE.md#public-interface). Its RAM helper at
`$0500` remains above STR8-N's complete `$0200-$0453` worker; the build rejects
an overlap if that contract changes.

The resident STR8-N `L` command is an operator recovery path, not a new public
ABI. It loads and immediately executes S19 programs in `$2000-$7AFF`. HIMON's
own `L` and `L G` commands remain R-YORS features with their separate monitor
policy.
