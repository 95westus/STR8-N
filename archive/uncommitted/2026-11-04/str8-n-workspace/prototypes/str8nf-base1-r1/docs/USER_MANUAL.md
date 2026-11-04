# STR8N-F 0.3.0 user manual

> Give me 4KB, I can give you 4 boards.

With ~32KB RAM shared by four selectable bank environments.

STR8N-F supplies the boot/recovery foundation. Your opaque image supplies
the application, language, monitor or operating environment. The optional
monitor name **Mona** is planned; no Mona program is included in this release.

## 1. What to download

Use the [0.3.0 release](https://github.com/95westus/STR8N-F/releases/tag/v0.3.0).

| Download | Purpose |
| --- | --- |
| `F.bin` | Exactly 4096 bytes of frozen F, for a flash programmer |
| `STR8N-F-BASE1-0.3.0.zip` | Complete operator kit: terminal, WDC migration hosts/RAM programs, CONFIG, OPAQUE, MAP, READBACK and DEMO |
| `STR8N-F-BASE1-0.3.0-source.zip` | Source, image example and build recipes; no assembler needed to use the operator kit |
| `STR8N-F-0.3.0-MANUAL.md` | This manual as a standalone downloadable file |
| `SHA256SUMS.txt` | Original ZIPs and canonical BIN hashes |
| `START_HERE_SHA256SUMS.txt` | Hashes for the added `F.bin` alias and this downloadable manual |

`F.bin` and `STR8N-F-BOOT-4096.bin` have identical bytes. F identifies itself as:

```text
STR8N-F 0.3.0 g00000001
BASE1 / PR05
```

Both BIN names have SHA-256:

```text
8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1
```

Extract the complete operator ZIP and run commands from its top directory.
The manual and `F.bin` are release addenda; the original ZIPs stay unchanged.

## 2. Host setup and terminal

Install Python 3.11 or later with Tk, then:

```text
python -m pip install -r requirements-console.txt
python tools/verify_release_kit.py .
python tools/nf_console.py
```

On Windows `py` may replace `python`. Select your board's actual port;
115200, 8N1 is the default. Only one program can own the port at a time.

| Key | Action |
| --- | --- |
| F1 | Help |
| F2 | Choose a RAM BIN |
| F3 | Send the chosen RAM BIN at an observed `SEND BIN` |
| F4 | At observed `REC>`, issue L and load the chosen RAM BIN |
| F5 | Load MAP |
| F6 | Load CONFIG |
| F7 | Load OPAQUE |
| F8 | Load DEMO |
| F9 | Start/stop a private host transcript |
| F10 | Connect/disconnect |
| F11 | Clear the local display |
| F12 / Ctrl-C | Cancel while waiting for the first BIN byte |

Each shortcut has a button. Connect with F10. If recovery was already waiting
before connection, press Enter to obtain a fresh `REC>` prompt.
The presets require an observed recovery prompt. They do not start migration.

Raw L loads RAM at $0200, accepts $0200-$64FF and starts the received image
after about three seconds of input idle. It has no declared length or transfer
CRC. Initial Ctrl-C cancels; after payload starts, every byte is data.
Do not select `F.bin`, an opaque flash image or an S-record as a terminal RAM BIN.
Loading a RAM tool overwrites borrowed application RAM; save original RAM
before the first helper when it must be preserved.

## 3. Choose an installation route

| Current board state | Route |
| --- | --- |
| Working WDCMONv2 debugger, no compatible N-F journal | WDC RAM migration below |
| External flash programmer available | Program only F, then provision C/D |
| Known b15 F with clean SNBT journal | Separate history-preserving upgrade; do not use factory provisioning |
| Matching BASE1 F and valid journal already present | Keep them; proceed to opaque-image installation |

Before installation, save agreeing independent full-bank captures and original
owner RAM/ZP. Keep owner firmware and per-board plans privately. Available-looking
or erased sectors may still be reserved by their owner. The factory tool refuses
recognized damaged/conflicting history; do not erase it to bypass that refusal.

### WDC-loadable RAM migration

The kit supplies `migrator/payload/archive.bin`, a read-only WDC-loadable RAM
archiver, and `migrator/payload/template.bin`, the migration-engine template.
The supplied Python host binds that template to fresh board captures, renders
the actual per-board RAM migration program, uploads it through the WDC debugger,
and independently reads the upload back before execution. No assembler is needed.
The unrendered engine template has no valid board plan and refuses flash writes.

The supported WDC entries are $2000 for 65C02 and $2010 for the 65C816 shim.
Use the host to select them and preserve the WDC debugger's RAM/stack contract.
These are WDC debugger uploads, not F-key recovery BIN loads.

Close/disconnect the terminal. On Windows PowerShell, replace `COMx` with the
assigned port and select `65c02` or `65c816`. Use three new private directories:

```powershell
$nfArgs = @(
  'migrate', '--port', 'COMx', '--cpu', '65c02',
  '--archiver', 'migrator/payload/archive.bin',
  '--archiver-manifest', 'migrator/payload/archive-manifest.json',
  '--engine-template', 'migrator/payload/template.bin',
  '--f-image', 'firmware/payload/STR8N-F-BOOT-4096.bin',
  '--readback', 'firmware/payload/STR8N-F-READBACK-RAM.bin',
  '--readback-manifest', 'firmware/minimal-manifest.json',
  '--provision-cd', '--capture-out', 'owner-private/capture-01',
  '--plan-out', 'owner-private/plan-01', '--out', 'owner-private/run-01',
  '--allow-unqualified'
)
python migration-host/nf_migrate_live.py @nfArgs
```

**Running this combined command authorizes the admitted flash transaction.**
After checks, the host sends the engine's Y confirmation itself; it does not
pause for an additional interactive approval. `--allow-unqualified` explicitly
accepts the qualification limits described in section 9. Review the route and
target before invoking it. Separate preparation/inspection is available in the
[migration guide](https://github.com/95westus/STR8N-F/blob/v0.3.0/migration-host/README.md).

Follow its physical RESET requests promptly; the reset windows are bounded.
Keep power connected. The verbose host captures original RAM/ZP before helpers,
archives every flash bank twice, checks the source/CPU/chip and sealed plan,
then programs F, D and C as required. It reports receive, erase, program,
commit and verification separately. It does not copy WDC into B0 automatically.

After the final requested physical RESET it verifies BASE1 recovery, reads all
four final banks independently, restores original owner RAM/ZP, reads them back
and finishes at `REC>`. Keep captures, plan, logs and receipts. A complete
restoration/readback result is required before calling preservation complete.
A timeout or failure stops without automatic flash retry; retain the evidence
and inspect the state before deciding how to recover.

### Flash-programmer installation

Program `F.bin` only at **B3:$F000-$FFFF**. With the standard linear 128 KiB
bank ordering this is file offset **$1F000**. Confirm the programmer's actual
mapping and erase behavior. F.bin is not a whole-chip image and does not
contain C/D journals or owner application images. Verify the programmed bytes.

At first RESET, choose S/recovery. For completely blank C/D, matching CONFIG's
`I` command can initialize the journal without erasing. Inspect B and W first.
For occupied non-SNBT C/D, use the declared live provisioner with original escrow;
see the [C/D provisioning guide](https://github.com/95westus/STR8N-F/blob/v0.3.0/docs/LIVE_CD_PROVISIONING.md).
Do not initialize or replace existing compatible history. Supported b15/SNBT
upgrades have a separate [upgrade guide](https://github.com/95westus/STR8N-F/blob/v0.3.0/docs/JOURNAL_F_UPGRADE.md).

## 4. Recovery and a first inspection

At RESET, press **S without Enter** during the chooser to reach recovery.
F-only operation does not require a monitor. At `REC>`:

```text
REC> C1
REC> ?
```

C1 selects USB for the current session. F5 loads MAP; `M1` displays the bank
map. Q restarts through F; press S if the saved default is an application.
F6 loads CONFIG at `REC>`. Bare `B`, `C`
and `W` inspect saved boot settings and erase-attempt counts.

Counts are conservative tracked erase attempts, not certified lifetime wear.
Unknown prior history stays unknown even on an apparently unused chip. External
programmer erases cannot be reconstructed automatically from F.bin.

## 5. Where opaque images go

An opaque image supplies its own code/data, CPU/mode, devices and interface.
F selects its bank and jumps to the configured address. It does not relocate
the image, interpret its format or supply its application dependencies.

| Flash sectors | Use |
| --- | --- |
| B0/B1/B2:$8000-$FFFF | Owner opaque images |
| B3:$8000/$9000/$A000/$B000/$E000 | Owner opaque images; compatible A/B monitors are optional occupants |
| B3:$C000/$D000 | Reserved boot/wear journals |
| B3:$F000 | Reserved frozen bootstrap/recovery |

Each OPAQUE installation unit is exactly **4096 bytes**, linked for its intended
CPU address and bank. Install every sector of a larger image before enabling it.
A bank can contain multiple programs, but CONFIG saves only one entry per bank;
an image-owned launcher can select additional applications.

## 6. Install an image: B1:$9000 example

This example assumes you have assigned B1:$9000 to your image and supplied
`MY-B1-9000-4096.bin`, a complete sector image linked for that location.
Choose the port and target from your own inventory; `COMx` is a placeholder.

1. At `REC>`, press F6 to load CONFIG. Enter `C S`, then `Q`. C S saves
   recovery as the default immediately, so a reset during replacement will
   not automatically launch the image being replaced.
2. Back at `REC>`, press F7 to load OPAQUE. Observe its exact prompt:

```text
OPAQUE BASE1 / PR05 I Q>
```

3. Press F10 to disconnect the terminal. In the extracted kit directory run:

```text
python tools/nf_opaque.py replace --port COMx --bank 1 --sector 9000 --image MY-B1-9000-4096.bin --request-prompt --out owner-backups/b1-9000-install-01
```

Use a fresh output directory for each run. `--request-prompt` is appropriate
only after the matching OPAQUE program has been loaded and observed. The host
requests a fresh prompt, reads the current sector, durably saves `before.bin`,
then performs the preimage-checked CRC-protected transfer. The RAM writer
reserves its erase attempt in C/D before erasing. The host independently reads
the sector again and compares every byte. Identical contents cause no erase.

Keep `before.bin`, `after.bin`, `receipt.json` and the adjacent private serial
log. Require `replace-verified` or `identical-no-write` before booting. Installing
the bytes does not enable the bank or change its boot entry/default. Borrowed
RAM is not restored by this helper.

4. Reconnect the terminal with F10. At the still-running OPAQUE program enter
   `Q`. With saved default S, return through startup to recovery.

To read a sector without replacing it, load/observe OPAQUE and disconnect the
terminal as above, then run:

```text
python tools/nf_opaque.py read --port COMx --bank 1 --sector 9000 --request-prompt --out owner-backups/b1-9000-read-01
```

Do not send the opaque sector itself with F2/F4: those load executable RAM
programs at $0200. OPAQUE is the RAM tool that installs your flash sector.

## 7. Enable the bank and make it the default

After the complete image is verified, load CONFIG with F6 at `REC>`:

```text
B
B 1 9000
C 1
B
Q
```

`B 1 9000` enables B1 and saves its $9000 entry immediately. `C 1` saves B1 as
the default immediately. Both append journal settings; Q restarts through F.
Let the countdown expire to boot the saved default. At subsequent power-on or
RESET the journal supplies the same settings. For another bank, substitute its
number and the image's actual supported entry.

Allowed entries are $8000-$E000 in $1000 steps. B3:$C000/$D000 are excluded,
and $F000 is never an opaque entry. CONFIG does not inspect or validate the
image. There is no bank-disable command in this release.

For a one-time launch, press the enabled bank number at startup or enter it
at `REC>`. To stop automatic application boot, RESET, press S, load CONFIG,
enter `C S`, then `Q`. Saved settings and images remain separate operations.

## 8. Application return and optional monitors

An application's Q command is defined by that application. Restarting through
F uses the saved default and can launch that application again. A deliberate
return to recovery must account for the default or allow S at startup.

The included source example `examples/base1-b0-9000.asm` demonstrates public
RAM ABI calls and restart behavior. It is source, not a bundled opaque ROM BIN.
Mona remains a future optional monitor. Existing g0034/full-system monitors
need ABI/provider review before use under BASE1. A/B chooser slots require
the compatible monitor header and CRC; an arbitrary opaque image uses its
bank number and configured entry.

## 9. Release evidence and limits

Reviewed 2512/65C02/FT245/Windows cases passed reset/recovery, native terminal
keys/dialogs, RAM transfer, CONFIG/opaque boot, WDC migration, programmer-F
provisioning and named chip-idle C/D recovery cases. The extracted rc1
existing-SNBT upgrade and terminal core checks passed on 2609/65C816 emulation.
The final package's runtime bytes match rc1; it has no additional live trial.
WDC and programmer-F provisioning from an extraction remain untested package
routes. This manual adds instructions, not new hardware qualification.

Normal recovery assumes F stays golden. ACIA physical operation, other
platforms/layouts, native application-mode calls, interrupted F installation
and electrical interruption during active programming remain unqualified.
See [release scope](https://github.com/95westus/STR8N-F/blob/v0.3.0/docs/RELEASE_STATUS.md)
and [rc1 findings](https://github.com/95westus/STR8N-F/blob/v0.3.0/docs/RC1_KNOWN_ISSUES.md).
