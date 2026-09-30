"""Build or verify the allowlisted STR8-N 2.0a24 board-test ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from build_v2_a24 import read_s19
from verify_v2_a24_bank_maint_carrier import decode_carrier


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "BUILD/v2-alpha24"
MIGRATION = ROOT / "BUILD/v2-alpha24-wdcmon-ram"
DEST = ROOT / "output/release/str8n-v2-alpha24"
TOP_SHA256 = "43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a"
SR_SHA256 = "6df4b51df973ac5159b27e1bb5a32601d8c31c66b12717ed129201b2eb274f2d"
INSTALLER_SHA256 = "66bd1030c2f48444826f03562886fc4828d4047f36d4ba42d1e5f8e5396cbebe"
MAINT_SHA256 = "9dda57fe5a9ab0744c3db40b6ea3507efbc8ad15d2ddb2e66d8a623ad2559736"
SESSION_RAW_SHA256 = "d84513887537443752f42763bd960fff0729064751f5d1913ef1c067c3d9f6d3"
SESSION_EVENTS_SHA256 = "082a97a3acc96032bfb7c95a8d9d7227acbaa620704f4f3e48ae7d90e4267192"

SOURCES = {
    "FIRMWARE/str8n-v2-alpha24-f000-ffff.bin": BUILD / "str8n-v2-alpha24-f000-ffff.bin",
    "FIRMWARE/str8n-v2-alpha24-e000-efff.bin": BUILD / "str8n-v2-alpha24-e000-efff.bin",
    "FIRMWARE/str8n-v2-alpha24-e000-ffff.bin": BUILD / "str8n-v2-alpha24-e000-ffff.bin",
    "FIRMWARE/str8n-v2-alpha24-e000-ffff.s19": BUILD / "str8n-v2-alpha24-e000-ffff.s19",
    "FIRMWARE/str8n-v2-alpha24-8000-ffff.bin": BUILD / "str8n-v2-alpha24-8000-ffff.bin",
    "FIRMWARE/str8n-v2-alpha24-8000-ffff.s19": BUILD / "str8n-v2-alpha24-8000-ffff.s19",
    "FIRMWARE/str8n-v2-alpha24-wdcmonv2-install-2000.s19": MIGRATION / "str8n-v2-alpha24-wdcmonv2-install-2000.s19",
    "APPLICATIONS/str8n-v2-bank-maint-2000.s19": ROOT / "tools/v2-apps/str8n-v2-bank-maint-2000.s19",
    "APPLICATIONS/str8n-v2-bank-maint-2000.a": ROOT / "tools/v2-apps/str8n-v2-bank-maint-2000.a",
    "APPLICATIONS/str8n-v2-alpha24-b3-top-update-2000.s19": BUILD / "str8n-v2-alpha24-b3-top-update-2000.s19",
    "APPLICATIONS/str8n-v2-alpha24-b3-top-update-2000.a": BUILD / "str8n-v2-alpha24-b3-top-update-2000.a",
    "PUBLIC/str8n-v2-public.inc": ROOT / "src/v2a24/str8n-v2-public.inc",
    "MIGRATE-STR8N-V2-A24.ps1": ROOT / "tools/wdcmonv2/MIGRATE-STR8N-V2-A24.ps1",
    "GUIDE-816.md": ROOT / "docs/STR8N_V2_A24_816_MANUAL_MIGRATION.md",
    "MAPS.md": ROOT / "docs/STR8N_V2_A24_MAPS.md",
    "STR8N_V2_2609_B0_TO_B3_RESTORE_2026-09-30.md": ROOT / "docs/STR8N_V2_2609_B0_TO_B3_RESTORE_2026-09-30.md",
    "STR8N_V2_2609_MANUAL_REMIGRATION_2026-09-30.md": ROOT / "docs/STR8N_V2_2609_MANUAL_REMIGRATION_2026-09-30.md",
    "STR8N_V2_A24_2609_OPERATOR_SESSION.md": ROOT / "docs/STR8N_V2_A24_2609_OPERATOR_SESSION.md",
    "EVIDENCE/v2-a24-migration-20260930-152511.raw": ROOT / "docs/evidence/board-2609-a24/v2-a24-migration-20260930-152511.raw",
    "EVIDENCE/v2-a24-migration-20260930-152511.raw.events.txt": ROOT / "docs/evidence/board-2609-a24/v2-a24-migration-20260930-152511.raw.events.txt",
    "CHECKLIST-816.md": ROOT / "docs/STR8N_V2_A24_816_CHECKLIST.md",
    "CHECKLIST-816.pdf": ROOT / "output/pdf/STR8N_V2_A24_816_CHECKLIST.pdf",
    "README.md": ROOT / "docs/STR8N_V2_A24_PACKAGE_README.md",
    "LICENSE": ROOT / "LICENSE",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def exact_s19(s19: bytes, start: int, image: bytes, scratch: Path) -> None:
    scratch.write_bytes(s19)
    try:
        memory, entry = read_s19(scratch)
    finally:
        scratch.unlink()
    expected = {start + offset: byte for offset, byte in enumerate(image)}
    if memory != expected or entry != 0xF004:
        raise ValueError(f"S19 differs from dense image at ${start:04X}")


def validate_payload(payload: dict[str, bytes], scratch: Path) -> None:
    f = payload["FIRMWARE/str8n-v2-alpha24-f000-ffff.bin"]
    ef = payload["FIRMWARE/str8n-v2-alpha24-e000-ffff.bin"]
    bank = payload["FIRMWARE/str8n-v2-alpha24-8000-ffff.bin"]
    if len(f) != 4096 or sha256(f) != TOP_SHA256:
        raise ValueError("F image differs from board-tested alpha24")
    if len(ef) != 8192 or ef[-4096:] != f:
        raise ValueError("E/F image does not contain the exact alpha24 F")
    e = payload["FIRMWARE/str8n-v2-alpha24-e000-efff.bin"]
    if len(e) != 4096 or e != ef[:4096]:
        raise ValueError("T48 E page does not match canonical E/F image")
    if sha256(ef[0x800:0xF00]) != SR_SHA256:
        raise ValueError("E S/R slice differs from board-tested code")
    if len(bank) != 32768 or bank[-8192:] != ef:
        raise ValueError("Full bank does not contain the canonical E/F")
    exact_s19(payload["FIRMWARE/str8n-v2-alpha24-e000-ffff.s19"],
              0xE000, ef, scratch)
    exact_s19(payload["FIRMWARE/str8n-v2-alpha24-8000-ffff.s19"],
              0x8000, bank, scratch)
    installer = payload["FIRMWARE/str8n-v2-alpha24-wdcmonv2-install-2000.s19"]
    if sha256(installer) != INSTALLER_SHA256:
        raise ValueError("Migration installer identity changed")
    maint_s19 = payload["APPLICATIONS/str8n-v2-bank-maint-2000.s19"]
    scratch.write_bytes(maint_s19)
    try:
        maint, entry = read_s19(scratch)
    finally:
        scratch.unlink()
    carrier = decode_carrier(payload["APPLICATIONS/str8n-v2-bank-maint-2000.a"].decode("ascii"))
    if entry != 0x2000 or carrier != maint:
        raise ValueError("Bank-maintenance .a/.s19 image mismatch")
    image = bytes(maint[address] for address in range(0x2000, 0x2000 + len(maint)))
    if len(image) != 703 or sha256(image) != MAINT_SHA256:
        raise ValueError("Static bank-maintenance image changed")
    raw = payload["EVIDENCE/v2-a24-migration-20260930-152511.raw"]
    events = payload["EVIDENCE/v2-a24-migration-20260930-152511.raw.events.txt"]
    if sha256(raw) != SESSION_RAW_SHA256 or sha256(events) != SESSION_EVENTS_SHA256:
        raise ValueError("Operator session evidence changed")
    if (b"TYPE INSTALL STR8-N 2.0a24> INSTALL STR8-N 2.0A24" not in raw
            or b"MIGRATION VERIFIED; PRESS PHYSICAL RESET" not in raw
            or b"TX LINE install str8-n 2.0a24" not in events
            or b"SESSION END OUTCOME=TERMINAL CLOSED BY OPERATOR" not in events):
        raise ValueError("Operator session prompt, input, or result missing")
    updater_s19 = payload["APPLICATIONS/str8n-v2-alpha24-b3-top-update-2000.s19"]
    scratch.write_bytes(updater_s19)
    try:
        updater, updater_entry = read_s19(scratch)
    finally:
        scratch.unlink()
    updater_carrier = decode_carrier(payload["APPLICATIONS/str8n-v2-alpha24-b3-top-update-2000.a"].decode("ascii"))
    if updater_entry != 0x2000 or updater_carrier != updater or bytes(updater[a] for a in range(0x4000, 0x5000)) != f:
        raise ValueError("Top updater S19/.a mismatch or wrong candidate")


def verify_archive(archive: Path) -> dict:
    with ZipFile(archive) as z:
        expected = set(SOURCES) | {"MANIFEST.json"}
        if len(z.namelist()) != len(expected) or set(z.namelist()) != expected:
            raise ValueError("Package allowlist or duplicate entry mismatch")
        manifest = json.loads(z.read("MANIFEST.json"))
        if manifest["package"] != "STR8-N 2.0a24 board-test" or set(manifest["files"]) != set(SOURCES):
            raise ValueError("Package manifest identity or file list mismatch")
        payload = {name: z.read(name) for name in SOURCES}
        for name, data in payload.items():
            if sha256(data) != manifest["files"][name]:
                raise ValueError(f"Package hash mismatch: {name}")
    scratch = archive.parent / ".str8n-a24-verify.s19"
    validate_payload(payload, scratch)
    return manifest


def build() -> Path:
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT):
        raise ValueError("Commit source and package documents before building the distributable ZIP")
    payload = {name: path.read_bytes() for name, path in SOURCES.items()}
    DEST.mkdir(parents=True, exist_ok=True)
    validate_payload(payload, DEST / ".str8n-a24-verify.s19")
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = {
        "package": "STR8-N 2.0a24 board-test",
        "firmware": "STR8-N 2.0a24",
        "source_commit": source_commit,
        "board_2609_bank3_f_sha256": TOP_SHA256,
        "board_2609_sr_slice_sha256": SR_SHA256,
        "edu_attached_qualified": False,
        "stock_wdcmonv2_firmware_included": False,
        "owner_bank_archives_included": False,
        "owner_approved_operator_session_included": True,
        "files": {name: sha256(data) for name, data in sorted(payload.items())},
    }
    payload["MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    archive = DEST / "str8n-v2-alpha24-board-test.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as z:
        for name, data in sorted(payload.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            z.writestr(info, data)
    verify_archive(archive)
    (DEST / "str8n-v2-alpha24-board-test.sha256").write_text(
        f"{sha256(archive.read_bytes())}  {archive.name}\n", encoding="ascii")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path, help="Verify an extracted package ZIP")
    args = parser.parse_args()
    archive = args.verify or build()
    manifest = verify_archive(archive)
    print(f"PASS: {archive}: SHA-256 {sha256(archive.read_bytes())}")
    print(f"{len(manifest['files'])} allowlisted files; source {manifest['source_commit']}")


if __name__ == "__main__":
    main()
