# Quick start

Start with a compatible b15 F already installed, or follow
[explicit F-sector provisioning](INSTALLATION.md). Keep owner backups and saved
wear history. The kit does not flash or reconfigure a board automatically.

At the startup chooser, press `S` without Enter. From a matching MON, `J3`
restarts F; press `S` during its countdown. F-only operation needs no MON.

```text
REC> C1
REC> L
SEND BIN
```

Use the terminal's binary file-send operation to send the matching RAM BIN.
Do not send S19 or type a path into the board. After the complete transfer,
wait about three seconds. Initial Ctrl-C cancels while waiting for the first byte.

The tools borrow RAM starting at $0200. Preserve application RAM independently
before loading a tool if it matters. Raw L executes after an idle gap, without
declared length/transfer CRC; an interrupted transfer can execute a partial tool.

Send `STR8N-F-CONFIG-RAM.bin`. At `RAM CONFIG ? B C I W Q>`:

```text
B
W
```

Bare B/C and W inspect only. Completely blank C/D can be initialized with I,
without erasing, recording prior wear as unknown. Do not erase or initialize
existing owner records to clear an error.

After separately installing and verifying an image at B1:$9000:

```text
B 1 9000
C 1
B
Q
```

Both setting commands save immediately. Let the countdown expire to use the
saved default. Press `1` at startup, or enter `1` at REC, for a one-time launch
of an enabled B1 entry. `C S` selects recovery as the saved default.

CONFIG does not install bytes. Use the matching OPAQUE RAM program and
[paced OIP1 procedure](OPAQUE_PROTOCOL.md) with verified sector preimages and
payloads. The packet helper prepares separate header/payload files; it does
not open a port or automatically install an image. Verify every image sector
before enabling the entry. Preserve B0 if it contains a WDC backup.

The optional BASE MON files are separate B3:A/B components. They are not raw L
input and the ordinary opaque writer cannot install them. See installation.
