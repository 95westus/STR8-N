"""Execute the extended CONFIG through b14 raw L on both CPUs and consoles."""
import argparse
import json
from pathlib import Path

from test_b14_core import load_core
from test_b14_raw import start, feed

PROMPT = b'RAM CONFIG ? B C I W Q> '
CPUS = ('65c02', '65c816-e')
core, _ = load_core()
core.GENERATION = 0x8000000e


def latest(banks):
    rows = []
    for address in range(0x4000, 0x6000, 256):
        r = bytes(banks[3][address:address+256])
        if (r[:6] == b'SNBT\x01\x20' and r[255] == 0
                and core.crc(r[:30]) == int.from_bytes(r[30:32], 'little')
                and core.crc(r[:252]) == int.from_bytes(r[252:254], 'little')):
            rows.append(r)
    return max(rows, key=lambda r:int.from_bytes(r[8:12], 'little')) if rows else None


def load(build, cpu, port=1, rows=(), banks=None):
    h = core.Machine(build, cpu, rows, opaque=True)
    if banks is not None:
        h.m.banks[:] = [bytearray(b) for b in banks]
    h.recovery()
    h.run(lambda:h.c.pc == h.b['BOOT_B08_READ_LINE'])
    before_ram = bytes(h.m.ram)
    start(h, port)
    data = (build/'payload/ram-config-offline.bin').read_bytes()
    feed(h, port, data)
    h.run(lambda:bytes(h.m.tx).endswith(PROMPT) and bytes(h.m.acia_tx).endswith(PROMPT))
    assert bytes(h.m.ram[0x200+len(data):0x6700]) == before_ram[0x200+len(data):0x6700]
    assert bytes(h.m.ram[:0xe0]) == before_ram[:0xe0]
    assert not h.m.events
    assert h.m.banks[3][0x2000:0x4000] == b'\xff'*8192, 'Tests require MON A/B absent'
    h.original_ram = before_ram
    h.loaded_end = 0x200+len(data)
    h.initial_banks = tuple(map(bytes, h.m.banks))
    return h


def command(h, port, line, ending=b'\r'):
    return h.port_command(port, line+ending, PROMPT)


def preserved(h):
    assert bytes(h.m.ram[:0xe0]) == h.original_ram[:0xe0]
    assert bytes(h.m.ram[h.loaded_end:0x6700]) == h.original_ram[h.loaded_end:0x6700]
    assert bytes(h.m.ram[0x6800:0x7800]) == h.original_ram[0x6800:0x7800]
    for n in range(4):
        for offset in range(0, 32768, 4096):
            if n == 3 and offset in (0x4000, 0x5000):
                continue
            assert bytes(h.m.banks[n][offset:offset+4096]) == h.initial_banks[n][offset:offset+4096]


def unchanged_fields(before, after, changed=()):
    ignore = set(changed) | set(range(8, 12)) | {30, 31, 252, 253}
    assert all(before[n] == after[n] for n in range(256) if n not in ignore)


def reboot_reader(build, cpu, banks):
    h = core.Machine(build, cpu, opaque=True)
    h.m.banks[:] = [bytearray(b) for b in banks]
    assert h.call(h.b['BOOT_READ_RECORD'])
    assert bytes(h.m.ram[0x6700:0x6720]) == latest(banks)[:32]
    assert not h.m.events
    return h


