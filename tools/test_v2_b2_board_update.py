"""Execute exact-board b2 updaters using the frozen original beta1 opcodes.

No serial I/O. The existing flash/FT245 model supplies electrical abstractions;
the actual published beta1 reset, copied 759-byte worker, RAM ABI and updater
instructions execute. Only the original long boot wait is fast-forwarded.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

import build_v2_b2_board_update as update
import build_v2_b2 as b2
from v2_b2_config import boot_pocket, checksum

# Existing models load symbols from the current build, whose worker front ABI,
# monitor scratch and RAM console entry addresses are unchanged. Override IMAGE
# and boot-wait addresses below before creating a CPU; no reduced core executes.
sys.modules['build_v2'] = b2
import test_v2_boot as boot
import test_v2_flash as flash


class OriginalCPU(boot.BaseMPU):
    boot_waits = 0

    def step(self):
        if self.pc == 0x7BEE:
            self.boot_waits += 1
            self.processorCycles += 329_217
            self.pc = 0x7BF6
            return
        return super().step()


class B2CPU(boot.BaseMPU):
    boot_waits = 0

    def step(self):
        if self.pc == boot.REPORT['worker']['V2W_BOOT_DELAY']:
            self.boot_waits += 1
            self.processorCycles += 329_217
            self.pc = boot.REPORT['worker']['V2W_BOOT_DELAY_DONE']
            return
        return super().step()


def run(cpu, stop, limit=15_000_000):
    boot.run(cpu, stop, limit)


def setup(source, artifact, backup, resident=3):
    boot.IMAGE = source
    mem = flash.FlashMemory(resident)
    cpu = OriginalCPU(memory=mem, pc=0xF004)
    mem.cpu = cpu
    run(cpu, lambda: boot.waiting(cpu), 1_000_000)
    # This is the original published RAM worker, not the current 741-byte build.
    expected = source[4096 + 0xC02:4096 + 0xEF9]
    assert len(expected) == 759
    assert mem.ram[0x7900:0x7BF7] == expected
    assert cpu.boot_waits == 160
    for bank in range(4):
        if bank != resident:
            mem.banks[bank][:] = bytes((bank * 37 + i) & 255 for i in range(32768))
    mem.banks[2][0x7000:] = backup
    memory, entry = b2.read_s19(artifact[0])
    for address, value in memory.items():
        mem.ram[address] = value
    assert max(memory) < 0x5800
    cpu.pc, cpu.sp = entry, 0xFF
    return cpu, mem, artifact[2]


def prompt(cpu, sym):
    run(cpu, lambda: b'TYPE Y to install b2>' in cpu.memory.tx)
    # Drain execution into the source core's initialized RAM receive routine.
    run(cpu, lambda: cpu.pc == boot.SYM['V2_GETC_WAIT'] and not cpu.memory.rx, 100_000)


def finish(cpu):
    run(cpu, lambda: cpu.pc in (0xF004, 0xF007))


def check_artifacts(source, backup, artifacts):
    for phase, artifact in artifacts.items():
        path, new, sym = artifact
        memory, entry = b2.read_s19(path)
        assert entry == 0x2000 and sym['E_END'] < 0x5800
        assert bytes(memory[a] for a in range(sym['E_NEW'], sym['E_NEW'] + 4096)) == new
        phase_source = source if phase == 'e' else artifacts['e'][1] + source[4096:]
        old, _, guard, _ = update.plan(phase_source, phase, backup)
        assert bytes(memory[a] for a in range(sym['E_OLD'], sym['E_OLD'] + 4096)) == old
        assert bytes(memory[a] for a in range(sym['E_GUARD_IMAGE'], sym['E_GUARD_IMAGE'] + 4096)) == guard
        assert len(memory) == sym['E_END'] - 0x2000
    assert update.normalized(artifacts['f'][1]) == update.normalized(
        (b2.OUT / f'{b2.STEM}-f000-ffff.bin').read_bytes())
    assert artifacts['f'][1][update.POCKET] == source[4096:][update.POCKET]
    print('PASS exact embeds, original baseline, preserved pocket, b2 bounds', flush=True)


def check_success(source, backup, artifacts):
    for phase in ('e', 'f'):
        phase_source = source if phase == 'e' else artifacts['e'][1] + source[4096:]
        cpu, mem, sym = setup(phase_source, artifacts[phase], backup)
        before = [bytes(bank) for bank in mem.banks]
        prompt(cpu, sym)
        assert not mem.events
        mem.rx.append(ord('Y'))
        finish(cpu)
        assert cpu.pc == 0xF004 and b'b2 VERIFIED' in mem.tx
        start = 0x6000 if phase == 'e' else 0x7000
        assert bytes(mem.banks[3][start:start + 4096]) == artifacts[phase][1]
        assert bytes(mem.banks[3][:start]) == before[3][:start]
        assert bytes(mem.banks[3][start+4096:]) == before[3][start+4096:]
        assert [bytes(bank) for bank in mem.banks[:3]] == before[:3]
        assert all(event[1] == 3 and start+0x8000 <= event[2] < start+0x9000 for event in mem.events)
        assert mem.bank == 3
        if phase == 'f':
            # Complete readback has succeeded before the deliberate reset.
            # The model may now execute verified ROM and install b2's new RAM
            # worker. This does not permit ROM execution during failure paths.
            mem.self_changed = False
            restarted = B2CPU(memory=mem, pc=0xF004)
            mem.cpu = restarted
            run(restarted, lambda: boot.waiting(restarted), 1_000_000)
            assert b'STR8-N 2.0b2' in mem.tx
            output = flash.send(restarted, b'K\r', limit=15_000_000)
            assert b'K 00' in output and b'RTS unavailable' not in output
            assert mem.ram[0x7DE8] == 1
            assert bytes(mem.ram[0x7503:0x7507]) == bytes(4)
    print('PASS E then F full-sector updates through original beta1 RAM worker', flush=True)


def check_preflight(source, backup, artifacts):
    for phase in ('e', 'f'):
        phase_source = source if phase == 'e' else artifacts['e'][1] + source[4096:]
        for defect in ('old', 'guard', 'backup', 'cancel', 'late-old', 'late-guard', 'late-backup'):
            if 'backup' in defect and phase != 'f':
                continue
            cpu, mem, sym = setup(phase_source, artifacts[phase], backup)
            target = 0x6000 if phase == 'e' else 0x7000
            guard = 0x7000 if phase == 'e' else 0x6000
            if defect == 'old':
                mem.banks[3][target+123] ^= 1
            elif defect == 'guard':
                mem.banks[3][guard+456] ^= 1
            elif defect == 'backup':
                mem.banks[2][0x7ABC] ^= 1
            else:
                prompt(cpu, sym)
                if defect == 'late-old':
                    mem.banks[3][target+123] ^= 1
                elif defect == 'late-guard':
                    mem.banks[3][guard+456] ^= 1
                elif defect == 'late-backup':
                    mem.banks[2][0x7ABC] ^= 1
                mem.rx.append(ord('N' if defect == 'cancel' else 'Y'))
            finish(cpu)
            assert cpu.pc == 0xF007 and not mem.events, (phase, defect)
            assert mem.bank == 3
    print('PASS old/other-sector/B2 backup guards, post-confirmation rechecks, cancellation', flush=True)


def check_failure_recovery(source, backup, artifacts):
    for phase in ('e', 'f'):
        phase_source = source if phase == 'e' else artifacts['e'][1] + source[4096:]
        for fault in ('timeout', 'verify'):
            cpu, mem, sym = setup(phase_source, artifacts[phase], backup)
            before = [bytes(bank) for bank in mem.banks]
            prompt(cpu, sym)
            mem.fault = fault
            mem.rx.append(ord('Y'))
            run(cpu, lambda: cpu.pc == sym['E_ROLLBACK'])
            mem.fault = None
            finish(cpu)
            assert cpu.pc == 0xF004 and b'OLD RESTORED' in mem.tx
            assert [bytes(bank) for bank in mem.banks] == before
        cpu, mem, sym = setup(phase_source, artifacts[phase], backup)
        before = [bytes(bank) for bank in mem.banks]
        prompt(cpu, sym)
        # Erase readback failure also persists when the old E image is all FF;
        # a program-only failure would disappear during an erase-only rollback.
        mem.fault = 'erase_verify'
        mem.rx.append(ord('Y'))
        run(cpu, lambda: b'WRITE/ROLLBACK FAILED' in mem.tx)
        run(cpu, lambda: cpu.pc == sym['E_FAILED_WAIT'], 100_000)
        assert cpu.pc < 0x8000
        mem.fault = None
        mem.rx.append(ord('Y'))
        finish(cpu)
        assert b'OLD RESTORED' in mem.tx and [bytes(bank) for bank in mem.banks] == before
    print('PASS timeout/readback rollback and double-failure RAM retry for E/F', flush=True)


def check_host_rejections(source, backup, artifacts):
    for data, phase, saved in ((source, 'f', backup),
                               (artifacts['e'][1]+source[4096:], 'f', b'\xff'*4096)):
        try:
            update.plan(data, phase, saved)
        except ValueError:
            pass
        else:
            raise AssertionError('Unsafe F plan accepted')
    damaged = bytearray(source)
    damaged[-100] ^= 1
    try:
        update.plan(bytes(damaged), 'e')
    except ValueError:
        pass
    else:
        raise AssertionError('Unknown source core accepted')
    invalid = bytearray(artifacts['e'][1] + source[4096:])
    pocket = bytearray(invalid[-48:-32])
    pocket[3:5] = (0x5800).to_bytes(2, 'little')
    pocket[14:] = checksum(pocket[:14])
    invalid[-48:-32] = pocket
    try:
        update.plan(bytes(invalid), 'f', bytes(invalid[-4096:]))
    except ValueError:
        pass
    else:
        raise AssertionError('Reserved RAM autostart accepted')
    print('PASS host rejection of wrong E, wrong backup, unknown core and invalid b2 boot address', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--readback', type=Path)
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    frozen = update.baseline()
    if args.readback:
        source = update.source_ef(args.readback.read_bytes())
    else:
        f = bytearray(frozen)
        f[update.POCKET] = boot_pocket()
        source = b'\xff' * 4096 + bytes(f)
    backup = update.backup_f(args.backup.read_bytes()) if args.backup else source[4096:]
    out = update.ROOT / 'BUILD/v2-b2-board-update-tests'
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='run-', dir=out) as temporary:
        artifacts = {}
        artifacts['e'] = update.build(source, Path(temporary) / 'e', 'e')
        artifacts['f'] = update.build(artifacts['e'][1] + source[4096:], Path(temporary) / 'f', 'f', backup)
        check_artifacts(source, backup, artifacts)
        check_success(source, backup, artifacts)
        check_preflight(source, backup, artifacts)
        check_failure_recovery(source, backup, artifacts)
        check_host_rejections(source, backup, artifacts)
        receipt = dict(tested_original_core_sha256=update.BASELINE_SHA,
                       source_ef_sha256=update.sha(source), backup_sha256=update.sha(backup),
                       candidate_e_sha256=update.sha(artifacts['e'][1]),
                       candidate_f_sha256=update.sha(artifacts['f'][1]),
                       groups=5, original_ram_worker_bytes=759,
                       builder_sha256=update.sha(Path(update.__file__).read_bytes()),
                       test_source_sha256=update.sha(Path(__file__).read_bytes()),
                       updater_end={phase: artifact[2]['E_END'] for phase, artifact in artifacts.items()})
        (out / 'test-results.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('All exact-board updater host tests passed.', flush=True)


if __name__ == '__main__':
    main()
