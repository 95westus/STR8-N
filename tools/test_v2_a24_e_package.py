"""Exercise the packaged B3:E updater builder against the CPU/flash model."""

import importlib.util
from pathlib import Path
import sys

import build_v2_a24 as firmware

sys.modules["build_v2"] = firmware
import test_v2_a24_console  # installs alpha24 FT245 timing in the CPU model
import test_v2_boot as boot
import test_v2_flash as flash


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "BUILD/v2-alpha24"
TEMPLATE = ROOT / "BUILD/v2-alpha24-e-template/b3-e-guarded-template-2000.s19"
TOOL = ROOT / "tools/v2-apps/BUILD-B3-E-UPDATER.py"
spec = importlib.util.spec_from_file_location("b3_e_package_tool", TOOL)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def exercise(old_e, mismatch=False, approve=True):
    f = (OUT / "str8n-v2-alpha24-f000-ffff.bin").read_bytes()
    e = (OUT / "str8n-v2-alpha24-e000-efff.bin").read_bytes()
    s19, new_e = builder.build(old_e + f, TEMPLATE.read_bytes(), e)
    updater = builder.read_s19(s19)
    assert bytes(updater[-4096:]) == old_e
    assert bytes(updater[-8192:-4096]) == new_e
    cpu, memory = flash.boot_flash(3)
    memory.banks[3][0x6000:0x7000] = old_e
    memory.banks[3][0x7000:0x8000] = f
    if mismatch:
        memory.banks[3][0x6800] ^= 1
    before_b0 = bytes(memory.banks[0])
    before_b2 = bytes(memory.banks[2])
    for offset, value in enumerate(updater):
        memory.ram[0x2000 + offset] = value
    cpu.pc, cpu.sp = 0x2000, 0xFF
    if mismatch:
        boot.run(cpu, lambda: cpu.pc == 0xF007, limit=2_000_000)
        assert b"OLD IMAGE MISMATCH" in memory.tx and not memory.events
        return
    boot.run(cpu, lambda: b"TYPE Y to repair>" in memory.tx, limit=2_000_000)
    assert not memory.events
    memory.rx.append(ord("Y" if approve else "N"))
    boot.run(cpu, lambda: cpu.pc == (0xF004 if approve else 0xF007), limit=15_000_000)
    if approve:
        assert bytes(memory.banks[3][0x6000:0x7000]) == new_e
        assert memory.events and all(event[1] == 3 and 0xE000 <= event[2] <= 0xEFFF
                                     for event in memory.events)
    else:
        assert not memory.events
    assert bytes(memory.banks[3][0x7000:0x8000]) == f
    assert bytes(memory.banks[0]) == before_b0
    assert bytes(memory.banks[2]) == before_b2


def main():
    blank = bytes(4096)
    patterned = bytes((i * 29 + 7) & 255 for i in range(4096))
    exercise(blank)
    exercise(patterned)
    exercise(patterned, mismatch=True)
    exercise(patterned, approve=False)
    print("PASS: blank/patterned E install, exact-preimage refusal, cancel, B0/B2/F preservation")


if __name__ == "__main__":
    main()
