"""Build ASM-F2 ORG/DB carriers from the frozen RC1 RAM programs."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "output/qualification/v2-alpha21-2026-09-24/candidate"
ASM_TOP_SHA256 = "61d7541bbe21989c39a00e4ed771b93dfd6d00cfd0f4c5d35da1bd41f8a00583"
BUILD = ROOT / "BUILD/v2-rc1-apps"
APPS = ROOT / "tools/v2-apps"
TOP_S19 = ROOT / "BUILD/v2-alpha21/str8n-v2-alpha21-b3-top-update-2000.s19"
INFO_SOURCE = APPS / "str8n-v2-bank3-id-2000.asm"
INFO_S19 = BUILD / "str8n-v2-bank3-id-2000.s19"


def s19_bytes(path: Path) -> tuple[dict[int, int], int]:
    data: dict[int, int] = {}
    entry: int | None = None
    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith("S0"):
            continue
        if not re.fullmatch(r"S[19][0-9A-Fa-f]+", line):
            raise ValueError(f"unsupported S19 record in {path.name}: {line}")
        row = bytes.fromhex(line[2:])
        if len(row) != row[0] + 1 or sum(row) & 255 != 255:
            raise ValueError(f"invalid S19 count/checksum: {path.name}")
        address = int.from_bytes(row[1:3], "big")
        if line[1] == "9":
            if entry is not None:
                raise ValueError("multiple S9 records")
            entry = address
            continue
        for offset, byte in enumerate(row[3:-1]):
            target = address + offset
            if target in data:
                raise ValueError(f"duplicate S19 byte at ${target:04X}")
            data[target] = byte
    if not data or entry != 0x2000 or min(data) != 0x2000:
        raise ValueError(f"expected nonempty $2000 image and entry: {path.name}")
    if len(data) != max(data) - min(data) + 1:
        raise ValueError(f"image is not dense: {path.name}")
    if max(data) >= 0x6900:
        raise ValueError(f"image overlaps v2 sector buffer: {path.name}")
    return data, entry


def make_carrier(data: dict[int, int], output: Path, role: str) -> None:
    last = max(data)
    lines = [
        f"; {output.name.upper()}",
        "; ASM-F2 ORG/DB image carrier for the public R-YORS 00.0915(2324) assembler.",
        f"; {role}",
        "; ASM NEW; send complete file; require END/SEAL with no ERR; enter .; G 2000.",
        "; Source bytes are checked against the matching RC1 S19; do not edit DB rows.",
        "",
        "        ORG $2000",
    ]
    for address in range(0x2000, last + 1, 8):
        row = [data[x] for x in range(address, min(address + 8, last + 1))]
        lines.append("        DB " + ",".join(f"${byte:02X}" for byte in row))
    lines.extend(["        END", ""])
    output.write_bytes("\r\n".join(lines).encode("ascii"))
    loaded: dict[int, int] = {}
    pc: int | None = None
    for line in output.read_text(encoding="ascii").splitlines():
        stripped = line.strip()
        if stripped.startswith("ORG "):
            pc = int(stripped[5:].removeprefix("$"), 16)
        elif stripped.startswith("DB "):
            assert pc is not None
            for field in stripped[3:].split(","):
                loaded[pc] = int(field.removeprefix("$"), 16)
                pc += 1
    if loaded != data:
        raise ValueError(f"carrier image mismatch: {output.name}")
    print(f"{output.relative_to(ROOT)}: {len(data)} exact bytes, $2000-${last:04X}")


def main() -> None:
    subprocess.run(["python", str(ROOT / "tools/build_v2.py")],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    built_firmware = ROOT / "BUILD/v2-alpha21/str8n-v2-alpha21-e000-ffff.bin"
    frozen_firmware = SNAPSHOT / "str8n-v2-alpha21-e000-ffff.bin"
    if built_firmware.read_bytes() != frozen_firmware.read_bytes():
        raise ValueError("rebuilt firmware differs from frozen alpha21")
    if hashlib.sha256(TOP_S19.read_bytes()).hexdigest() != ASM_TOP_SHA256:
        raise ValueError("ASM-F2 top-updater S19 hash mismatch")
    BUILD.mkdir(parents=True, exist_ok=True)
    local_source = BUILD / INFO_SOURCE.name
    shutil.copyfile(INFO_SOURCE, local_source)
    subprocess.run(["wdc02as", "-G", "-L", "-S", "-W", str(local_source)],
                   cwd=BUILD, check=True)
    subprocess.run(["wdcln", "-g", "-s", "-t", "-hm19", "-j", "-o",
                    str(INFO_S19), str(BUILD / (INFO_SOURCE.stem + ".obj"))],
                   cwd=BUILD, check=True)
    lines = INFO_S19.read_text(encoding="ascii").splitlines()
    lines[-1] = "S9032000DC"
    INFO_S19.write_text("\n".join(lines) + "\n", encoding="ascii")
    make_carrier(s19_bytes(TOP_S19)[0],
                 APPS / "str8n-v2-alpha21-b3-top-update-2000.a",
                 "Guarded B3:F update; v2 cancel enters HOLD at $F007, not signature $F000.")
    make_carrier(s19_bytes(INFO_S19)[0],
                 APPS / "str8n-v2-bank3-id-2000.a",
                 "Read-only Bank 3 top header/vector; restores the caller's flash overlay.")


if __name__ == "__main__":
    main()
