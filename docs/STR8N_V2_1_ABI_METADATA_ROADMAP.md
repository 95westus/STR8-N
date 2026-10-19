# Future v2.1: ABI and metadata organization

Owner direction recorded October 17, 2026 (CDT). **v2.0rc1 is the current
release and installed firmware version on 2604 and 2609.** v2.1 is future
development focused on organizing public ABIs and metadata. This page records
requirements; it assigns no stable service IDs, addresses or register contracts.
IRQ/NMI sequencing and acceptance requirements added October 18, 2026 (CDT).

The separate `codex/v2.1-alpha` branch and saved working changes remain intact.
Its existing offline discovery foundation is development evidence, not a
released ABI or authorization to install a new firmware image.

## Common contract and metadata work

- Locate the ABI base at runtime through a defined bootstrap discovery
  mechanism. Validate its signature, format/version, length and address bounds
  before using the directory; return an explicit unavailable/incompatible
  result when discovery fails. Programs obtain service entry points from that
  validated base instead of embedding private implementation addresses.
  The bootstrap locator itself still needs a documented contract; its exact
  anchor or bounded search scheme remains a design decision.
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

## Interrupt ABI sequence: IRQ, then NMI

Establish ABI discovery and resource ownership first, then implement and verify
the IRQ ABI, followed by the NMI ABI. Complete this interrupt foundation before
releasing interrupt-driven VIA timer services. Polling-only timer work and the
LED ABI can proceed independently. Existing interrupt vectors and historical
probes are a starting point, not qualification of the new public contracts.

### Shared handler contracts

- Discover versioned IRQ and NMI capabilities separately, including supported
  sources, registration capacity, reserved owners and current availability.
  Queries must not install handlers, enable sources or acknowledge events.
- Specify registration/removal inputs, validated handler address ranges,
  flags, ownership identity and explicit errors for unsupported, invalid,
  duplicate, busy/reserved and full requests. Refused requests must leave the
  previous registration and device state intact. Define whether chaining is
  supported; registration must not silently replace another owner's handler.
- Require handler code and data to remain resident until removal completes.
  Define publication/removal atomicity, pending and in-flight event handling,
  and when the caller may reclaim memory. Specify source disable/quiesce and
  acknowledgment ordering separately from registration.
- Document entry registers, source/context information, hardware stack frame,
  register/flag preservation, decimal-mode handling, scratch ownership, stack
  budget and bank visibility/restoration on both 65C02 and 65C816 E=1. Define
  the wrapper's responsibilities and whether callbacks return with RTS or RTI;
  preserve the interrupted context through the final RTI. Native 816 remains
  deferred.
- Keep hardware interrupts distinct from DBG1 BRK services and their saved
  context. Specify nesting and IRQ/NMI preemption rules, including NMI during
  IRQ dispatch. Define bounded execution and latency assumptions. Initially
  restrict handlers to documented interrupt-safe operations and event recording
  for foreground processing; existing non-reentrant monitor calls, console,
  BRK services, loaders and flash operations are not implicitly interrupt-safe.
  Any event queue/counter needs an overflow and foreground synchronization rule.
- Define cleanup at HOLD, X, reset and application handoff, including ownership
  release, default routing and safe device state. Resolve debugger stop/resume
  and flash/bank-transition behavior explicitly; this work does not imply
  debugger interrupt virtualization. Unsupported combinations must have a
  documented refusal or safe-entry policy before applications enable sources.

### First: IRQ ABI

Define source identities and routing for the shared IRQ line, starting with a
claimed VIA timer as the first client. Document pending-source inspection,
dispatch order, whether one or all pending sources are serviced per entry, and
the handler's handled/unhandled result. Separate BRK from hardware IRQ without
altering either interrupted frame.

Assign responsibility for each device acknowledgment and interrupt-enable bit.
Handle simultaneous pending sources without clearing another owner's event or
changing unrelated VIA functions. Specify unclaimed, persistent and spurious
IRQ behavior, including how an interrupt storm is contained and reported.
Define an IRQ-masked publication/removal protocol that restores the caller's
previous interrupt state; registration alone must not execute CLI or arm a
device. State which foreground ABI operations may run with IRQ enabled and
which require masking.

### Second: NMI ABI

