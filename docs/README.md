# STR8-N documentation

Start with [F / MON / UTIL / DEV](COMPONENT_GUIDE.md) for current source,
component versions and preserved release downloads. Read
[file and transfer formats](FILE_FORMATS.md) before loading a `.bin`, `.s19`,
`.srec`, `.s29` or memory backup. F remains frozen at 0.3.0 / BASE1 / PR05.

| Area | Guides |
| --- | --- |
| Foundation and boot | [F manual](USER_MANUAL.md), [quick start](QUICK_START.md), [operator guide](OPERATOR_GUIDE.md), [installation](INSTALLATION.md), [F identity](F_IDENTITY.md) |
| MON and on-board utilities | [MON/UTIL manual](NATIVE_UTILITIES_MANUAL.md), [component names](COMPONENT_NAMING.md), [image contract](IMAGE_CONTRACT.md) |
| PC terminal and memory | [Terminal](SERIAL_CONSOLE.md), [optional board profiles](BOARD_PROFILES.md), [MEMORY backup/restore/load/offload](MEMORY_UTILITY.md) |
| DEV | [ASM/DBG manual](DEVELOPER_MANUAL.md), [historical first RAM increment](ASM_DBG_BASE1_RAM.md) |
| Worked examples | [Microchess ASM/RAM/AP02 and OSI BASIC opaque B0](EXAMPLES.md) |
| Recovery and flash transfer | [BASE1 readback/RAM restore](RECOVERY_BASE1.md), [readback overview](READBACK.md), [OPAQUE host](OPAQUE_HOST.md), [OIP1 protocol](OPAQUE_PROTOCOL.md) |
| Source and packaging | [Current build/verification](CONSOLIDATION_SOURCE_REVIEW.md), [build/freeze policy](BUILD.md), [build helpers](BUILD_HELPERS.md), [development policy](DEVELOPMENT.md) |
| Acceptance limits | [Current qualification scope](QUALIFICATION_SCOPE.md), [MEMORY acceptance summary](MEMORY_ACCEPTANCE_SUMMARY.md), [export evidence scope](EXPORT_EVIDENCE_SCOPE.md) |
| Preserved releases/history | [Release index](https://github.com/95westus/STR8-N/blob/main/RELEASE_INDEX.md), [archived Foundation records](https://github.com/95westus/STR8-N/tree/main/docs/archive/str8n-f) |

Release closeouts, dated checkpoints, lab protocols and acceptance records
describe the versions and bytes tested at that time. Their older filenames,
board references and pending gates are historical context. Use the current
component guide and qualification scope for today's named kit. The existence
of a script or historical command does not establish a supported current
installation route; see the build-helper guide.

Published ZIPs/manuals and historical Git tags retain their original content.
Documentation on `main` can be newer than a release's downloadable manual.
