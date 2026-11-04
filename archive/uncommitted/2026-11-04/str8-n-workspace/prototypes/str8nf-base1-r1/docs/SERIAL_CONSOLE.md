# STR8N-F Serial Console 0.1.0

The Python console is included in the BASE1 candidate kit. It provides an ASCII
terminal and function-key transfers to recovery's RAM loader. Every shortcut
also has a button; laptops may require Fn. Console versioning is independent of
the frozen F version and generation.

Install Python 3.11+ with Tk support, extract the complete candidate ZIP, and run
these commands from its directory:

```text
python -m pip install -r requirements-console.txt
python tools/nf_console.py
```

On Windows, `py` may replace `python`. On Linux, Tk may require your distribution's
`python3-tk` package. Tk and a desktop display are required; pyserial 3.5 is the
only pip dependency. Native serial/key/dialog acceptance passed on
Windows/2512/FT245; other hosts/adapters remain unqualified.

Select the board's port and baud rate (default 115200, 8N1), close any terminal
already using that port, then press F10. You can preselect with
`python tools/nf_console.py --port COM4 --baud 115200`; this does not connect.
The console requests DTR/RTS off and no flow control, sends no reset or probe,
and never connects automatically. USB adapters may still toggle modem lines
when opened; this needs hardware acceptance with the actual adapter.

| Key | Action |
| --- | --- |
| F1 | Show help |
| F2 | Choose a host RAM BIN |
| F3 | Send the chosen BIN at an observed `SEND BIN` |
| F4 | From an observed `REC>`, send L, wait for `SEND BIN`, send chosen BIN |
| F5 | Load the bundled MAP RAM tool through recovery |
| F6 | Load the bundled CONFIG RAM tool through recovery |
| F7 | Load the bundled OPAQUE RAM tool through recovery |
| F8 | Load the bundled DEMO RAM tool through recovery |
| F9 | Start/stop an optional private host transcript |
| F10 | Connect/disconnect |
| F11 | Clear the local display |
| F12 | Ctrl-C; cancel before the first payload byte |

For example, enter recovery on the board and wait for `REC>`. If it was already
waiting before you connected, press Enter once to obtain a fresh prompt. Press
F5, wait for the RAM tool's prompt, then type `M1` and Enter. Use the running
tool's Q command to return to recovery before another preset. The console
requires the observed prompt; it does not guess the board's mode.

To load your own program, use F2 and F4 at `REC>`. Alternatively type L, wait
for `SEND BIN`, then press F3. BINs must run at $0200 and fit $0200-$64FF
(1-25344 bytes). The bytes are sent exactly, without header, newline conversion
or appended terminator, in paced chunks. A leading $03 would cancel the loader
and is refused. Bundled tools are checked against their manifest before L is
sent. Known flash components are refused; arbitrary BIN contents cannot be
automatically proven to be a RAM program. Do not choose a programmer ROM,
opaque flash image, Intel HEX or S-record file for these shortcuts.

The loader runs the image after roughly three seconds of input idle. The
console waits for queued output to drain and an additional 3.5 seconds before
releasing the terminal. Its completion message means host bytes were sent:
raw L supplies no declared length, CRC or independent board readback. Check
the expected program prompt. The console does not restore RAM overwritten by
the loaded program; use the migration workflow when owner-RAM preservation is
required.

Ctrl-C can cancel before the first payload byte. After that it is literal BIN
data: the console blocks cancellation/keyboard injection and finishes the file.
Disconnect/window close is deferred until transfer and idle interval finish.
A serial failure is reported without retry; a partial image may run after idle,
so inspect/reset the board before continuing. Do not unplug an active transfer.

Type ASCII in the terminal; Enter sends CR. Ctrl+V pastes paced ASCII text;
Ctrl+Shift+C copies selected output. F12 and Ctrl+C send Ctrl-C outside an
active payload. The terminal displays board echo, not local echo, and handles
plain text rather than ANSI cursor-control screens.

F9 creates a new JSONL transcript with UTC timestamps, exact RX/TX bytes in
hex, and transfer/status events. It never overwrites a log. These files can
contain private board data; they are host files, separate from both board
journals. Logging is off until requested.

Function keys only connect, send terminal input or load RAM tools. They do not
erase/program flash, save boot settings or run migration automatically.
CONFIG and OPAQUE can write when you explicitly issue their commands. The
verbose WDC migrator remains a separate CLI. Migration is not a function-key
action. The candidate includes it and the programmer-F and SNBT-upgrade CLIs;
disconnect the terminal before using their port. Leave board 2205 alone.

Release acceptance must exercise physical keys/buttons, Ctrl-C before payload,
normal BIN loading, disconnect deferral, and actual adapter timing on an
authorized board. The 2512 checkpoint on October 28, 2026 exercised the released console over
real COM4 serial with the existing b15 F and matching prebuilt b15 RAM tools.
All F1-F12 bindings were exercised using Tk-generated key events; native
file/help dialogs used deterministic test substitutes. Ctrl-C at SEND BIN,
F3/F4 normal loading, demo calculation/input and independent code readback
passed. F5 loaded the matched b15 MAINT tool under the MAP preset filename;
F6-F8 loaded matching CONFIG, OPAQUE and DEMO. No settings or flash writes
were issued. All four flash banks matched, owner RAM $0200-$66FF and ZP
$00-$DF matched after restoration, and MON B/COM4 were returned/released.
The harness was corrected after mistakenly waiting twice for SEND BIN on
manual F3; the demo had already loaded and run normally. Raw captures and
backups remain private. Native key presses/dialogs and BASE1 acceptance were
pending at that earlier checkpoint; the later case below closed them on 2512.

The later [2512 BASE1 acceptance](2512_BASE1_ACCEPTANCE.md) exercised real native
F1-F12 keys/dialogs with matching BASE1 tools and a real-port disconnect request
after the first payload chunk. All flash matched the approved upgrade postimage
and original owner RAM/ZP were restored/read back. This closes the stated
65C02/COM4 case, not other platforms, every button alias or destructive writes.
Those earlier kit ZIPs remain historical snapshots. The 0.3.0-rc1 candidate
includes this later evidence and the unchanged Python console. Migration and
operator acceptance from that exact extracted ZIP remain pending; see
[the release workflow](RELEASE_WORKFLOW.md).
