# Next gate: scoped acceptance and accumulated measurements

2609 completed original A40/B35 payload restoration and two owner-controlled
power interruptions with captured flash, EEPROM, retained SRAM and recovery
evidence. See the [physical evidence index](evidence/physical/index.json).

The first interruption occurred after the first verified journal transfer,
while waiting for the next transfer. Original A40 booted as fallback; recovery
installed bf1 B. The second occurred after A48 payload/header commit, before
final journal activation. bf1 B48 booted as fallback; two journal-sector
transfers recovered activation of A48 without erasing its payload again.
Both cases verified emulation runtime, utility/CLOCK BATCH, exact modeled flash,
retained storage, conservative wear history and pre-interruption application
RAM restoration. Normal boot created the expected CRC-valid PF records, with
no manual ACK/CLEAR. User confirmations bound the power transitions; exact
physical switch instants are unknown.

These results cover these two verified transfer boundaries on 2609. They do
not qualify power loss during an erase/program pulse, arbitrary byte timing,
or 2604 electrical behavior. Native 816 applications/testing, ACIA and crypto
remain deferred. The unchanged startup detector exception remains accepted.

The next decision is whether this bounded pilot coverage is sufficient for a
scoped candidate acceptance, or whether additional explicitly planned electrical
tests are required. No additional power interruption is requested by this kit.
Continue the 2604 preserving soak and three-board RTC collection. The owner
must choose duration and acceptance thresholds; none have been invented.

2609 stays powered on with bf1 A/B and RTC-only collection. 2512 remains RTC-only,
2205 stays off, and clocks/trims and the original baseline stay unchanged.
Generic installation permission, release qualification and publication remain
false until a separate scoped acceptance and release decision.
