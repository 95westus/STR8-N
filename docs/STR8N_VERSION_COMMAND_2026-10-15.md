# VERSION command

The owner requested VERSION and flashing 2609. This command provides firmware
identity after a terminal connects late and misses the startup banner.

VERSION repeats the actual running monitor's banner, CPU and ABI, the saved
board name, and the running A/B slot and generation. It then validates and
lists both slots, marking the default using the bootstrap's real preference
and fallback rules. Manually starting A does not make it the default.

The banner is printed through the running slot's validated header callback;
it is not a hard-coded beta25 string. Thus the existing 2609 mixed pair shows
2.0b24/generation 00000023 for A and 2.0b25/generation 00000025 for B. Generation
numbers retain the existing hexadecimal display convention.

`tools/build_v2_version.py` builds the isolated `BUILD/v2-version` package.
The helper is 636 bytes of code/data, sealed into a 2,048-byte asset at
B2:E800-EFFF, within the existing reserved B2:E display sector. The shared
EF00 loader grows from 250 to 253 bytes. Incremental CRC validation during
the read/copy loop and shared source/destination low-byte advancement make
room for exact VERSION recognition. Normal TIME, boot/status and storage
dispatch remain available; a bad asset CRC or header is refused before
execution. The loader's failure message is shortened to `Status error`.

No new flash sector is allocated. The update rewrites three 4-KiB sectors:
B3:C (wear journal), B2:E (helper, preserving the local formatter and gap),
then B3:E (loader). Recovery F and both monitor slots remain byte-identical.
CLOCK 1.7, saved programs, RTC administration, identity/timezone records and
configuration values are retained. VERSION borrows $6E00-$75FF monitor
staging and does not modify application or service RAM or access RTC/SPI.

`tools/test_v2_version.py` exercises the real mixed slots from 2609's fresh
backup: default B, manual A with default B, alternate data-view bank, EDU OFF,
invalid preferred-slot fallback, exact command matching, corrupted asset
CRC/header refusal and shared TIME behavior. It checks flash/device snapshots,
application/service RAM, running slot and bank preservation. Existing boot
dialog and CLOCK 1.7 suites run against the candidate as regressions.

`tools/deploy_v2_version.py` targets only USB identity A10MPQXCA (2609), using
two independently compared full flash reads and an exact backup-bound
installer rehearsal. Evidence is stored at
`output/qualification/version-2609-2026-10-15/`.
Installation and post-reset verification completed on 2609 only. All four
flash banks (131,072 bytes) matched the planned image exactly. VERSION was
physically verified with B running (2.0b25, generation 00000025), then manual
A (2.0b24, generation 00000023) while B remained marked default. A final J3
startup restored default B. TIME and R CLOCK 1.7 also passed physical checks.
The tool returned to B3 and closed/released COM8.

See `upgrade/version-B.txt`, `upgrade/version-A.txt`,
`upgrade/version-B-restored.txt`, `upgrade/post-reset-report.json` and the
four complete `upgrade/post-reset-b*.bin` readbacks in the evidence directory.
