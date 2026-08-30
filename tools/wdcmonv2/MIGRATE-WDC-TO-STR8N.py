#!/usr/bin/env python3
"""Experimental Ubuntu launcher for the STR8-iN/65 factory migration."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_bridge_dir = _script_dir / "TOOLS" if (_script_dir / "TOOLS").is_dir() else _script_dir
if str(_bridge_dir) not in sys.path:
    sys.path.insert(0, str(_bridge_dir))
from start_wdcmonv2_ram import LoaderError, list_ports, read_migration_s19, run_loader, self_test


def select_port(requested: str | None) -> str:
    if requested:
        return requested
    ports = list_ports()
    if not ports:
        raise LoaderError("No serial ports were found. Connect the WDC board and try again.")
    print("SERIAL PORTS")
    for index, device in enumerate(ports, 1):
        print(f"  [{index}] {device}")
    default = ports[0] if len(ports) == 1 else ""
    prompt = f"Enter serial port [{default}]: " if default else "Enter serial port: "
    answer = input(prompt).strip()
    if not answer:
        answer = default
    if answer.isdecimal():
        choice = int(answer)
        if not 1 <= choice <= len(ports):
            raise LoaderError(f"Serial-port choice is out of range: {answer}")
        return ports[choice - 1]
    if answer not in ports and not Path(answer).exists():
        raise LoaderError(f"Serial port is not currently present: {answer}")
    return answer


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimental Ubuntu STR8-iN/65 loader")
    parser.add_argument("--port", help="Linux serial device, for example /dev/ttyUSB0")
    parser.add_argument("--transcript-path")
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
            return 0
        kit_root = Path(__file__).resolve().parent
        installer = kit_root / "ARTIFACTS" / "STR8-iN65-LOADER-2000.s19"
        candidate = kit_root / "ARTIFACTS" / "STR8-N-v1-29.bin"
        bank_maint = kit_root / "ARTIFACTS" / "STR8-iN65-BANK-MAINT-2000.s19"
        for path in (installer, candidate, bank_maint):
            if not path.is_file():
                raise LoaderError(f"Migration kit is incomplete: {path}")
        candidate_data = candidate.read_bytes()
        if len(candidate_data) != 4096:
            raise LoaderError(f"Canonical STR8-N BIN is {len(candidate_data)} bytes; expected 4096")
        image = read_migration_s19(installer)
        device = select_port(args.port)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        transcript = Path(args.transcript_path) if args.transcript_path else kit_root / "LOCAL" / f"factory-migration-linux-{stamp}.raw"
        print()
        print("STR8-iN/65 LOADER - PYTHON/UBUNTU EXPERIMENTAL")
        print("Factory WDCMONv2 -> STR8-N 1.29")
        print("STATUS ....................................... UNTESTED ON LINUX HARDWARE")
        print("Windows 11 PowerShell remains the board-proven reference.")
        print(f"Port ......................................... {device}")
        print("Top image .................................... 4096 bytes; $F000-$FFFF")
        print("Evidence ..................................... full raw + event logs")
        print()
        print("READ THE SCREEN: enter commands and press control keys only when requested.")
        print("Confirmations: COPY B3 TO B0, then INSTALL STR8-N 1.29.")
        print("When the screen asks for the top BIN, press CTRL+U once.")
        print("After boot, follow the screen: S, L, CTRL+D once, D, then 0, FF, WDCV2, ADOPT B0.")
        print("Do not reset, assert NMI, or remove power during active flash writes.")
        if args.details:
            print()
            print("DETAILS")
            print("  Bank 3 is preserved byte-for-byte as an opaque 32K Bank-0 guest.")
            print("  B1 and B2 are not migration destinations.")
            print("  D0 is written only in the Bank-3 directory after verified v1.29 boot.")
            print(f"  STR8-N TOP BIN    = {candidate.name}")
            print(f"  BIN SHA-256       = {hashlib.sha256(candidate_data).hexdigest().upper()}")
            print("  T48 DEVICE OFFSET = $1F000")
            print(f"  RAW TRANSCRIPT    = {transcript}")
            print(f"  HOST EVENT LOG    = {transcript}.events.txt")
        print()
        run_loader(device, image, candidate, bank_maint, transcript, force=args.force)
        print()
        print("NEXT: connect a serial terminal at 115200-8N1 and press physical RESET.")
        print("STR8-N 1.29 must appear; require D0 FF WDCV2 FFFF FCFFFFFF.")
        print("J0 is a complete handoff to the preserved factory system.")
        print("Physical RESET is the designed return to STR8-N; this is not a flaw.")
        return 0
    except (LoaderError, OSError, KeyboardInterrupt) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
