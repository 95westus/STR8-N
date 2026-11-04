"""Offline combined-app integration plus the linked OIP1 regression suite."""
import argparse
import json
from pathlib import Path
import test_b14_tools as t
import test_mon_absent as ma

ROOT = Path(__file__).resolve().parents[2]
PROMPT = b'RAM KIT ? T I X Q> '
CONFIRM = b'Erase BOTH monitors: type ERASE then Enter> '
MON = b'\r\nB3> '
F_REC = b'REC> '


class Combined(t.InstallerMachine):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.i = self.sy['core/recovery-kit']

    def request(self, raw, body=None, port=1, ending=b'\r', result_ending=PROMPT):
        # The inherited method's default was bound to the old prompt at import.
        self.begin(port, ending)
        if body is None:
            return self.port_command(port, raw, result_ending)
        self.port_command(port, raw, t.PAYLOAD_READY)
        return self.port_command(port, body, result_ending)

    def port_command(self, port, data, ending=F_REC, timed=False):
        out=super().port_command(port,data,ending,timed)
        if ending==PROMPT:
            # FTDI completes the final prompt byte before ACIA. Reach the
            # text-input checkpoint before switching which console we watch.
            self.run(lambda:self.c.pc==self.w['V2W_GETC'])
        return out

    def load(self, via_f=True):
        data = (self.build/'payload/recovery-kit.bin').read_bytes()
        if via_f:
            self.recovery()
            self.command(b'C1\r')
            self.command(b'L\r', b'SEND BIN\r\n')
            self.command(data, PROMPT)
        else:
            self.m.ram[0x200:0x200+len(data)] = data
            self.c.pc = 0x200
            self.run(lambda: bytes(self.m.tx).endswith(PROMPT))
        assert self.m.banks[3][0x2000:0x4000] == b'\xff'*8192
        self.m.rx.clear()
        self.m.acia_rx.clear()
        self.run(lambda: self.c.pc == self.w['V2W_GETC'])


# Existing linked OIP1 tests exercise the combined binary and its actual new
# symbol addresses; unchanged stand-alone binaries are NOT used as substitutes.
t.InstallerMachine = Combined
t.PROMPT = PROMPT


def fresh(build, cpu, banks):
    h = Combined(build, cpu, banks=banks)
    h.accelerate_local_crc = False
    old = h.m
    memory = ma.Memory(banks, dual=True)
    memory.ram[:] = old.ram
    memory.bank, memory.cpu = 3, h.c
    memory.initial_counts = t.latest_record(banks)
    h.m = h.c.memory = memory
    return h


def raw_load(h, build, body=None, prompt=PROMPT):
    if body is None:
        body = (build/'payload/recovery-kit.bin').read_bytes()
    h.recovery()
    h.command(b'C3\r')
    h.command(b'L\r', b'SEND BIN\r\n')
    out=h.command(body, prompt)
    if prompt==PROMPT: h.run(lambda:h.c.pc==h.w['V2W_GETC'])
    return out


