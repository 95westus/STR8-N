# Future v2.1: ABI and metadata organization

Owner direction recorded October 17, 2026 (CDT). **v2.0rc1 is the current
release and installed firmware version on 2604 and 2609.** v2.1 is future
development focused on organizing public ABIs and metadata. This page records
requirements; it assigns no stable service IDs, addresses or register contracts.

The separate `codex/v2.1-alpha` branch and saved working changes remain intact.
Its existing offline discovery foundation is development evidence, not a
released ABI or authorization to install a new firmware image.

## Common contract and metadata work

- Provide versioned discovery of public service groups and operations, with
  explicit calling conventions, ownership, buffer bounds and error returns.
- Separate compiled support, current availability and resource ownership.
  Discovery alone must not initialize devices, change outputs or start timers.
- Describe detected CPU, execution mode and callable ABI profiles separately.
  Target the shared 65C02 / 65C816 emulation-mode runtime; native 816 services
  remain deferred. Retain the accepted startup CPU-detector exception.
- Keep command names and storage formats distinct from callable interfaces.
  Preserve or explicitly map rc1 public contracts; audit callers before moving
  an entry, assigning an ID or changing application RAM ownership.
- Document hardware instances and capabilities in metadata rather than requiring
  applications to know private implementation addresses.

## Eight-LED ABI

Plan a public service covering all eight LEDs. Define logical LED bit numbering
and mask semantics independently of electrical polarity and port placement.
Specify query/read, whole-display and masked-update behavior, with explicit
ownership or arbitration for applications and monitor/console status reporting.

The design must explain what can be read back, how ownership is released or
restored on exit, and how unrelated port bits and hardware functions remain
intact. Pattern scheduling or animation can be a later operation; it must not
be implied by the basic LED contract or silently consume a VIA timer.

## Timer ABIs for both VIA chips

Cover T1 and T2 on each of the two VIA chips, with explicit chip/timer identity.
Inventory current users and reserved resources before advertising availability.

| Area | Required design coverage |
|---|---|
| Discovery | Chip/timer identity, supported modes, clock source/tick units, width, availability and current owner |
| Ownership | Claim/release, busy/reserved refusal, cleanup and restoration policy |
| Control | Validated configuration, start/reload/stop and defined one-shot or repeating behavior where supported |
| Observation | Counter/status reads with documented consistency and hardware read side effects |
| Interrupts | Polling versus interrupt operation, registration/routing, explicit acknowledgment and preservation of other pending sources |
| Shared hardware | Preserve unrelated VIA port, handshake, shift-register and timer functions; disclose pin conflicts or unsupported modes |

Resolve timer clock/counter differences and supported modes per instance rather
than promising one universal timing rate. Define expiration, wraparound,
interrupt latency assumptions and unsupported-mode errors before publishing
examples. A query must not arm, reload, stop or acknowledge a timer.

## Acceptance work before implementation is released

Audit actual resource ownership and memory costs; specify the contracts and
metadata; then verify both CPU profiles, LED mask isolation, timer ownership,
counter boundaries, interrupt coexistence and error paths. Hardware testing
will require a separate authorized session. No such tests or implementations
are claimed by this planning checkpoint.

Both soaks and RTC sampling remain stopped. 2205/2512 remain off; clocks and
trims remain unchanged. RTC qualification, native 816 applications/tests, ACIA
and crypto remain deferred. No release assets or board firmware change here.
