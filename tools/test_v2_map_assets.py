"""Read-only firmware-asset map recognition and failure cases in linked code."""
import os
os.environ.setdefault('STR8_RTC_BUILD', 'BUILD/v2-map-assets')
import json
from pathlib import Path
from beta4_migration import crc
from test_v2_status import fresh, boot, snapshot, OUT
from test_v2_storage import cmd
from test_v2_local_time import invoke

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT/'output/qualification/map-assets-2609-2026-10-15/prior-verified-2'
META = json.loads((OUT/'build.json').read_text())
MAINT = json.loads((OUT/'maint/manifest.json').read_text())
S = MAINT['symbols']


def fixture():
    cpu, m = fresh()
    m.banks = [bytearray((PRIOR/f'b{i}.bin').read_bytes()) for i in range(4)]
    m.spi.banks = m.banks
    m.banks[1][:12288] = (OUT/META['maintenance_storage_file']).read_bytes()
    boot(cpu)
    return cpu, m


def main():
    checks = []
    cpu, m = fixture()
    before = snapshot(m)
    editor = bytes(m.ram[0x5000:0x6000])
    accesses, frames = len(m.bus.accesses), len(m.spi.frames)
    for view in (1, 2, 3):
        out = cmd(cpu, m, f'M{view}\r'.encode())
        assert out.endswith(b'B3> '), out[-300:]
        assert snapshot(m) == before and bytes(m.ram[0x5000:0x6000]) == editor
        assert len(m.bus.accesses) == accesses and len(m.spi.frames) == frames
        if view == 1:
            assert b'B2 .  .  S  S  +  F  F  .' in out, out
            assert b'F firmware assets' in out and b'B2:C800-D1FF status; B2:E local/board + VERSION.' in out
            assert b'B1 S  +  +  S  +  +' in out and b'B3 I  I  A  B* J  J  X  R' in out
        else:
            assert b'Firmware status formatter C800-D1FF reserved' in out, out
            assert b'Local/board E000-E6FF; VERSION E800-EFFF reserved' in out, out
            assert b'SR MAINT' in out and b'SR CLOCK' in out
        (OUT/f'map-M{view}-preview.txt').write_bytes(out)
        checks.append(f'M{view}: correct asset names/ownership; records/monitors retained; flash/device/editor preservation')
        print('PASS', checks[-1], flush=True)
    # Run actual identification code directly to cover failure cases cheaply.
    image = (OUT/'maint/board-name.bin').read_bytes()
    m.ram[0x2000:0x2000+len(image)] = image
    original = [bytes(b) for b in m.banks]
    def identify(bank, sector):
        m.ram[S['MAPBANK']] = bank
        m.ram[S['MAPSEC']] = sector
        m.ram[S['MAP_APP_OWNER']] = 0xFF
        m.ram[S['MAP_OWNER_END']:S['MAP_OWNER_END']+2] = b'\0\0'
        m.ram[S['MAP_STATUS']+(sector-0x80)//16] = ord('U')
        m[0x7FEC] = (m.ram[0x7FEC]&0x11)+(0xCC, 0xCE, 0xEC, 0xEE)[bank]
        invoke(cpu, S['MAP_IDENTIFY'])
        return chr(m.ram[S['MAP_KIND']])
    for start, length, sector, name in ((0x4800, 2560, 0xD0, 'status'),
                                        (0x6000, 1792, 0xE0, 'local'),
                                        (0x6800, 2048, 0xE0, 'VERSION')):
        for fault in ('crc', 'header', 'erased'):
            m.banks = [bytearray(b) for b in original]
            m.spi.banks = m.banks
            asset = bytearray(m.banks[2][start:start+length])
            if fault == 'erased':
                asset[:] = b'\xff'*length
            elif fault == 'header':
                asset[0] ^= 1
                asset[-2:] = crc(asset[:-2]).to_bytes(2, 'big')
            else:
                asset[100] ^= 1
            m.banks[2][start:start+length] = asset
            prior = snapshot(m)
            assert identify(2, sector) == 'U', (name, fault)
            assert snapshot(m) == prior
    checks.append('bad CRC/header and absent status/local/VERSION assets stay untagged')
    m.banks = [bytearray(b) for b in original]
    m.spi.banks = m.banks
    m.banks[0][0x6000:0x7000] = m.banks[2][0x6000:0x7000]
    assert identify(0, 0xE0) == 'U'
    checks.append('matching bytes in another bank are not mislabeled as firmware assets')
    report = dict(passed=True, checks=checks, artifacts=META['artifacts'],
        maintenance_sha256=MAINT['program_sha256'], storage_sha256=MAINT['storage_sha256'],
        board_access=False, boards_flashed=False)
    (OUT/'map-assets-test-results.json').write_text(json.dumps(report, indent=2)+'\n')
    for check in checks[3:]:
        print('PASS', check, flush=True)


if __name__ == '__main__':
    main()
