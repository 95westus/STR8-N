# Python serial console 0.1.2

The unified candidate includes the current console separately in `terminal/`.
Its root launcher selects the unchanged Foundation assets with `--kit foundation`.
The published Foundation subkit, including its older console/manifest, is kept
byte-for-byte exact. Launch the current console through `terminal.py`.

From the extracted ZIP root:

```text
python -m pip install -r requirements-console.txt
python terminal.py
python terminal.py --port COM4 --baud 115200
```

The last command preselects a port; it does not connect. Windows users can
open Start-Terminal.cmd. For a source checkout or the standalone Foundation
kit, its corresponding entry remains `python tools/nf_console.py`. Python
3.11+, Tk/desktop display and pyserial 3.5 are required. Linux may need the
system python3-tk package; other host/adapter combinations need qualification.

Choose the correct board/port, close competing terminal sessions and use F10
or its button to connect. Default is 115200, 8N1, no flow control. The program
requests DTR/RTS off, sends no reset/probe and never auto-connects. Adapter
open behavior still depends on the actual hardware.

## Keys and buttons

| Key | Action |
| --- | --- |
| F1 | Help |
| F2 | Choose a raw RAM BIN |
| F3 | Send selected BIN at observed SEND BIN |
| F4 | At observed REC>, send L, wait for SEND BIN and send BIN |
| F5 | Load Foundation MAP inspection tool |
| F6 | Load Foundation CONFIG |
| F7 | Load Foundation OPAQUE |
| F8 | Load Foundation DEMO |
| F9 | Start/stop private host transcript |
| F10 | Connect/disconnect |
| F11 | Clear local display |
| F12 | Send Ctrl-C outside active payload |
| Shift+F2 | Choose RAM S19 |
| Shift+F3 | Send at monitor RAM S19 prompt |

Each action also has a button. A laptop may need Fn. F2 selects
`rec/MAINT.bin` or `rec/FLASH.bin`; F4 loads it from REC>. These full tools
start at $0200. F5's MAP is the smaller inspection tool, not BANK MAINT.
MON Q returns to REC>. Main Q in the full REC tools restarts Foundation,
using the saved default; choose S at its chooser to remain in recovery.

## Transfer and cancellation

Raw BIN loads at $0200, within recovery's $0200–$64FF input range, and starts
after input idle. Use a raw RAM packet, not a full flash image, AP/02 image,
Intel HEX or S19 file. The sender waits for queued output and the idle period;
its completion message establishes host transmission, not board readback.
Raw L has no declared length/checksum. Verify the expected program prompt.
Normal RAM loading borrows/overwrites application RAM and does not restore it.

Ctrl-C cancels SEND BIN before its first payload byte. After that Ctrl-C is
binary data, so the console finishes the file and defers close/disconnect.
A serial failure has no automatic retry; a partial image can run after idle.
Inspect/reset recovery before another transfer after such a failure.

For RAM S19, enter `S19` at MON and wait for the exact prompt:

```text
SEND S19 (S0/S1/S9); Ctrl-C cancels
```

Use Shift+F2/F3. It does not send L, YES, a boot command or a flash command.
RAM records have line checksums and do not autorun; inspect before G. This is
separate from FLASH's dense ascending full-sector S19 protocol.

Enter sends CR. Ctrl+V pastes paced ASCII; Ctrl+Shift+C copies selected output.
Ctrl+C/F12 sends cancellation outside a payload. Display is board echo/plain
text, not an ANSI screen emulator. Logs are private optional host files.

## Board labels and qualification

Auto mode reads the host USB inventory without opening a port. Saved adapter
labels identify the lab's 2205/2512/2604/2609 adapters and CPU models. These
are host labels, not a live electronic CPU/EDU query. Windows can renumber
ports; update a moved adapter's assignment or use Board override/--board.

Earlier Candidate3 Windows/2512 acceptance used physical Shift+F2/F3, F2/F4/F12
and native dialogs for S19/BIN cancellation and normal loading. Earlier
developer candidate2 used the extracted transfer backend for ASM/DBG RAM
acceptance. Candidate4 subsequently passed its exact extracted console/core
on 2512: physical Shift+F2/F3, checked RAM S19 and normal BIN loads, initial
SEND S19/BIN cancellation, MAP/CONFIG inspection, OPAQUE exit without writing,
DEMO, help/display/log/connect actions. Ordinary actions used physical keys
or buttons as recorded in the companion `ACCEPTANCE-2512.json`; native file
dialogs were prefilled by the harness. Owner RAM/ZP/cache/hooks were restored,
and flash/SPI metadata stayed exact. The tested ZIP remains unchanged; its
packaging-time pending text is superseded by that companion acceptance.