def interface_tests(build, cpu, port, passed):
    h = load(build, cpu, port)
    help_text = command(h, port, b'?')
    assert b'B bank entry' in help_text and b'B3 excludes C000/D000' in help_text
    assert b'Install the opaque image separately. B/C only save boot settings.\r\n' in help_text
    assert help_text.count(b'B bank entry') == 1 and not h.m.events
    assert b'REFUSED: journal/target' in command(h, port, b'B')
    assert b'OK\r\n' in command(h, port, b'I')
    assert b'UNKNOWN HISTORY' in command(h, port, b'W')
    initial = latest(h.m.banks)
    assert initial[7] == ord('S') and initial[13] == 0
    n = len(h.m.events)
    show = command(h, port, b'B')
    assert b'DEFAULT=S\r\n' in show
    for bank in range(4):
        assert f'B{bank} OFF ENTRY=8000\r\n'.encode() in show
    assert len(h.m.events) == n
    assert b'REFUSED: journal/target' in command(h, port, b'C 0')
    assert len(h.m.events) == n
    for ending, line, bank, page in ((b'\r', b'b 0 a000', 0, 10),
                                     (b'\n', b'B 1 9000', 1, 9),
                                     (b'\r\n', b'B 2 E000', 2, 14),
                                     (b'\r', b'B 3 8000', 3, 8)):
        before = latest(h.m.banks)
        assert b'OK\r\n' in command(h, port, line, ending)
        after = latest(h.m.banks)
        assert after[13] == before[13] | (1 << bank) and after[14+bank] == page
        assert after[7] == before[7]
        unchanged_fields(before, after, {13, 14+bank})
    before = latest(h.m.banks)
    assert b'OK\r\n' in command(h, port, b'c 0')
    after = latest(h.m.banks)
    assert after[7] == ord('0')
    unchanged_fields(before, after, {7})
    n = len(h.m.events)
    show = command(h, port, b'C')
    assert b'DEFAULT=0\r\n' in show and b'B0 ON  ENTRY=A000\r\n' in show
    assert len(h.m.events) == n
    assert b'OK\r\n' in command(h, port, b'B 0 A000')
    assert len(h.m.events) == n and latest(h.m.banks) == after
    assert b'REFUSED: journal/target' in command(h, port, b'I')
    assert len(h.m.events) == n
    preserved(h)
    reboot_reader(build, cpu, h.m.banks)
    # Q must perform the actual saved opaque handoff, without either MON.
    (h.m.rx if port == 1 else h.m.acia_rx).extend(b'Q\r')
    h.run(lambda:h.m.bank == 0 and h.c.pc == 0xa000)
    assert b'Boot : 6 5 4 3 2 1 0' in (h.m.tx if port == 1 else h.m.acia_tx)
    assert len(h.m.events) == n
    passed(cpu, port, 'raw-L-help-init-show-enable-default-noop-preservation-Q-opaque-boot')


def refusal_tests(build, cpu, port, passed):
    h = load(build, cpu, port, [(0xc000, core.record(mask=0))])
    before = tuple(map(bytes, h.m.banks))
    bad = (b'', b'?', b'B 4 8000', b'B -1 8000', b'B A 8000', b'B 00 8000',
           b'B 0', b'B 0 ', b'B 0 800', b'B 0 08000', b'B 0 8001',
           b'B 0 8100', b'B 0 7000', b'B 0 F000', b'B 0 0x8000', b'B 0 $8000',
           b'B 0 G000', b'B 3 C000', b'B 3 D000', b'B 0 8000 X', b'B 0 8000 ',
           b'B 0  8000', b'C 0', b'C X', b'C A', b'C B', b'C 00', b'C 0 X',
           b'I X', b'W X', b'Q X', b'? X', b'X', b'B 0 8000\x01',
           b'B 0 8000\xff', b'B 0 8000'+b'X'*40, b'B 0 8000\x03', b'B 0 8000\x1b')
    for line in bad:
        out = command(h, port, line)
        if line not in (b'', b'?'):
            assert b'REFUSED' in out, (cpu, port, line, out)
        assert tuple(map(bytes, h.m.banks)) == before and not h.m.events, line
    preserved(h)
    passed(cpu, port, 'invalid-disabled-malformed-cancelled-commands-never-mutate', commands=len(bad))


def bank_entries(build, cpu, passed):
    for bank in range(4):
        for page in range(8, 15):
            if bank == 3 and page in (12, 13):
                continue
            h = load(build, cpu, rows=[(0xc000, core.record(mask=0))])
            assert b'OK' in command(h, 1, f'B {bank} {page:X}000'.encode())
            assert b'OK' in command(h, 1, f'C {bank}'.encode())
            r = latest(h.m.banks)
            assert r[13] == 1 << bank and r[14+bank] == page and r[7] == ord('0')+bank
            reboot = reboot_reader(build, cpu, h.m.banks)
            reboot.c.pc = reboot.b['BOOT_START_CHOICES']
            reboot.run(lambda:reboot.m.bank == bank and reboot.c.pc == page*4096)
            assert not reboot.m.events
            preserved(h)
    passed(cpu, 1, 'every-admitted-bank-entry-persists-and-boots', entries=26)


