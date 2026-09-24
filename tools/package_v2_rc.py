"""Package the frozen alpha21 image as a scoped local RC, without rebuilding."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent.parent
FREEZE = ROOT / "docs/STR8N_V2_ALPHA21_FREEZE.json"
SNAPSHOT = ROOT / "output/qualification/v2-alpha21-2026-09-24"
DEST = ROOT / "output/release/str8n-v2-rc1"
BOARD_TOP_SHA256 = "3738eab501c50ef0470e9a81ef573b563da7dc656cc18a83573d16c9bd2e6e49"
ARTIFACTS = (
    "str8n-v2-alpha21-e000-ffff.bin",
    "str8n-v2-alpha21-e000-ffff.s19",
    "str8n-v2-alpha21-8000-ffff.bin",
    "str8n-v2-alpha21-8000-ffff.s19",
)
PUBLIC_FILES = {
    "README.md": ROOT / "docs/STR8N_V2_RC1_PACKAGE_README.md",
    "GETTING-STARTED-816.md": ROOT / "docs/STR8N_V2_RC1_GETTING_STARTED_816.md",
    "QUALIFICATION-CHECKLIST-816.md": ROOT / "docs/STR8N_V2_RC1_816_QUALIFICATION_CHECKLIST.md",
    "QUALIFICATION-CHECKLIST-816.pdf": ROOT / "output/pdf/STR8N_V2_RC1_816_QUALIFICATION_CHECKLIST.pdf",
    "LICENSE": ROOT / "LICENSE",
    "START-STR8N-V2-RC1.ps1": ROOT / "tools/wdcmonv2/START-STR8N-V2-RC1.ps1",
    "VERIFY-STR8N-V2-READBACK.ps1": ROOT / "tools/wdcmonv2/VERIFY-STR8N-V2-READBACK.ps1",
    "TOOLS/start_wdcmonv2_ram.ps1": ROOT / "tools/wdcmonv2/start_wdcmonv2_ram.ps1",
    "APPLICATIONS/str8n-v2-alpha21-b3-top-update-2000.a": ROOT / "tools/v2-apps/str8n-v2-alpha21-b3-top-update-2000.a",
    "APPLICATIONS/str8n-v2-bank3-id-2000.a": ROOT / "tools/v2-apps/str8n-v2-bank3-id-2000.a",
    "APPLICATIONS/README.md": ROOT / "docs/STR8N_V2_RC1_ASMF2_APPLICATIONS.md",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if freeze["candidate"] != "STR8-N 2.0a21":
        raise ValueError("unexpected freeze identity")
    package: dict[str, bytes] = {}
    for name in ARTIFACTS:
        data = (SNAPSHOT / "candidate" / name).read_bytes()
        if sha256(data) != freeze["candidate_files"][name]:
            raise ValueError(f"freeze hash mismatch: {name}")
        package[f"FIRMWARE/{name}"] = data
    top = package["FIRMWARE/str8n-v2-alpha21-e000-ffff.bin"][-4096:]
    if sha256(top) != BOARD_TOP_SHA256:
        raise ValueError("packaged Bank 3 F differs from board readback")
    subprocess.run(["python", str(ROOT / "tools/build_v2_rc_a.py")],
                   cwd=ROOT, check=True)
    package["FIRMWARE/str8n-v2-alpha21-b3-top-update-2000.s19"] = (
        ROOT / "BUILD/v2-alpha21/str8n-v2-alpha21-b3-top-update-2000.s19").read_bytes()
    package["FIRMWARE/str8n-v2-bank3-id-2000.s19"] = (
        ROOT / "BUILD/v2-rc1-apps/str8n-v2-bank3-id-2000.s19").read_bytes()
    subprocess.run(["python", str(ROOT / "tools/build_v2_rc_qualification_pdf.py")],
                   cwd=ROOT, check=True)
    subprocess.run(["python", str(ROOT / "tools/build_v2_rc1_wdcmon_ram.py")],
                   cwd=ROOT, check=True)
    build = ROOT / "BUILD/v2-rc1-wdcmon-ram"
    built_top = (build / "str8n-v2-alpha21-f000-ffff.bin").read_bytes()
    if built_top != top:
        raise ValueError("RAM installer top BIN differs from frozen firmware")
    package["FIRMWARE/str8n-v2-alpha21-f000-ffff.bin"] = built_top
    package["FIRMWARE/str8n-v2-rc1-wdcmonv2-install-2000.s19"] = (
        build / "str8n-v2-rc1-wdcmonv2-install-2000.s19").read_bytes()
    for name, path in PUBLIC_FILES.items():
        package[name] = path.read_bytes()
    allowed = {f"FIRMWARE/{name}" for name in ARTIFACTS} | {
        "FIRMWARE/str8n-v2-alpha21-f000-ffff.bin",
        "FIRMWARE/str8n-v2-rc1-wdcmonv2-install-2000.s19",
        "FIRMWARE/str8n-v2-alpha21-b3-top-update-2000.s19",
        "FIRMWARE/str8n-v2-bank3-id-2000.s19",
        *PUBLIC_FILES.keys(),
    }
    if set(package) != allowed:
        raise ValueError("public package allowlist mismatch")
    manifest = {
        "release": "STR8-N 2.0 RC1",
        "firmware": freeze["candidate"],
        "source_freeze": "docs/STR8N_V2_ALPHA21_FREEZE.json in repository",
        "board_2512_bank3_f_sha256": BOARD_TOP_SHA256,
        "stock_wdcmonv2_firmware_included": False,
        "owner_bank_archives_included": False,
        "migration_hardware_tested": False,
        "files": {name: sha256(data) for name, data in sorted(package.items())},
    }
    package["MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    DEST.mkdir(parents=True, exist_ok=True)
    archive = DEST / "str8n-v2-rc1.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as out:
        for name, data in sorted(package.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            out.writestr(info, data)
    with ZipFile(archive) as check:
        if set(check.namelist()) != set(package):
            raise ValueError("ZIP entry allowlist mismatch")
        for name, expected in manifest["files"].items():
            if sha256(check.read(name)) != expected:
                raise ValueError(f"package verification failed: {name}")
    print(f"{archive.relative_to(ROOT)}: {sha256(archive.read_bytes())}")
    print(f"{len(package)} files; frozen firmware, board top, and RAM installer verified")


if __name__ == "__main__":
    main()
