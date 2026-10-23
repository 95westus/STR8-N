"""Assemble, save/reload, debug and execute source-cycle samples offline."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from test_rc1_source_flash import FlashMemory
from test_rc1_source_store import Harness, OUT, ROOT, packed

CS_ADDRS = (0x7F00, 0x7F20, 0x7F40, 0x7F60)


class SampleMemory(FlashMemory):
    def __init__(self, *a):
        super().__init__(*a); self.guest = False; self.io = []; self.led = []
        self.cancel_after = None

    def __getitem__(self, a):
        if isinstance(a, int) and self.guest and 0x200 <= self.cpu.pc < 0x3300:
            if a in CS_ADDRS: self.io.append(a)
            if 0x7FA0 <= a <= 0x7FA3: assert self.edu, 'EDU access on bare SXB'
        return super().__getitem__(a)

    def __setitem__(self, a, v):
        if self.guest and 0x200 <= self.cpu.pc < 0x3300:
            assert a not in CS_ADDRS and a not in (0x7FA1, 0x7FA2, 0x7FA3), ('Unexpected I/O write', a)
            if a == 0x7FA0:
                assert self.edu
                self.led.append(v & 255)
                if self.cancel_after == len(self.led): self.rx.append(3)
        super().__setitem__(a, v)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--cpu', choices=('65c02','65c816-e'), default='65c02')
    a = ap.parse_args(); checks = []; transcripts = []
    output = ROOT/'BUILD/rc1-dev-samples'; output.mkdir(exist_ok=True)
    manifest = json.loads((ROOT/'examples/source-cycle/patterns.json').read_text())
    for edu in (False, True):
        for slot in ('A', 'B'):
            h = Harness(a.cpu, slot, edu=edu, memory_factory=SampleMemory); h.command_limit = 15000000
            h.open(); initial_system = [bytes(b) for b in h.m.banks[1:]]
            for name, prefix in (('sxb-cs-patterns','CS'), ('edu-led31','E31')):
                path = ROOT/'examples/source-cycle'/(name+'.asm')
                lines = path.read_text().splitlines()
                h.command('NEW')
                # Exercise the documented PASTE entry, then real numbered edit.
                h.command('PASTE\r'+'\r'.join(lines)+'\r.', contains='ASM>')
                source = packed([(10*(i+1), text) for i,text in enumerate(lines)])
                assert h.source() == source
                h.command(f'SAVE FLASH {prefix}1', contains='Source saved')
                h.command('ASM', contains='OK ')
                n = int.from_bytes(h.m.ram[0x6302:0x6304], 'little')
                code = bytes(h.m.ram[0x200:0x200+n])
                # Publish exactly what the onboard assembler emitted.
                (output/f'{name}-{a.cpu}-{slot}-{int(edu)}.bin').write_bytes(code)
                export = h.command('S19'); (output/f'{name}-{a.cpu}-{slot}-{int(edu)}-export.txt').write_text(export)
                records = [s for s in export.splitlines() if re.fullmatch(r'S[019](?:[0-9A-F]{2}){4,}',s)]
                (output/(name+'.s19')).write_text('\n'.join(records)+'\n')
                h.command('QUIT','monitor')
                h.m.ram[0x7FA0] = 0xA5; h.m.ram[0x7FA1] = 0x34
                h.m.io.clear(); h.m.led.clear()
                if name == 'edu-led31' and not edu:
                    h.m.guest = True
                    result = h.command('G 0200', 'monitor', contains='E')
                    h.m.guest = False
                    assert not h.m.led and not h.m.io
                    checks.append(dict(cpu=a.cpu, slot=slot, edu=edu, sample=name,
                                       passed=True, absent_EDU_refused=True, code_bytes=n))
                else:
                    h.command('G 0200','debug')
                    entry_LED = h.m.ram[0x7FA0]
                    # Single-step one instruction at the initial BRK, then C.
                    stepped = h.command('S','debug'); assert '?' not in stepped
                    delay = code.find(bytes.fromhex('A2 FF A0 00 88')) if name == 'edu-led31' else code.find(bytes.fromhex('A2 40 A0 00'))
                    assert delay >= 0
                    delay += 0x200
                    original_step = h.cpu.step
                    def paced_step():
                        # Full table/control/ABI instructions execute. Reduce
                        # only dwell loop counts for the long animation runs.
                        if h.cpu.pc == delay:
                            h.cpu.x = 1; h.cpu.pc += 2; return
                        if name == 'sxb-cs-patterns' and h.cpu.pc == delay+2:
                            h.cpu.y = 1; h.cpu.pc += 2; return
                        return original_step()
                    h.cpu.step = paced_step
                    h.m.io.clear(); h.m.led.clear(); h.m.guest = True
                    h.command('C','debug'); h.m.guest = False
                    h.cpu.step = original_step
                    frames = [v for p in manifest[name]['patterns'] for v in p['frames']]
                    assert len(set(tuple(p['frames']) for p in manifest[name]['patterns'])) == manifest[name]['pattern_count']
                    if name == 'edu-led31':
                        assert h.m.led == frames+[entry_LED] and h.m.ram[0x7FA0] == entry_LED
                        assert not h.m.io
                    else:
                        expected = [address for mask in frames for bit,address in enumerate(CS_ADDRS) if mask & (1 << bit)]
                        assert h.m.io == expected and not h.m.led
                    h.command('C','monitor')
                    # Actual full dwell routine on one frame, without pacing.
                    saved_regs = {k:getattr(h.cpu,k) for k in ('pc','sp','p','a','x','y')}
                    saved_stack = bytes(h.m.ram[0x100:0x200])
                    h.cpu.pc = delay; h.cpu.stPushWord(0x1FF)
                    h.m.guest = True; before = len(h.m.io)
                    h.run(lambda: h.cpu.pc == 0x200, limit=2000000)
                    h.m.guest = False
                    if name == 'sxb-cs-patterns':
                        # Last mask $09: two selects per pulse, 64*256 pulses.
                        assert len(h.m.io)-before == 2*64*256
                    h.m.ram[0x100:0x200] = saved_stack
                    for k,v in saved_regs.items(): setattr(h.cpu,k,v)
                    # Re-enter and exercise cancellation with restoration.
                    if name == 'edu-led31':
                        h.command('G 0200','debug')
                        cancel_entry = h.m.ram[0x7FA0]
                        h.m.led.clear(); h.m.cancel_after = 3; h.cpu.step = paced_step; h.m.guest = True
                        h.command('C','debug'); h.m.guest = False; h.cpu.step = original_step
                        assert h.m.led == frames[:3]+[cancel_entry]
                        h.m.cancel_after = None; h.command('C','monitor')
                    checks.append(dict(cpu=a.cpu, slot=slot, edu=edu, sample=name,
                        passed=True, patterns=manifest[name]['pattern_count'], frames=len(frames),
                        code_bytes=n, packed_source_bytes=len(source), dwell_accelerated_for_full_animation=True,
                        one_full_dwell_instruction_test=True, entry_LED_restored=(name == 'edu-led31')))
                h.open(); h.command(f'LOAD FLASH {prefix}1', contains='Source loaded')
                assert h.source() == source
                h.command('ASM', contains='OK '); assert bytes(h.m.ram[0x200:0x200+n]) == code
                target = 'DWELL_OUTER = $FF' if name == 'edu-led31' else 'BURST_BATCHES = $40'
                edit = 'DWELL_OUTER = $80' if name == 'edu-led31' else 'BURST_BATCHES = $20'
                number = 10*(lines.index(target)+1)
                h.command(f'{number} {edit}')
                h.command(f'SAVE FLASH {prefix}2', contains='Source saved')
                h.command('ASM', contains='OK ')
                assert bytes(h.m.ram[0x200:0x200+n]) != code
                h.command(f'LOAD FLASH {prefix}2', contains='Source loaded')
                assert edit.encode() in h.source()
                h.command('ASM', contains='OK ')
                # A second entry verifies the edited image still debugs/returns.
                h.command('QUIT','monitor')
                if name != 'edu-led31' or edu:
                    h.command('G 0200','debug'); h.command('X','monitor')
                h.open()
                assert [bytes(b) for b in h.m.banks[1:]] == initial_system
                print('PASS',a.cpu,slot,'EDU' if edu else 'bare',name,n,'bytes',flush=True)
            transcripts.append(dict(slot=slot, edu=edu, commands=h.transcripts))
    report = dict(passed=True, board_access=False, cpu=a.cpu,
        firmware_sha256=hashlib.sha256((OUT/'firmware.bin').read_bytes()).hexdigest(),
        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), checks=checks,
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'examples/source-cycle').glob('*') if p.is_file()})
    (output/f'test-{a.cpu}.json').write_text(json.dumps(report, indent=2)+'\n')
    (output/f'transcripts-{a.cpu}.json').write_text(json.dumps(transcripts, indent=2)+'\n')


if __name__ == '__main__': main()
