# F identity and stability contract

Product STR8N-F; F version 0.3.0; F generation 00000001; profile BASE1;
private compatibility PR05; public ABI major 2; descriptor format 1.

F03C-F03F contains ASCII FI and a little-endian descriptor pointer. Consumers
keep B3 visible, validate the locator, bound the pointer to F's payload, then
validate format, length and CRC. The record currently starts at FDFD; callers
must discover it through the locator rather than embed that address.

| Offset | Bytes | Meaning |
| --- | ---: | --- |
| 00 | 4 | NFI1 magic |
| 04 | 1 | Length 64 |
| 05 | 1 | Public ABI major 2 |
| 06 | 1 | Descriptor format 1 |
| 07 | 1 | Reserved 0 |
| 08 | 4 | F generation, little endian |
| 0C | 8 | Product, NUL-padded |
| 14 | 8 | F version, NUL-padded |
| 1C | 8 | Profile, NUL-padded |
| 24 | 4 | Private contract PR05 |
| 28 | 2 | RAM ABI signature address, 7E60 |
| 2A | 2 | Reset entry, F004 |
| 2C | 2 | F base, F000 |
| 2E | 2 | Image length, 1000 |
| 30 | 14 | Reserved 0 |
| 3E | 2 | CRC16/CCITT-FALSE over 00-3D, little endian |

The startup hook is a same-size JMP substitution after the original input drain
and boot-record selection. The helper, text and record append after the old
code/worker images. The old body changes only in that JMP operand and the
previously unused four locator bytes. The `Recovery L ` face stays compatible.

F generation identifies F bytes, not the OS, default or journal append. The
existing SNBT field for optional monitor generation stays 8000000F; it must not
be replaced with F generation 00000001. OS/personality images print their own
identity, board/EDU/SRAM/RTC/battery status and login/session information after
handoff. WDC catalogue matches have no N/F generation.

F_FREEZE.json binds the exact BIN and source inputs. Later RAM catalogue/tool
changes reuse it. A boot defect requires a separately reviewed F generation and
candidate; deleting the lock to rebuild this identity is not the maintenance
procedure. Hardware evidence can be added without changing these frozen bytes.

Current private-ABI utilities still require matching F bindings and exact-image
guards where present. The locator does not make every private service public.
