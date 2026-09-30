"""Build a distributable, exact-image B3:E updater template from synthetic data."""

from pathlib import Path
import subprocess
import sys

import build_v2_a24 as firmware


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "BUILD/v2-alpha24-e-template"
NAME = "b3-e-guarded-template-2000.s19"


def main() -> None:
    out = OUT / "build"
    out.mkdir(parents=True, exist_ok=True)
    f = (firmware.OUT / f"{firmware.STEM}-f000-ffff.bin").read_bytes()
    e = (firmware.OUT / f"{firmware.STEM}-e000-efff.bin").read_bytes()
    if len(f) != 4096 or len(e) != 4096:
        raise ValueError("Build alpha24 F and E before the E updater template")
    old_e = bytes(4096)
    new_e = old_e[:0x800] + e[0x800:0xf00] + old_e[0xf00:]
    source = out / "synthetic-ef.bin"
    staged = out / "synthetic-e.bin"
    source.write_bytes(old_e + f)
    staged.write_bytes(new_e)
    subprocess.run([sys.executable, str(ROOT / "tools/build_v2_a24_816_e_install.py"),
                    str(source), str(staged), "--out", str(out)], check=True)
    original = out / "str8n-v2-alpha24-board2609-e-install-2000.s19"
    lines = original.read_text(encoding="ascii").splitlines()
    lines[0] = firmware.record("0", 0, b"STR8-N 2.0a24 B3:E template")
    target = OUT / NAME
    target.write_text("\n".join(lines) + "\n", encoding="ascii")
    memory, entry = firmware.read_s19(target)
    end = max(memory) + 1
    if entry != 0x2000 or set(memory) != set(range(0x2000, end)):
        raise ValueError("E template is not a dense RAM image")
    if bytes(memory[a] for a in range(end - 8192, end - 4096)) != new_e:
        raise ValueError("E template new sector is misplaced")
    if bytes(memory[a] for a in range(end - 4096, end)) != old_e:
        raise ValueError("E template old sector is misplaced")
    print(target)


if __name__ == "__main__":
    main()
