# v2.1 alpha ABI goals

Branch: `codex/v2.1-alpha`. Recorded 2026-10-16 from the owner's discussion.
This is the design scope, not a built firmware release or a hardware acceptance
claim. ATECC acceleration is deferred. No board update is implied. The first
[offline ABI foundation](STR8N_V2_1_ALPHA_ABI_FOUNDATION.md) is implemented and
model-tested; permanent discovery-anchor and boot integration remain pending.

CPU scope: W65C02 and W65C816 in emulation mode (E=1). Use "65C02-compatible
ABI" as the short profile name, with the explicit CPU/mode scope beside it.
The current W65C02SXB and W65C816SXB boards are hardware targets, not the name
or definition of the CPU ABI. Board-specific I/O remains discoverable through
services; this scope alone does not establish support for arbitrary boards.
Preserve the distinction between supported ABI profiles, the detected CPU,
and the current execution mode. Existing native interrupt support must not
advertise native-mode service calls; native-mode calls are outside this alpha.

## Uniform discovery with minimum size

Provide one stable discovery anchor and a versioned directory of public service
groups and their operations. Programs know the anchor and assigned numeric
service/operation IDs; they discover entry addresses rather than private linked
addresses. Retain explicit calling conventions, ownership and availability.
Private implementations remain private unless deliberately promoted to a public
contract. Command names and storage formats are distinct from callable APIs.

Combine system/capability/board information in a SYSTEM_QUERY record. Include
detected CPU and execution mode, supported and currently callable profiles,
console state, directory version, service support and current readiness. Keep
legacy CAPS_QUERY and BOARD_QUERY behavior through compatible entries where
practical. Report observed state without automatically probing or initializing
optional devices during a query.

Use compact numeric records, caller-owned result buffers and existing public
entry points where practical. Keep human-readable names optional. Do not promise
zero hardcoded addresses: discovery still needs one stable bootstrap anchor.
Audit all RAM ownership before assigning an address; do not reduce application
RAM merely to simplify directory placement.

Discussion budget, not an assembled measurement: approximately 0.5–1 KiB flash
and 64–112 bytes RAM for discovery, lookup and bounded results. Measure smaller
alternatives before choosing a layout. Existing utility spare space is limited;
do not treat erased flash or unnamed RAM as available without checking ownership.

## FTDI and ACIA discovery

Explore cooperative discovery of both the FTDI parallel interface and ACIA.
Neither poll may block the other. Represent support, initialization, observed
readiness/input/errors, selected input owner and output routing independently.
ACIA initialization does not establish terminal presence. Discovery and session
selection are separate; do not interleave two input streams into one command.

Initial policy to evaluate: bounded polling of both, first deliberate input
selects a session, explicit switch/reset changes ownership, optional mirrored
output. Preserve FTDI recovery access and test headless, simultaneous-input,
serial-error and cancellation behavior before claiming ACIA hardware support.

## Dispatch and compatibility

Consider a shared command registry for names, aliases, help and action IDs.
Retain compact single-character dispatch where it is smaller. Evaluate software
FNV-1a only for longer-name candidate lookup; folded 16-bit hashes or small bucket
indexes are options, not a chosen implementation. Exact token and boundary
comparison remains required before dispatch, including for unknown inputs that
collide. Reject registry duplicates and diagnose collisions at build time.
Keep command action IDs distinct from stable public service IDs.

Do not weaken existing image/migration integrity checks by folding their hashes.
Do not depend on ATECC or I2C for normal command dispatch. Crypto identification
work remains separate; no SHA engine or provisioning work is in this scope.

Retain the ROM compatibility table, especially current RESET/HOLD paths, unless
a measured alternative justifies its small saving and callers are audited.
Prefer a stable public gateway over direct calls to private recovery validators.

## Additional ABI direction recorded 2026-10-16

Record these as design goals for 2.1; they do not expand beta32's stable-release
scope or authorize flashing. Discussion of these operations remains separate
from the already implemented offline discovery foundation.

- Public operations for independent, opaque machine-code images: expose
  deliberate service contracts, not every private helper. Explore build-time
  service inclusion, runtime operation permissions and permitted address ranges.
  Discovery should report permitted operations; each operation must also enforce
  its policy. These software checks are cooperative safeguards, not a sandbox
  against unrestricted machine code on the current CPUs. ATECC/signature-based
  authentication remains deferred and would not provide memory isolation.
