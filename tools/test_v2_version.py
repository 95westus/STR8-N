"""VERSION: actual/default monitor identity, fallback and read-only behavior."""
import os
os.environ.setdefault('STR8_RTC_BUILD', 'BUILD/v2-version')
import json
from pathlib import Path
from beta4_migration import crc, journal, metadata, config_sum
from test_v2_status import fresh, boot, snapshot, OUT
from test_v2_storage import cmd
from test_v2_board_name import record

ROOT = Path(__file__).resolve().parents[1]
META = json.loads((OUT/'build.json').read_text())
PRIOR = ROOT/'output/qualification/version-2609-2026-10-15/prior-verified'


def fixture(off=False, slot=None):
    cpu, m = fresh(off=off)
    # Real 2609 mixed slots: beta24 A generation 35, beta25 B generation 37.
    prior = (PRIOR/'b3.bin').read_bytes()
    m.banks[3][0x2000:0x4000] = prior[0x2000:0x4000]
    j = journal(m.banks[3])
    cfg = bytearray(j[8:24])
    cfg[7:13] = b'P\xb0'+(37).to_bytes(4, 'little')
    cfg[14:] = config_sum(cfg)
    m.banks[3][0x4000:0x6000] = metadata(cfg, [0]*32, 1)+b'\xff'*(8192-128)
    m.banks[3][0x1C20:0x1C40] = record(b'2609')
    sent = False
    def key(c):
        nonlocal sent
        if slot and not sent and c.pc == META['boot']['BOOT_RECOVERY_WINDOW']:
            m.rx.extend(slot)
            sent = True
        return False
    boot(cpu, key if slot else None)
    return cpu, m


def verify_query(cpu, m, running, version, default):
    before = snapshot(m)
    app = bytes(m.ram[0x200:0x6700])
    bank = m.ram[0xF3]
    active = m.ram[0x7D30]
    accesses, frames = len(m.bus.accesses), len(m.spi.frames)
    out = cmd(cpu, m, b'VERSION\r')
    assert version in out, out
    assert b'Board: 2609' in out
    assert running in out, out
    assert default in out, out
    assert snapshot(m) == before
    assert bytes(m.ram[0x200:0x6700]) == app
    assert m.ram[0x7D30] == active and m.ram[0xF3] == bank
    assert len(m.bus.accesses) == accesses and len(m.spi.frames) == frames
    assert out.endswith(b'\r\n\r\nB3> '), out
    return out


def main():
    checks = []
    for slot in (None, b'A'):
        cpu, m = fixture(slot=slot)
        if slot:
            running, version = b'Running: MONITOR A, gen 00000023', b'STR8-N 2.0b24 B3 65C02'
        else:
            running, version = b'Running: MONITOR B, gen 00000025', b'STR8-N 2.0b25 B3 65C02'
        out = verify_query(cpu, m, running, version, b'MONITOR B gen 00000025 VALID default')
        assert b'MONITOR A gen 00000023 VALID default' not in out
        (OUT/('version-'+('A' if slot else 'B')+'-preview.txt')).write_bytes(out)
        # Data-view bank changes must not change the firmware bank label.
        cmd(cpu, m, b'B0\r')
        before = snapshot(m)
        out = cmd(cpu, m, b'VERSION\r')
        assert version in out and snapshot(m) == before, out
        cmd(cpu, m, b'B3\r')
        checks.append(('manual A vs default B' if slot else 'default B')+'; correct banner/generation; app/service RAM and bank preserved')
        print('PASS', checks[-1], flush=True)
    cpu, m = fixture(off=True)
    verify_query(cpu, m, b'Running: MONITOR B, gen 00000025', b'STR8-N 2.0b25', b'MONITOR B gen 00000025 VALID default')
    checks.append('EDU OFF VERSION performs no RTC/SPI access or reclaimed-RAM writes')
    cpu, m = fixture(slot=b'A')
    m.banks[3][0x301F] = 0xFF
    before = snapshot(m)
    out = cmd(cpu, m, b'VERSION\r')
    assert b'MONITOR A gen 00000023 VALID default' in out and b'MONITOR B INVALID' in out, out
    assert snapshot(m) == before and m.ram[0x7D30] == 0xA0
    checks.append('invalid preferred slot is reported invalid; actual default falls back to A')
    cpu, m = fixture()
    # Commands that merely start with VERSION must not be claimed.
    before = snapshot(m)
    for line in (b'VERSIO', b'VERSIONX', b'VERSION X'):
        out = cmd(cpu, m, line+b'\r')
        assert b'Running: MONITOR' not in out and snapshot(m) == before
    for fault in ('crc', 'header'):
        original = (OUT/'version/asset.bin').read_bytes()
        bad = bytearray(original)
        bad[0 if fault == 'header' else 100] ^= 1
        if fault == 'header':
            bad[-2:] = crc(bad[:-2]).to_bytes(2, 'big')
        m.banks[2][0x6800:0x7000] = bad
        before = snapshot(m)
        out = cmd(cpu, m, b'VERSION\r')
        # The compact combined loader uses the monitor's shared failure path.
        failure = b'Bad cmd' if META.get('battery_age') else b'Status error'
        assert failure in out and b'Running: MONITOR' not in out, out
        assert snapshot(m) == before
    checks.append('exact command match; bad CRC/header refused before execution')
    # Restore valid helper and check the shared loader still handles TIME.
    m.banks[2][0x6800:0x7000] = (OUT/'version/asset.bin').read_bytes()
    before = snapshot(m)
    text = cmd(cpu, m, b'TIME\r')
    assert b'Thu 2026-10-08 19:53:15 (+00:00)' in text and snapshot(m) == before
    checks.append('shared loader retains one-line TIME behavior')
    report = dict(passed=True, checks=checks, artifacts=META['artifacts'],
        version_asset_sha256=META['version_asset_sha256'],
        version_code_bytes=META['version_code_bytes'], board_access=False, boards_flashed=False)
    (OUT/'version-test-results.json').write_text(json.dumps(report, indent=2)+'\n')
    for check in checks[2:]:
        print('PASS', check, flush=True)


if __name__ == '__main__':
    main()
