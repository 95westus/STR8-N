"""Check named payloads, unchanged commands, AP loaders and executed banners."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

from build_named_components import BASE, ROOT, symbols

OUT = ROOT/'BUILD/str8n-components-naming-r1'
crc = lambda data: binascii.crc_hqx(data, 65535)


class NamingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((OUT/'COMPONENTS.json').read_text())
        cls.artifacts = cls.manifest['artifacts']
        cls.catalog = json.loads((OUT/'NATIVE-COMPONENTS.json').read_text())

    def artifact(self, name, ram=False):
        matches = [f for f,v in self.artifacts.items() if v['component'] == name
                   and (not ram or v.get('load') == '0200')]
        self.assertEqual(len(matches), 1, matches)
        return (OUT/matches[0]).read_bytes()

    def pair(self, role, cpu):
        targets = [i for i in self.catalog['targets'] if i['bank']==0
                   and int(i['address'],16) in ((0xa000,0xb000) if role=='ASM' else (0xc000,0xd000))]
        return b''.join((OUT/(i['variants'][cpu]['file'] if 'variants' in i else i['file'])).read_bytes()
                        for i in targets)

    def test_artifact_paths_and_hashes(self):
        for file, info in self.artifacts.items():
            self.assertRegex(Path(file).name, r'^str8n-(f-|mon-|util-|dev-)[a-z0-9.-]+\.bin$')
            data = (OUT/file).read_bytes()
            self.assertEqual(len(data), info['bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), info['sha256'])
        for item in self.catalog['targets']+self.catalog['retirement_targets']:
            for info in item.get('variants', {'single': item}).values():
                self.assertEqual(hashlib.sha256((OUT/info['file']).read_bytes()).hexdigest(), info['sha256'])

    def test_packaged_launchers_run_without_ports(self):
        for entry, title in (('str8n-terminal.py','STR8-N Terminal'),
                             ('str8n-util-memory.py','STR8-N UTIL MEMORY')):
            result = subprocess.run([sys.executable, '-B', str(OUT/entry), '--version'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn(title,result.stdout)
            self.assertIn('Copyright (c) 2026 95west.us/wlp1963; MIT',result.stdout)

    def test_foundation_frozen_and_monitor_notice_valid(self):
        self.assertEqual(self.artifact('F'), (BASE/'F.bin').read_bytes())
        for slot in ('a', 'b'):
            file = next(f for f,v in self.artifacts.items() if v['component']=='MON' and 'slot-'+slot in f)
            body = (OUT/file).read_bytes()
            self.assertIn(b'(c)2026 95west.us/wlp1963; MIT',body)
            self.assertEqual(int.from_bytes(body[18:20],'little'),crc(body[:18]+body[32:]))

    def test_names_and_short_prompts(self):
        for name in ('CONFIG','FLASH','MAINT','ASM','DBG'):
            self.assertIn(('STR8-N '+('DEV ' if name in ('ASM','DBG') else 'UTIL ')+name).encode(),
                          self.artifact(name, True))
        for component, prompt in (('CONFIG',b'RAM CONFIG ? B C I W Q> '),('FLASH',b'FLASH/MAINT> '),
                                  ('ASM',b'ASM> '),('DBG',b'DBG> ')):
            self.assertIn(prompt, self.artifact(component, True))
        source = json.loads((OUT/'product-names.json').read_text())
        for name in ('CONFIG','FLASH','CLOCK','MAINT','MEMORY','ASM','DBG'):
            self.assertEqual(source['components'][name]['command'], name)
        presets = json.loads((OUT/'preset-assets.json').read_text())
        for key in ('MAP','CONFIG','OPAQUE','DEMO'):
            self.assertTrue((OUT/presets[key]).is_file())
            self.assertTrue(Path(presets[key]).name.startswith('str8n-util-'+key.lower()+'-'))
        self.assertIn("preset-assets.json", (OUT/'terminal/nf_console.py').read_text())

    def test_clock_and_maint_checksums(self):
        clock = b''.join((OUT/f).read_bytes() for f,v in self.artifacts.items() if v['component']=='CLOCK')
        self.assertEqual(crc(clock), 0)
        self.assertIn(b'STR8-N UTIL CLOCK 1.10\r\n(c)2026 95west.us/wlp1963; MIT\r\n\0', clock)
        sy = symbols(ROOT/'BUILD/loadable-maint-full-r2/maint-adapter.map')
        maint = self.artifact('MAINT', True)
        self.assertEqual(crc(maint[0x1e00:sy['MA_IMM_END']-0x200]), 0)
        wb = b''.join((OUT/f).read_bytes() for f,v in self.artifacts.items()
                      if v['component']=='SERVICES' and v.get('bank')==2
                      and v.get('address') in ('8000','9000'))
        self.assertEqual(crc(wb[0x300:0x1f00]), 0)
        self.assertIn(b'STR8-N UTIL MAINT WB2 gE', wb)
        self.assertIn(b'WORKBENCH> ', wb)

    def test_app_checksums_ids_and_paired_provider(self):
        for cpu in ('65c02','65c816e'):
            for role in ('ASM','DBG'):
                image = self.pair(role, cpu)
                self.assertEqual(image[:8], b'AP\x02 PR05')
                self.assertEqual(image[16:16+len(role)], role.encode())
                self.assertEqual(int.from_bytes(image[28:30], 'little'), crc(image[:28]))
                size = int.from_bytes(image[8:10], 'little')
                self.assertEqual(int.from_bytes(image[30:32], 'little'), crc(image[32:size]))
                if role == 'DBG':
                    original = (BASE/'native/payload/B0-D000.bin').read_bytes()
                    self.assertEqual(image[0x1800:], original[0x800:])
                    self.assertIn(b'STR8-N DEV DBG g2', image)
                    self.assertIn(b'Copyright (c) 2026 95west.us/wlp1963; MIT',image)

    def run_print(self, memory, pc, stop, limit=100000, print_addresses=(0x7e6d,)):
        cpu = MPU(memory=memory, pc=pc)
        cpu.pc = pc
        text = bytearray()
        for _ in range(limit):
            if stop(cpu, text):
                return bytes(text)
            if cpu.pc in print_addresses:
                text.append(cpu.a)
                cpu.pc = (cpu.stPopWord()+1)&65535
            else:
                cpu.step()
        self.fail('Banner execution instruction limit at '+hex(cpu.pc))

    def test_executed_dbg_banner_preserves_original_entry(self):
        packet = self.artifact('DBG', True)
        original = (BASE/'developer/DBG-RAM.bin').read_bytes()
        entry = int.from_bytes(original[11:13], 'little')
        memory = [0]*65536
        memory[0x200:0x200+len(packet)] = packet
        printed = self.run_print(memory, 0x200, lambda c,t: c.pc==entry)
        self.assertEqual(printed, b'STR8-N DEV DBG g2\r\nCopyright (c) 2026 95west.us/wlp1963; MIT\r\n')
        self.assertEqual(memory[0x707a:0x707c], [0, 0x10])
        self.assertEqual(packet[0x5d00:], original[0x5d00:])

    def test_executed_clock_banner(self):
        clock = b''.join((OUT/f).read_bytes() for f,v in self.artifacts.items() if v['component']=='CLOCK')
        count = int.from_bytes(clock[8:10], 'little')
        memory = [0]*65536
        memory[0x2000:0x2000+count] = clock[32:32+count]
        memory[0x7e60:0x7e64] = b'RA\x01\x0d'
        printed = self.run_print(memory, 0x2006, lambda c,t: t.count(b'\n')==2)
        self.assertEqual(printed, b'STR8-N UTIL CLOCK 1.10\r\n(c)2026 95west.us/wlp1963; MIT\r\n')

    def test_executed_flash_startup_identity(self):
        packet = self.artifact('FLASH', True)
        sy = symbols(ROOT/'BUILD/flash-status-correction-r4/board-tool.map')
        memory = [0]*65536
        memory[0x200:0x200+len(packet)] = packet
        printed = self.run_print(memory, sy['CONFIG_START'], lambda c,t: t.endswith(b'\r\n'),
                                 print_addresses=(sy['V2W_PUTC'],))
        self.assertTrue(printed.startswith(b'STR8-N UTIL FLASH g2'), printed)

    def test_expanded_asm_name(self):
        sys.path.insert(0, str(ROOT/'release/str8nf-v0.2.0/tools'))
        from build_bank_features import expand
        sy = symbols(OUT/'asm-65c02/asm.map')
        image = self.pair('ASM','65c02')
        packed = image[sy['DT_PACKED']-0xa000:sy['DT_PACKED_END']-0xa000]
        ram = self.artifact('ASM', True)
        self.assertEqual(expand(packed,len(ram)-0x3e00), ram[0x3e00:])

    def test_executed_flash_version_copyright(self):
        packet = self.artifact('FLASH',True)
        sy = symbols(ROOT/'BUILD/flash-status-correction-r4/board-tool.map')
        memory = [0]*65536
        memory[0x200:0x200+len(packet)] = packet
        pc = sy['FT_VERSION_COMMAND']
        for at in range(pc,pc+40):
            if memory[at]==0xa2 and memory[at+2]==0xa0:
                pc=at
                break
        printed = self.run_print(memory,pc,lambda c,t:t.count(b'\n')==2,
                                 print_addresses=(sy['V2W_PUTC'],))
        self.assertIn(b'Copyright (c) 2026 95west.us/wlp1963; MIT',printed)

    def test_helper_banner_restores_original_self_checked_bytes(self):
        original = (BASE/'foundation/firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
        packet = self.artifact('OPAQUE', True)
        memory = [0]*65536
        memory[0x200:0x200+len(packet)] = packet
        printed = self.run_print(memory, 0x200, lambda c,t: c.pc==0x200 and bool(t))
        self.assertEqual(printed, b'STR8-N UTIL OPAQUE\r\nCopyright (c) 2026 95west.us/wlp1963; MIT\r\n')
        self.assertEqual(bytes(memory[0x200:0x200+len(original)]), original)

    def test_notices_in_component_binaries_and_license(self):
        for name in ('CONFIG','FLASH','MAINT','ASM','DBG','OPAQUE','MAP','READBACK','DEMO','MEMORY'):
            self.assertIn(b'Copyright (c) 2026 95west.us/wlp1963; MIT',self.artifact(name,True))
        self.assertEqual((OUT/'LICENSE').read_bytes(),(ROOT/'LICENSE').read_bytes())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=OUT)
    parser.add_argument('--cpu', choices=('65c02','65c816-e'), default='65c02')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    OUT = args.build
    sys.path.insert(0, str(ROOT/'tmp/migration-python'))
    if args.cpu == '65c816-e':
        sys.path.insert(0, str(ROOT/'tmp/p1-clean/BUILD/test-deps-816'))
        from py65816.devices.mpu65c816 import MPU
    else:
        from py65.devices.mpu65c02 import MPU
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NamingTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if args.report:
        args.report.write_text(json.dumps(dict(passed=result.wasSuccessful(), tests=result.testsRun,
            cpu=args.cpu, hardware_access=False, commands_changed=False), indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