- Byte and bounded block access, including convenient 16/32-byte transfers;
  caller-selected lengths rather than mandatory block-sized operations. If
  16/32 refers to bit widths, little-endian helpers are possible but not atomic
  on the current CPUs. Flash erase remains physically 4096-byte sectors;
  programming and erase/rewrite UPDATE must be distinct, explicit operations,
  with authorized ranges, preservation, wear accounting and verification.
- Initially a small named-object store built on saved-program storage, not a
  general filesystem. Consider list/stat, open/close, read/seek, create/write,
  delete and verified commit. Use handles, define partial-write/power-loss
  behavior, and keep internal directory layouts private. Rename and in-place
  update depend on a defined commit/recovery strategy.
- Add a storage GEOMETRY query. Describe capacity/address bounds, minimum read
  and program units, hardware page boundary/wrap behavior, erase unit, preferred
  transfer and maximum request size, allocation unit, and commit/publication
  rules separately. Include persistence/backup, ownership and write-policy
  flags; distinguish unknown, unsupported and not applicable. Transfer size,
  allocation size and commit size must not be aliases. A commit unit describes
  the service's verified publication protocol, not an unsupported guarantee
  of atomic multi-byte hardware writes. Ordinary byte-range requests remain
  valid where supported; drivers split them at hardware boundaries and expose
  partial completion/failure. Do not hardcode all devices to a 32-byte page.
  Current examples: MCP79411 EEPROM writes split at eight-byte pages; its
  64-byte SRAM is byte/sequential; 23LCV1024 has 32-byte page mode but the
  current driver uses sequential transfers capped at 64 payload bytes; managed
  allocation uses 256-byte pages; SST erase is 4096 bytes. These sizes do not
  grant access to RTC registers, reserved history or protected identity bytes.
- CRC and/or FNV-1a for the named-object store are options to discuss, not an
  algorithm selection. Distinguish payload/metadata corruption detection from
  name lookup/indexing. Hash-based lookup still compares exact names; folded
  indexes do not establish object identity. Neither CRC nor FNV authenticates an
  image. Do not silently change existing on-storage formats or checksums.
- Interrupt service operations to query/install/restore handlers; distinguish
  IRQ, NMI and BRK, preserve register/frame/acknowledgement contracts and pointer
  publication safety. Queue work for foreground services; do not make storage,
  console or bus services IRQ-safe merely by listing them. Handlers needed while
  flash is busy must execute from RAM.
- A separately enabled debug service: controlled memory inspection/modification,
  register snapshots, breakpoints, continue and possibly stepping. Avoid
  side-effecting I/O reads, route flash changes through guarded services, and
  permit optional symbols for opaque images. Debug grants broad control and
  requires explicit owner enablement.

The hourly reminder requested by the owner concerns resuming beta32 stable 2.0
release preparation, not accepting the object-store/hash design. Hold release
work while the owner discusses this idea. Keep the soak stopped and do not flash.

## Starting evidence and preservation

The current hardware checkpoint has 2512 and 2609 on matching beta32 B, beta28 A,
recovery/services, native utilities and saved CLOCK 1.9 code. Each board retains
its own data, identity, settings and wear history; bank 0 images are not cloned.
The owner stopped the 2512 soak before implementation; its failed serial/RAM
restoration attempt was recovered after USB reconnection and the RAM backup
verified. Keep it stopped. New builds and tests use separate alpha
outputs; never rebuild a sealed beta32 package in place. No flash action has
been requested for this alpha.

The branch begins at the current Git HEAD, with existing tracked and untracked
working changes preserved. Creating the branch does not commit those changes
or make the ignored hardware packages reproducible from HEAD alone. Do not
silently include unrelated drift/crypto work in an ABI commit.

The earlier [command processor draft](STR8N_V2_1_COMMAND_PROCESSOR_DESIGN.md) is
background. Its beta23 baseline, RAM-loaded processor design and exclusion of
batching predate beta32 and require reconciliation with the current mostly-flash
utilities and BATCH. It is not an implementation requirement for this alpha.
