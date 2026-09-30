"""Verify the published ASM-F2 bank-maintenance carrier against its S19."""

import hashlib
from pathlib import Path

from build_v2_a24 import read_s19


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools/v2-apps/str8n-v2-bank-maint-2000"
EXPECTED_MACHINE_SHA256 = (
    "9dda57fe5a9ab0744c3db40b6ea3507efbc8ad15d2ddb2e66d8a623ad2559736"
)


def decode_carrier(source: str) -> dict[int, int]:
    memory: dict[int, int] = {}
    pc = None
    ended = False
    for raw in source.splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        if ended:
            raise ValueError("ASM-F2 carrier has content after END")
        if line.startswith("ORG $"):
            if pc is not None:
                raise ValueError("ASM-F2 carrier has multiple ORG directives")
            pc = int(line[5:], 16)
            if pc != 0x2000:
                raise ValueError("ASM-F2 carrier origin is not $2000")
        elif line.startswith("DB "):
            if pc is None:
                raise ValueError("ASM-F2 carrier has DB before ORG")
            for field in line[3:].split(","):
                field = field.strip()
                if len(field) != 3 or not field.startswith("$"):
                    raise ValueError(f"Unsupported ASM-F2 byte: {field}")
                memory[pc] = int(field[1:], 16)
                pc += 1
        elif line == "END":
            ended = True
        else:
            raise ValueError(f"Unexpected ASM-F2 directive: {line}")
    if not ended or not memory:
        raise ValueError("ASM-F2 carrier is incomplete")
    return memory


def main() -> None:
    carrier = decode_carrier(BASE.with_suffix(".a").read_text(encoding="ascii"))
    s19, entry = read_s19(BASE.with_suffix(".s19"))
    if entry != 0x2000 or carrier != s19:
        raise ValueError("ASM-F2 carrier differs from the published S19")
    image = bytes(carrier[address] for address in range(0x2000, 0x2000 + len(carrier)))
    digest = hashlib.sha256(image).hexdigest()
    if len(image) != 703 or digest != EXPECTED_MACHINE_SHA256:
        raise ValueError("Bank-maintenance machine image changed")
    print(f"PASS: .a and .s19 carry {len(image)} exact bytes at $2000; SHA-256 {digest}")


if __name__ == "__main__":
    main()