Build on the accepted shared/IRQ contracts, with an independent NMI policy.
Define ownership and source identification for the physical NMI input and any
supported device sources; do not promise IRQ-style source arbitration where
the hardware cannot identify the cause. Specify default/unclaimed behavior,
device acknowledgment where applicable, repeated edges and nested NMI behavior.

SEI does not protect NMI registration. Provide a publication/removal protocol
that cannot expose a partially written pointer or reclaimed handler. Define
behavior for NMI during initialization, pointer changes, cleanup, debugger
activity and flash/bank transitions. If dispatch is gated, specify whether an
event is deferred, coalesced or lost and how that is reported; returning with
RTI is not by itself a device acknowledgment. Document hardware edge-latching
limits rather than promising an exact count of all physical NMI edges.

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

Interrupt-driven modes must use the accepted IRQ ownership/routing contract;
timer registration must not install a competing private dispatcher. NMI routing
is advertised only for hardware sources explicitly supported by the NMI ABI.

Resolve timer clock/counter differences and supported modes per instance rather
than promising one universal timing rate. Define expiration, wraparound,
interrupt latency assumptions and unsupported-mode errors before publishing
examples. A query must not arm, reload, stop or acknowledge a timer.

## Acceptance work before implementation is released

Audit actual resource ownership and memory costs; specify the contracts and
metadata; then verify ABI-base discovery and invalid/absent-directory refusals,
both CPU profiles, LED mask isolation, timer ownership,
counter boundaries, interrupt coexistence and error paths. Hardware testing
will require a separate authorized session. No such tests or implementations
are claimed by this planning checkpoint.

### IRQ/NMI acceptance gates

Specify expected outcomes and build repeatable offline checks first, then
qualify supported hardware configurations in the separately authorized session.
Run applicable checks on both 65C02 and 65C816 E=1, across supported flash-bank
states and MON A/B. Record measured stack use, RAM/code costs and latency
against the documented limits. Existing rc1/DBG1 evidence does not satisfy
these v2.1 gates.

1. **Discovery and lifecycle:** reject absent/incompatible metadata, invalid
   pointers/flags, duplicate, exhausted and reserved registrations without
   mutation. Verify side-effect-free queries, ownership enforcement, removal
   with pending/in-flight events, safe memory reclamation, re-registration and
   cleanup at HOLD, X, reset and application handoff.
2. **Context and coexistence:** verify A/X/Y/P, PC, SP, hardware frames and bank
   restoration, including supported stack-boundary cases and decimal-mode
   entry. Check 816 E=1 bank/direct-page requirements and hidden accumulator
   preservation under the defined contract. Exercise BRK/IRQ discrimination
   and DBG1 coexistence, reentrancy refusals, foreground event synchronization
   and overflow handling. Verify debugger/flash restrictions or safe-entry
   behavior without claiming interrupt virtualization.
3. **IRQ gate:** use a claimed VIA timer to prove entry, acknowledgment and
   return; then exercise simultaneous supported sources, other-owner pending
   events, repeated expiration, spurious/unclaimed IRQ and a persistent source.
   Verify dispatch order, storm containment, unrelated VIA state preservation,
   source enable/disable ordering and restoration of the caller's I flag.
   Inject IRQ at registration/removal boundaries to check atomicity.
4. **NMI gate, after IRQ passes:** inject NMI at each pointer-publication and
   removal boundary, during IRQ dispatch, and during initialization/cleanup.
   Verify no torn pointer, stale-handler execution or context corruption.
   Exercise repeated/nested NMI under the chosen policy, default/unclaimed
   routing, gated-event behavior and device acknowledgment where supported.
   Check debugger and flash/bank-transition cases against their stated policy.
   Include an explicitly observed physical NMI test; software injection alone
   does not qualify the board input or hardware edge-latching behavior.
5. **Timer integration gate:** before releasing interrupt-driven timer modes,
   verify claim/start/expire/stop/release for each advertised VIA timer and mode,
   coexistence with other owners, busy/reserved refusals and cleanup with an
   expiration pending. Confirm queries remain side-effect-free and polling-only
   operation does not enable interrupts or replace interrupt registrations;
   any acknowledgment must follow the documented operation contract.

Both soaks and RTC sampling remain stopped. 2205/2512 remain off; clocks and
trims remain unchanged. RTC qualification, native 816 applications/tests, ACIA
and crypto remain deferred. No release assets or board firmware change here.
