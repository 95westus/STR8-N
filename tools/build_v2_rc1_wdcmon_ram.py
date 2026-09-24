"""Build the independent WDCMONv2-to-STR8-N alpha21 RAM installer."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "output/qualification/v2-alpha21-2026-09-24/candidate"
BUILD = ROOT / "BUILD/v2-rc1-wdcmon-ram"
SOURCE = ROOT / "tools/wdcmonv2/wdcmonv2str8n-install-2000.asm"
BOARD_TOP_SHA256 = "3738eab501c50ef0470e9a81ef573b563da7dc656cc18a83573d16c9bd2e6e49"


def run(*args: str) -> None:
    subprocess.run(args, cwd=BUILD, check=True)


def main() -> None:
    image = (SNAPSHOT / "str8n-v2-alpha21-e000-ffff.bin").read_bytes()
    if len(image) != 8192:
        raise ValueError("frozen E-F BIN has wrong length")
    top = image[-4096:]
    if hashlib.sha256(top).hexdigest() != BOARD_TOP_SHA256:
        raise ValueError("frozen top differs from board readback")
    if top[:4] != b"SN\x02\x00" or top[0xFFC:0xFFE] == b"\xff\xff":
        raise ValueError("top lacks v2 signature or RESET vector")
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "str8n-v2-alpha21-f000-ffff.bin").write_bytes(top)
    fnv = 2166136261
    for byte in top:
        fnv = ((fnv ^ byte) * 16777619) & 0xFFFFFFFF
    inc = BUILD / "str8n-v2-rc1-wdcmonv2-install-image.inc"
    inc.write_text("".join(
        f"W2I_CANDIDATE_FNV{n}      EQU             ${((fnv >> (8 * n)) & 255):02X}\n"
        for n in range(4)
    ), encoding="ascii")
    local_source = BUILD / SOURCE.name
    shutil.copyfile(SOURCE, local_source)
    run("wdc02as", "-G", "-L", "-S", "-W", "-I", str(BUILD),
        "-DSTR8_V2_RC1=1", str(local_source))
    s19 = BUILD / "str8n-v2-rc1-wdcmonv2-install-2000.s19"
    run("wdcln", "-g", "-s", "-t", "-hm19", "-j", "-o", str(s19),
        str(local_source.with_suffix(".obj")))
    lines = s19.read_text(encoding="ascii").splitlines()
    lines[-1] = "S9032000DC"
    s19.write_text("\n".join(lines) + "\n", encoding="ascii")
    run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(ROOT / "tools/wdcmonv2/check_wdcmonv2_install.ps1"),
        "-SourcePath", str(SOURCE), "-S19Path", str(s19),
        "-MapPath", str(s19.with_suffix(".map")),
        "-TopBinPath", str(BUILD / "str8n-v2-alpha21-f000-ffff.bin"),
        "-CandidateBinPath", str(BUILD / "str8n-v2-alpha21-f000-ffff.bin"),
        "-VersionText", "2.0a21", "-V2Signature")
    run("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        str(ROOT / "tools/wdcmonv2/start_wdcmonv2_ram.ps1"),
        "-ImagePath", str(s19), "-ValidateOnly")
    print(f"WDCMONv2 RAM installer: {s19}")


if __name__ == "__main__":
    main()
