"""Unified source/profile integration tests. Synthetic data; no serial access."""
import argparse
import binascii
import json
from pathlib import Path
from test_boot_and_opaque import Machine, REC, CFG, crc, latest

ROOT = Path(__file__).resolve().parents[1]
MON = b'\r\nB3> '
MAINT = b'MAINT RO> '
FLASH = b'FLASH> '
SERVICE = b'RAM SERVICE> '


class System(Machine):
    def __init__(self, build, cpu, board):
        super().__init__(build, cpu, mask=15 if board == '2512' else 0)
        self.sy = json.loads((build/'system-symbols.json').read_text())
        profiles = json.loads((ROOT/'profiles.json').read_text())
        self.profile = profiles['boards'][board]
        for target, name in self.profile['installed_components'].items():
            bank, sector = int(target[1]), int(target[3], 16)
            start = (sector-8)*4096
            self.m.banks[bank][start:start+4096] = (build/'payload'/name).read_bytes()
        self.active = None
        original = self.c.step
        def step():
            sy = self.sy.get(self.active, {})
            name = {'maint': 'MA_CRC_BYTE', 'vx1': 'VX_CRC_BYTE',
                    'flash-8000': 'OI_CRC_BYTE'}.get(self.active)
            if name and self.c.pc == sy.get(name):
                address = 0xd4 if self.active == 'vx1' else sy['MA_CRC' if self.active == 'maint' else 'OI_CRC']
                value = binascii.crc_hqx(bytes((self.c.a,)), int.from_bytes(self.m.ram[address:address+2], 'little'))
                self.m.ram[address:address+2] = value.to_bytes(2, 'little')
                self.c.x = 0
                self.c.pc = (self.c.stPopWord()+1)&65535
                return self.c
            return original()
        self.c.step = step

    def run(self, stop, limit=12000000):
        return super().run(stop, limit)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    build, out = args.build.resolve(), args.out.resolve()
    assert not out.exists()
    out.mkdir(parents=True)
    cases = []
    def passed(cpu, board, name):
        cases.append(dict(passed=True, cpu=cpu, board=board, case=name))
        (out/'progress.json').write_text(json.dumps(cases, indent=2)+'\n')
        print('PASS', cpu, board, name, flush=True)
    for cpu in ('65c02', '65c816-e'):
        for board in ('2512', '2609'):
            h = System(build, cpu, board)
            before = list(map(bytes, h.m.banks))
            h.recovery()
            h.command(b'C1\r', REC)
            h.load('STR8N-F-CONFIG-RAM.bin', CFG)
            text = h.command(b'B\r', CFG)
            assert b'DEFAULT=S\r\n' in text
            assert (b'B0 ON  ENTRY=8000' if board == '2512' else b'B0 OFF ENTRY=8000') in text
            assert b'Save default' in h.command(b'?\r', CFG)
            assert b'UNKNOWN HISTORY' in h.command(b'W\r', CFG)
            assert not h.m.events and list(map(bytes, h.m.banks)) == before
            passed(cpu, board, 'same-CONFIG-inspects-profile-without-changing-policy-or-wear')

            h.active = 'maint'
            h.load('STR8N-F-MAINT-RO-RAM.bin', MAINT)
            assert b'No write, erase' in h.command(b'?\r', MAINT)
            roles = h.command(b'M\r', MAINT)
            assert b'WDC-BACKUP' not in roles and b'VX1-SLOT' not in roles
            assert b'OWNER IMAGE PRESERVE' in roles and b'OPTIONAL OWNER IMG' in roles
            assert b'BUFFER LOADED' in h.command(b'R 0 8000 800F\r', MAINT)
            assert h.m.ram[0x5000:0x5010] == before[0][:16]
            assert f'CRC16={crc(before[0][:16]):04X}'.encode() in h.command(b'K\r', MAINT)
            assert b'MATCH' in h.command(b'V 0 8000 800F 0 8000\r', MAINT)
            assert b'REFUSED' in h.command(b'F 9000 00\r', MAINT)
            assert not h.m.events and list(map(bytes, h.m.banks)) == before
            passed(cpu, board, 'same-MAINT-map-read-CRC-compare-and-write-refusal')

            h.active = None
            h.load('STR8N-F-READBACK-RAM.bin', SERVICE)
            owner = bytes(h.m.ram[0x200:0x6500])
            zp = bytes(h.m.ram[:0xe0])
            packet = h.command(b'F\x00', SERVICE)
            assert packet[:-len(SERVICE)-2] == before[0]
            assert int.from_bytes(packet[-len(SERVICE)-2:-len(SERVICE)], 'little') == crc(before[0])
            replacement = bytes((n*17+5)&255 for n in range(0x6300))
            h.command(b'W'+replacement+crc(replacement).to_bytes(2, 'little'), SERVICE)
            packet = h.command(b'M', SERVICE)
            assert packet[:0x6300] == replacement
            assert int.from_bytes(packet[0x6300:0x6302], 'little') == crc(replacement)
            assert h.command(b'Z', SERVICE)[:0xe0] == zp
            assert not h.m.events and list(map(bytes, h.m.banks)) == before
            passed(cpu, board, 'same-binary-readback-and-fixed-range-RAM-restore-with-CRC')

            h.command(b'Q', REC)
            if board == '2512':
                h.active = 'flash-8000'
                h.load('STR8N-F-FLASH-8000-RAM.bin', FLASH)
                assert h.m.ram[0x7fa0] == 1
                assert b'OK: RAM' in h.command(b'M 2000 41 42 03\r', FLASH)
                assert h.m.ram[0x2000:0x2003] == b'AB\x03'
                assert b'REFUSED' in h.command(b'I 8000\r', FLASH)
                assert b'YES' in h.command(b'F 9000 00\r', b'type YES> ')
                assert b'verified sector' in h.command(b'YES\r', FLASH)
                assert h.m.banks[0][0x1000] == 0 and h.m.ram[0x7fa0] == 1
                h.command(b'I 9000\r', b'type YES> ')
                assert b'verified sector' in h.command(b'YES\r', FLASH)
                assert h.m.banks[0][0x1000:0x2000] == b'\xff'*4096 and h.m.ram[0x7fa0] == 1
                h.active = None
                assert b'2.0proto b15' in h.command(b'Q\r', MON)
                assert h.m.banks[0][:4096] == before[0][:4096]
                assert list(map(bytes, h.m.banks[1:3])) == before[1:3]
                assert bytes(h.m.banks[3][:0x4000]) == before[3][:0x4000]
                assert bytes(h.m.banks[3][0x6000:]) == before[3][0x6000:]
                assert latest(h.m.banks)[7:8] == b'S'
                passed(cpu, board, 'FLASH-RAM-edit-real-program-erase-LED-cleanup-and-Q-to-MON')
            else:
                h.active = 'vx1'
                for slot in (b'A', b'B'):
                    h.command(slot+b'\r', MON)
                    version = h.command(b'VERSION\r', MON)
                    assert b'STR8-N VERSION / VX1' in version
                    assert b'Running MON: '+slot in version
                    assert b'legacy CAPS=01/17' in h.command(b'CAPS\r', MON)
                    (out/(cpu+'-'+slot.decode()+'-VERSION.txt')).write_bytes(version)
                    h.command(b'J3\r', b'S=Recovery  A/B=Monitor  0-3=Bank\r\n')
                    h.command(b'S', REC)
                h.active = None
                # Missing optional ES1 refuses without a peripheral init/read.
                h.m.banks[3][:4096] = b'\xff'*4096
                h.load('STR8N-F-EDU-SRAM-RAM.bin', REC)
                assert b'ES1' in bytes(h.m.tx[-200:])
                assert not h.m.events
                assert bytes(h.m.banks[0]) == before[0]
                assert bytes(h.m.banks[3][0x2000:]) == before[3][0x2000:]
                passed(cpu, board, 'VX1-both-MONs-and-optional-EDU-unavailable-path')
    (out/'qualification.json').write_text(json.dumps(dict(passed=True, checks=len(cases),
        hardware=False, serial_access=False, cases=cases,
        limits=['Synthetic banks and wear; both CPU models and both layouts',
                'Local CRC shortcuts for previously qualified identical routines',
                'No live serial, physical timing, power-cut or new EDU electrical claim']), indent=2)+'\n')
    print('PASS', len(cases), 'unified integration groups; no device access', flush=True)


if __name__ == '__main__':
    main()
