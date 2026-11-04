# STR8-N ASM 0.4

Standalone ROM-resident W65C02 assembler, brought forward from the ASM 0.3 branch
checkpoint 5313633. This is not ASM-F2 or HIMON. Beta33 ports it to the sealed
beta32 baseline and moves all source/symbol/state buffers above one contiguous
$0200-$32FF user-code window. Default origin and physical output are both $0200.

See the [user guide](STR8N_ASM_USER_GUIDE.md), [worked examples](../examples/beta33/README.md)
and [beta33 candidate record](STR8N_V2_BETA33_CANDIDATE_2026-10-16.md).

ASM 0.4 is 6,244 flash bytes at B1:E000-F863, entry E010. The same two sectors
also contain exception vectors at the end of B1:F. Its named-app descriptor
claims active application RAM $0200-$64FF and ZP $00-$3F. No permanent monitor
RAM reservation is added. It targets W65C02 instructions; 816 hosts use the
supported emulation profile. Native 816 assembly is outside this version.

The engine has two passes, 212 instruction/addressing encodings, 256 symbols,
scoped locals, expressions, a numbered editor, paste, DUMP and S19 export.
The full instruction matrix is compared against the independent WDC tools.

| Range | Active use |
|---|---|
| $0200-$32FF | User code/output, 12,544 bytes |
| $3300-$4EFF | Packed source, 7,168 bytes |
| $4F00-$62FF | 256 symbol records of 20 bytes |
| $6300-$64FF | State and input buffers, 512 bytes |
| $6500-$66FF | Existing protected EDU services, outside ASM ownership |

ASM emits into the code window; it does not write directly to arbitrary ORG
addresses. ORG $0200 needs no relocation. Other logical origins can be exported
as S19 and loaded after QUIT. Code loaded after QUIT can overwrite former ASM
buffers within the normal application range.

The private engine interface uses packed source records: line number (word),
text length, pass-1 mode, then text. SRC_END at $6300 marks the end. RESULT_LEN,
RESULT_ORIGIN and RESULT_VALID are at $6302/$6304/$6306. ASM_ASSEMBLE returns
C=0 on success; C=1 identifies ERROR and LINENO. These are private assembler
internals, not new public monitor ABIs.

Build from a fresh output directory with the sealed beta32 parent present:

```text
make beta33-candidate
make beta33-check
```

Output is BUILD/v2-beta33-candidate. The builder refuses to overwrite an existing
candidate. Physical board qualification is separate from model and rebuild proof.
Historical October 5 ASM 0.3 evidence does not qualify this new RAM layout.
