# On-board ASM, RAM execution, and Store / Table / Restore

Beta33 uses standalone STR8-N ASM 0.4, brought forward from the earlier branch
assembler. It runs from B1:E-F. While ASM is open, CPU RAM is arranged as:

| Range | Use |
|---|---|
| $0200-$32FF | Contiguous user code/output, 12,544 bytes (12.25 KiB) |
| $3300-$4EFF | Packed ASM source, 7,168 bytes |
| $4F00-$62FF | 256 symbols, 5,120 bytes |
| $6300-$64FF | ASM state, line and token buffers, 512 bytes |

The default logical origin and physical output buffer both start at $0200.
Launching ASM starts a new source session; save wanted RAM contents first.
There is no permanent increase in monitor/service RAM reservations.

At B3>, enter ASM, then PASTE at ASM>. Wait for the paste message, send
hello.asm, and finish with a line containing only a period. Or type:

```text
10 PUTC = $7E6D
20 HOLD = $7E67
30 ORG $0200
40 LDA #'O'
50 JSR PUTC
60 LDA #'K'
70 JSR PUTC
80 LDA #13
90 JSR PUTC
100 LDA #10
110 JSR PUTC
120 JMP HOLD
```

At ASM>:

```text
ASM
DUMP
QUIT
```

ASM reports `OK 23 bytes, origin $0200, buffer $0200`. At B3>:

```text
G 0200
```

It prints OK and returns through public RAM HOLD. PUTC and HOLD are existing
bank-independent public ABI entries. The 816 host uses emulation mode.

Review M1 and T 1 before choosing storage. The candidate reference has free
B1:8-D and ASM in E-F. AUTO finds an erased extent; it does not erase occupied
space. With a unique label, save the generated RAM program:

```text
S 1 AUTO 0200 0216 HELLO0200
T 1
R 1 HELLO0200 L
G 0200
R 1 HELLO0200
```

S stores a 24-byte record header and the 23-byte program. T lists its saved
RAM range $0200-$0216 and name. R with L restores without running; R without
L restores and runs at the recorded start address. No MAINT copy is needed.
The qualification deliberately changes the RAM bytes before Restore and checks
that the original assembled bytes return.

ram-counter.asm increments a variable in the generated RAM program and prints
01, 02, etc. through public HEX/PUTC before returning. Restoring a saved copy
also restores the variable value that was saved.

ORG still controls logical addresses. An origin other than $0200 requires
placing output at that origin before execution; S19 export provides addressed
loader records. The physical output buffer always starts at $0200. After QUIT,
a program loaded by R or L may use the full normal application RAM range through
$64FF with EDU ON ($66FF with EDU OFF), overwriting the former ASM buffers.
This assembler emits at most 12,544 bytes per assembly.

ASM has no BATCH input provider. BATCH ASM;... stops before launch; enter ASM
directly. BATCH APPS;VERSION remains supported. QUIT preserves machine code in
RAM but does not persist source. LIST can be captured as text; S/T/R here stores
the assembled program, not its source editor session.