def integration(build, cpu, passed):
    info = json.loads((build/'mon-absent-build.json').read_text())
    plan = Path(info['source_plan'])
    original = [(plan/f'expected-b{n}.bin').read_bytes() for n in range(4)]
    absent = list(map(bytearray, original))
    absent[3][0x2000:0x4000] = b'\xff'*8192
    h = fresh(build, cpu, absent)
    raw_load(h, build)
    before = list(map(bytes, h.m.banks))
    for port in (1, 2):
        for ending in (b'\r', b'\n', b'\r\n'):
            out = h.port_command(port, b'?'+ending, PROMPT)
            for text in (b'?  Help', b'T  Restore', b'I  OIP1', b'X  Erase', b'Q  Restart', b'protects B3:A/B/C/D/F'):
                assert text in out, (text, out)
    assert not h.m.events and list(map(bytes, h.m.banks)) == before
    passed(cpu, 'F-raw-load-MON-absent-help-both-consoles-CR-LF-CRLF', comparisons=6)
    for ending in (b'\r', b'\n', b'\r\n'):
        h.command(b'x'+ending, CONFIRM)
        out = h.command(b'NO'+ending, PROMPT)
        assert b'CANCELED: MON erase' in out and not h.m.events
    for command in (b'R\r', b'D\r', b'V\r', b'TX\r', b'BAD\r'):
        assert b'REFUSED: command; ? for help' in h.command(command, PROMPT)
    assert not h.m.events
    passed(cpu, 'erase-confirmation-cancel-and-invalid-commands-no-writes', cancellations=3, invalid_commands=5)
    # Use OIP read before T, so its mutable header/CRC has changed. T must
    # recheck code/images without rejecting those legitimate state changes.
    out = h.request(t.frame(op=0))
    sector = bytes(h.m.banks[0][:4096])
    assert out == t.READ_READY+sector+t.crc(sector).to_bytes(2,'little')+t.READ_DONE+PROMPT
    assert b'Help' in h.command(b'?\r', PROMPT)
    start = len(h.m.tx)
    h.m.rx.extend(b't\r\n')
    h.run(lambda: len(h.m.tx)>start and bytes(h.m.tx).endswith(MON), limit=12000000)
    assert b'MON KIT DONE' in h.m.tx[start:] and b'2.0proto b14' in h.m.tx[start:]
    assert bytes(h.m.banks[3][0x2000:0x4000]) == original[3][0x2000:0x4000]
    ma.preserved(original, h.m.banks)
    for addr in (0xa000, 0xb000):
        events = [e for e in h.m.events if e[2]&0xf000==addr]
        assert events[0][0]=='erase' and events[-1] == ('program',3,addr+31,0)
    trace = list(h.m.events)
    restored = list(map(bytes, h.m.banks))
    passed(cpu, 'I-read-then-T-restores-both-commit-last-default-B-boot', mutations=len(trace))
    raw_load(h, build)
    before_events = list(h.m.events)
    start = len(h.m.tx)
    h.m.rx.extend(b'T\n')
    h.run(lambda: len(h.m.tx)>start and bytes(h.m.tx).endswith(MON), limit=12000000)
    assert before_events == h.m.events
    passed(cpu, 'identical-T-retry-no-erase-or-wear-reservation')
    raw_load(h, build)
    h.command(b'X\r\n', CONFIRM)
    out = h.command(b'ERASE\r\n', F_REC)
    assert b'MON KIT DONE' in out
    assert bytes(h.m.banks[3][0x2000:0x4000]) == b'\xff'*8192
    ma.preserved(restored,h.m.banks)
    erased = list(map(bytes,h.m.banks))
    raw_load(h,build)
    n = len(h.m.events)
    h.command(b'X\r',CONFIRM)
    h.command(b'ERASE\r',F_REC)
    assert len(h.m.events)==n
    passed(cpu,'confirmed-X-exact-preimages-and-already-blank-noop')
    raw_load(h,build)
    n = len(h.m.events)
    h.command(b'q\r',F_REC)
    assert len(h.m.events)==n
    passed(cpu,'Q-restarts-through-F-no-writes')
    # Corrupt a byte in either embedded slot or the app after an OIP read;
    # every mutation entry must revalidate before journal reservation.
    for entry in ('I','T','X'):
        z=fresh(build,cpu,absent)
        raw_load(z,build)
        z.request(t.frame(op=0))
        z.m.ram[z.i['MA_IMAGE_A']+100] ^= 1
        if entry=='X':
            z.command(b'X\r',CONFIRM)
            out=z.command(b'ERASE\r',F_REC)
        else:
            out=z.command(entry.encode()+b'\r',F_REC)
        assert b'MON KIT REFUSED/FAILED' in out and not z.m.events
    passed(cpu,'recheck-immutable-app-and-slot-integrity-before-I-T-X', entries=3)
    changed=list(map(bytearray,original));changed[3][0x2010]^=1
    z=fresh(build,cpu,changed);raw_load(z,build)
    z.command(b'X\r',CONFIRM)
    assert b'REFUSED/FAILED' in z.command(b'ERASE\r',F_REC) and not z.m.events
    passed(cpu,'unexpected-X-preimage-refuses-before-journal-mutation')
    # Real NOR mutation prefixes from T: relaunch through F, then complete T
    # at representative journal, erase, early/late program and slot commits.
    cuts={1,len(trace)}
    cuts.update(i+1 for i,e in enumerate(trace) if e[0]=='erase' or e[2] in (0xa000,0xb000,0xa01f,0xb01f,0xafff,0xbfff)
                or e[0]=='program' and 0xc000<=e[2]<0xe000 and e[2]&255==255)
    for cut in sorted(cuts):
        banks=list(map(bytearray,absent))
        for kind,bank,address,value in trace[:cut]:
            off=address-0x8000
            if kind=='erase': banks[bank][off:off+4096]=b'\xff'*4096
            else: banks[bank][off]=value
        ma.preserved(absent,banks)
        z=fresh(build,cpu,banks);raw_load(z,build)
        start=len(z.m.tx);z.m.rx.extend(b'T\r')
        z.run(lambda:len(z.m.tx)>start and bytes(z.m.tx).endswith(MON),limit=12000000)
        assert bytes(z.m.banks[3][0x2000:0x4000])==original[3][0x2000:0x4000]
        ma.preserved(absent,z.m.banks)
    passed(cpu,'MON-restore-interruption-prefixes-F-reload-and-T-completes',prefixes=len(cuts))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--cpu',choices=('65c02','65c816-e'),required=True)
    p.add_argument('--mode',choices=('integration','opaque'),default='integration')
    x=p.parse_args();build=x.build.resolve();cases=[]
    t.base.GENERATION=json.loads((build/'prototype-report.json').read_text())['experimental_generation']
    from prepare_monitor_size import protected, ATTEMPTS
    marker_paths=[ROOT/f'output/qualification/device-operations/{b}.json' for b in ('2512','2604','2609')]
    marker_paths.append(ROOT/'output/qualification/serial-coordination/owner.json')
    def guard():
        return dict(sources=protected(),boards_and_lease={str(p):t.sha(p.read_bytes()) for p in marker_paths})
    initial_guard=guard()
    def passed(cpu,case,**kw):
        cases.append(dict(cpu=cpu,case=case,passed=True,**kw))
        print('PASS',cpu,case,flush=True)
    result=build/f'recovery-kit-{x.mode}-{x.cpu}.json'
    bindings=dict(app_sha256=t.sha((build/'payload/recovery-kit.bin').read_bytes()),
                  symbols_sha256=t.sha((build/'symbols.json').read_bytes()),
                  checker_sha256=t.sha(Path(__file__).read_bytes()),
                  reused_checker_sha256=t.sha(Path(t.__file__).read_bytes()),
                  original_OIP_checker_sha256=t.sha((Path(__file__).parent/'test_opaque_installer.py').read_bytes()))
    try:
        if x.mode=='integration': integration(build,x.cpu,passed)
        else:
            h=t.patterned_machine(build,x.cpu,via_f=True)
            assert not h.m.events
            passed(x.cpu,'F-load-combined-app-with-MON-absent')
            t.protocol_tests(build,x.cpu,passed)
            t.interruption_tests(build,x.cpu,passed)
        assert guard()==initial_guard, 'Protected source/board markers/lease changed'
        assert not ATTEMPTS
        t.base.save(result,dict(passed=True,hardware=False,serial_access=False,failures=0,checks=len(cases),cases=cases,
                               mutation_prefixes=sum(c.get('prefixes',0) for c in cases),**bindings,
                               device_or_network_attempts=ATTEMPTS,protected_sources_and_all_three_board_markers_unchanged=True,
                               boards_and_lease_sha256=initial_guard['boards_and_lease'],
                               limitations=['CPU/NOR model only; no physical power interruption or NMI qualification']))
    except Exception as e:
        t.base.save(result,dict(passed=False,hardware=False,failures=1,checks=len(cases),cases=cases,error=repr(e),**bindings))
        raise


if __name__=='__main__': main()