def journal_refusals(build, cpu, passed):
    damaged = bytearray(core.record(mask=0)); damaged[0x50] ^= 1
    duplicate = bytearray(core.record(mask=0)); duplicate[0x50] ^= 1
    maximum = core.record(seq=0xffffffff, mask=0)
    exhausted = [(0xcf00, core.record(seq=15, mask=0)),
                 (0xc000, core.record(seq=1, mask=0)),
                 (0xd000, core.record(seq=2, mask=0))]
    counts = [1]*32; counts[29] = 0xffffff
    saturated = [(0xce00, core.record(seq=15, mask=0, counts=counts)),
                 (0xd000, core.record(seq=1, mask=0))]
    cases = [('absent', []), ('body-CRC', [(0xc000, bytes(damaged))]),
             ('conflicting-history', [(0xc000, core.record(mask=0)), (0xc100, bytes(duplicate))]),
             ('sequence-exhausted', [(0xc000, maximum)]),
             ('reservation-exhausted', exhausted), ('wear-saturated', saturated)]
    for name, rows in cases:
        h = load(build, cpu, rows=rows)
        before = tuple(map(bytes, h.m.banks))
        assert b'REFUSED: journal/target' in command(h, 1, b'B 0 9000'), name
        assert tuple(map(bytes, h.m.banks)) == before and not h.m.events, name
        preserved(h)
    passed(cpu, 1, 'journal-damage-ambiguity-capacity-and-wear-refusals', cases=len(cases))


def interruption_tests(build, cpu, passed):
    for operation in ('bank', 'default'):
        for rollover in (False, True):
            old = core.record(seq=15 if rollover else 1, mask=1 if operation == 'default' else 0,
                              pages=(9, 8, 8, 8))
            rows = [(0xce00 if rollover else 0xc000, old)]
            if rollover:
                rows.append((0xd000, core.record(seq=1, mask=0)))
            h = load(build, cpu, rows=rows)
            before = latest(h.m.banks)
            line = b'B 0 A000' if operation == 'bank' else b'C 0'
            assert b'OK' in command(h, 1, line)
            final = latest(h.m.banks)
            snapshots = list(h.m.snapshots)
            assert snapshots and any(e[0] == 'erase' for e in h.m.events) == rollover
            for snapshot in snapshots:
                banks = [bytearray(b) for b in h.initial_banks]
                banks[3][0x4000:0x6000] = snapshot
                reboot = reboot_reader(build, cpu, banks)
                r = latest(banks)
                # A prefix may publish only the old or requested boot tuple.
                assert r[7:8]+r[12:30] in (before[7:8]+before[12:30], final[7:8]+final[12:30])
                # Legacy settings, unknown-history flags and extensions survive.
                assert r[32:64]+r[160:252] == before[32:64]+before[160:252]
                assert bytes(reboot.m.ram[0x6700:0x6720]) == r[:32]
            # Retry selected torn data/commit and erase prefixes through raw L.
            selected = {0, len(snapshots)//2, len(snapshots)-1}
            selected.update(n for n,e in enumerate(h.m.events) if e[0] == 'erase')
            for index in sorted(selected):
                banks = [bytearray(b) for b in h.initial_banks]
                banks[3][0x4000:0x6000] = snapshots[index]
                retry = load(build, cpu, banks=banks)
                out = command(retry, 1, line)
                # A full final reservation page can require inspected recovery;
                # refusal is valid only if no flash mutation took place.
                if b'REFUSED' in out:
                    assert not retry.m.events
                else:
                    assert b'OK' in out
                    assert latest(retry.m.banks)[7:8]+latest(retry.m.banks)[12:30] == final[7:8]+final[12:30]
                preserved(retry)
            preserved(h)
            passed(cpu, 1, f'all-mutation-prefixes-{operation}-'+('rollover' if rollover else 'append'),
                   prefixes=len(snapshots), retries=len(selected))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--cpu', choices=CPUS)
    x = p.parse_args(); build = x.build.resolve(); results = []
    def passed(cpu, port, case, **details):
        results.append(dict(cpu=cpu, port=port, case=case, passed=True, **details))
        print('PASS', cpu, port, case, details, flush=True)
    for cpu in (x.cpu,) if x.cpu else CPUS:
        for port in (1, 2):
            interface_tests(build, cpu, port, passed)
            refusal_tests(build, cpu, port, passed)
        bank_entries(build, cpu, passed)
        journal_refusals(build, cpu, passed)
        interruption_tests(build, cpu, passed)
    receipt = dict(passed=True, checks=len(results), failures=0, hardware=False, serial_access=False,
                   cases=results, mutation_prefixes=sum(r.get('prefixes', 0) for r in results),
                   checker_sha256=core.sha(Path(__file__).read_bytes()),
                   app_sha256=core.sha((build/'payload/ram-config-offline.bin').read_bytes()),
                   build_report_sha256=core.sha((build/'ram-config-build.json').read_bytes()))
    suffix = '-'+x.cpu if x.cpu else ''
    core.save(build/f'ram-config-tests{suffix}.json', receipt)
    print('PASS total', len(results), 'prefixes', receipt['mutation_prefixes'], flush=True)


if __name__ == '__main__':
    main()
