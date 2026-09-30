"""Build a guarded alpha24 Bank 3 E installer from an exact 8 KiB E/F readback.

Python standard library only. This tool does not contact or write the board.
"""

import argparse
import hashlib
import json
from pathlib import Path


F_SHA256 = "43e6ee966963e1cc401986581742cc75b302cd0a02cfaf22965fe7ab8a43ec1a"
SR_SHA256 = "6df4b51df973ac5159b27e1bb5a32601d8c31c66b12717ed129201b2eb274f2d"
TEMPLATE_SHA256 = "75627feb8004207d00a7ab4a266d4006a743cb29699a0535be3375c00f736d92"
NAME = "str8n-v2-alpha24-b3-e-guarded-install-2000.s19"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(kind, address, data=b""):
    raw = bytes([len(data) + 3]) + address.to_bytes(2, "big") + data
    return "S" + kind + (raw + bytes([(~sum(raw)) & 255])).hex().upper()


def read_s19(data):
    memory = {}
    entry = None
    for line in data.decode("ascii").splitlines():
        if len(line) < 10 or line[:1] != "S" or line[1] not in "019":
            raise ValueError("Unsupported or malformed S-record")
        raw = bytes.fromhex(line[2:])
        if len(raw) != raw[0] + 1 or sum(raw) & 255 != 255:
            raise ValueError("S-record count or checksum mismatch")
        address = int.from_bytes(raw[1:3], "big")
        if line[1] == "1":
            for offset, value in enumerate(raw[3:-1]):
                if address + offset in memory:
                    raise ValueError("Duplicate RAM address in template")
                memory[address + offset] = value
        elif line[1] == "9":
            if entry is not None:
                raise ValueError("Duplicate S9 entry")
            entry = address
    if entry != 0x2000 or not memory:
        raise ValueError("Template entry is not $2000")
    end = max(memory) + 1
    if set(memory) != set(range(0x2000, end)):
        raise ValueError("Template RAM image is not dense from $2000")
    return bytearray(memory[address] for address in range(0x2000, end))


def build(source_ef, template, generic_e):
    if len(source_ef) != 8192:
        raise ValueError("Readback must be exactly 8192 bytes: B3 $E000-$FFFF")
    old_e, live_f = source_ef[:4096], source_ef[4096:]
    if sha(live_f) != F_SHA256:
        raise ValueError("B3:F readback is not the exact alpha24 monitor")
    if len(generic_e) != 4096 or sha(generic_e[0x800:0xF00]) != SR_SHA256:
        raise ValueError("Packaged E image does not contain the alpha24 S/R code")
    if sha(template) != TEMPLATE_SHA256:
        raise ValueError("Guarded E updater template identity mismatch")
    image = read_s19(template)
    if len(image) < 8192:
        raise ValueError("Template is too short")
    new_at = len(image) - 8192
    old_at = len(image) - 4096
    expected_template_e = bytes(0x800) + generic_e[0x800:0xF00] + bytes(0x100)
    if image[new_at:old_at] != expected_template_e or image[old_at:] != bytes(4096):
        raise ValueError("Template E image layout changed")
    new_e = old_e[:0x800] + generic_e[0x800:0xF00] + old_e[0xF00:]
    if new_e == old_e:
        raise ValueError("B3:E already contains the alpha24 S/R code")
    image[new_at:old_at] = new_e
    image[old_at:] = old_e
    lines = [record("0", 0, b"STR8-N 2.0a24 guarded B3:E")]
    lines.extend(record("1", address, image[address - 0x2000:address - 0x2000 + 32])
                 for address in range(0x2000, 0x2000 + len(image), 32))
    lines.append(record("9", 0x2000))
    result = ("\n".join(lines) + "\n").encode("ascii")
    if read_s19(result) != image:
        raise ValueError("Generated installer failed S19 round-trip")
    return result, new_e


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("readback", type=Path, help="exact binary B3:E/F readback, 8192 bytes")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    root = Path(__file__).resolve().parent.parent
    parser.add_argument("--template", type=Path, default=Path(__file__).with_name("b3-e-guarded-template-2000.s19"))
    parser.add_argument("--e-bin", type=Path, default=root / "FIRMWARE/str8n-v2-alpha24-e000-efff.bin")
    args = parser.parse_args()
    source = args.readback.read_bytes()
    result, new_e = build(source, args.template.read_bytes(), args.e_bin.read_bytes())
    args.out.mkdir(parents=True, exist_ok=True)
    installer = args.out / NAME
    staged = args.out / "str8n-v2-alpha24-b3-e-preserved.bin"
    report = args.out / "b3-e-installer-manifest.json"
    if any(path.exists() for path in (installer, staged, report)):
        raise FileExistsError("Refusing to replace an existing B3:E installer or evidence")
    installer.write_bytes(result)
    staged.write_bytes(new_e)
    report.write_text(json.dumps({
        "firmware": "STR8-N 2.0a24",
        "source_ef_sha256": sha(source),
        "old_e_sha256": sha(source[:4096]),
        "f_sha256": sha(source[4096:]),
        "new_e_sha256": sha(new_e),
        "installer_s19_sha256": sha(result),
        "preserved_ranges": ["E000-E7FF", "EF00-EFFF"],
        "replaced_range": "E800-EEFF",
        "board_installed": False,
    }, indent=2) + "\n", encoding="ascii")
    print(installer)
    print(f"OLD E SHA-256 {sha(source[:4096])}")
    print(f"NEW E SHA-256 {sha(new_e)}")
    print("Host preparation only; verify the exact live B3:E/F preimage before loading the S19")


if __name__ == "__main__":
    main()
