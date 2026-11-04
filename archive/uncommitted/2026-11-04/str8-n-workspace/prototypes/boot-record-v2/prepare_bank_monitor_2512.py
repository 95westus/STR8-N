"""Exact fresh-source FLASH install/edit/Q/restore models; no serial access."""
import argparse
from pathlib import Path
import board_bank_monitor_2512 as live
import test_bank_monitor as app


def source(run):
    a = [(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert a == [(run/f'source-r2-b{n}.bin').read_bytes() for n in range(4)] == live.banks_before()
    return a


def load(h, body, prompt):
    # The service bootstrap is unrolled code at $0200; its instruction stream
    # can cross a former app's CRC address. Never apply that app's shortcut
    # after replacing its bytes with another executable.
    h.accelerate_local_crc = prompt != live.io.SVC
    h.cmd(b'L\r',ending=b'SEND BIN\r\n')
    return h.port_command(1,body,prompt)


def save_banks(run, phase, banks):
    for n,bank in enumerate(banks):
        path = run/f'expected-{phase}-b{n}.bin'
        if path.exists(): assert path.read_bytes() == bank, ('CPU postimage differs',phase,n)
        else: live.io.durable(path,bytes(bank))


def execute(run, cpu, banks, owner, zp, edited, line):
    h = app.Machine(live.BUILD,cpu,banks=banks)
    h.m.ram[0x200:0x6500] = owner; h.m.ram[:0xe0] = zp
    # F has already initialized the real worker and vectors. Enter its recovery
    # menu, as the live MON J3/S sequence does, without rewriting any settings.
    h.recovery(); h.cmd(b'C1\r',ending=live.io.REC)
    oi = h.sy['core/ram-installer']; monitor = h.i
    installer = (live.BUILD/'payload/ram-installer-offline.bin').read_bytes()
    image = (live.BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    h.i = oi; load(h,installer,live.OI)
    original_record = live.io.latest(banks)
    h.m.arm((0,0x80))
    out = h.request(app.tools.frame(bank=0,sector=0x80,body=image,preimage=banks[0][:4096]),image)
    assert b'OK: verified sector' in out
    h.m.assert_preserved(); assert h.m.target_erases == 1
    h.cmd(b'Q\r',ending=live.io.REC)
    h.i = monitor
    out = h.cmd(b'0\r',ending=live.FLASH)
    assert b'FLASH / MAINT - b15 example\r\n' in out
    assert h.m.ram[h.i['BM_HOME']] == 0 and h.m.bank == 3
    assert b'F addr byte...' in h.cmd(b'?\r')
    assert b'OK: RAM' in h.cmd(b'M 2000 41 42 03 00 FF\r')
    assert h.m.ram[0x2000:0x2005] == b'AB\x03\x00\xff'
    assert b'41 42 03 00 FF ' in h.cmd(b'D 2000\r')
    for refusal in (b'M 1FFF 55\r',b'F 8000 55\r'):
        assert b'REFUSED:' in h.cmd(refusal)
    h.cmd(b'B0\r')
    h.m.arm((0,0x90))
    assert b'OK: verified sector' in h.write(line.encode()+b'\r')
    assert h.sector(0,0x90) == edited and h.m.target_erases == 1
    h.m.assert_preserved()
    assert live.policy(live.io.latest(h.m.banks)) == live.policy(original_record)
    events = len(h.m.events)
    assert b'OK: identical; no erase' in h.write(line.encode()+b'\r')
    assert len(h.m.events) == events
    out = h.cmd(b'Q\r',ending=live.io.MON)
    assert b'STR8-N 2.0proto b15 B3' in out and h.m.ram[0x7d30] == 0xb0
    assert h.m.ram[0x2000:0x2005] == b'AB\x03\x00\xff'
    save_banks(run,'edited',h.m.banks)
    # Independent RAM read/restore service is the exact previously exercised
    # loader, not the b14-bound MON restore kit. No T/X commands are sent.
    service = (live.io.SERVICE/'payload/mon-service-load.bin').read_bytes()
    h.recovery(); h.cmd(b'C1\r',ending=live.io.REC)
    load(h,service,live.io.SVC)
    h.port_command(1,b'Q',live.io.REC)
    h.i = oi; load(h,installer,live.OI)
    for sector,body,preimage in ((0x90,banks[0][4096:8192],edited),(0x80,banks[0][:4096],image)):
        h.m.arm((0,sector))
        out = h.request(app.tools.frame(bank=0,sector=sector,body=body,preimage=preimage),body)
        assert b'OK: verified sector' in out and h.m.target_erases == 1
        assert h.sector(0,sector) == body
        h.m.assert_preserved()
    final = list(map(bytes,h.m.banks)); assert final[:3] == banks[:3]
    before,after = original_record,live.io.latest(final)
    assert live.policy(before) == live.policy(after)
    for offset in (0,0x1000,0x2000,0x3000,0x6000,0x7000):
        assert final[3][offset:offset+4096] == banks[3][offset:offset+4096]
    for bank in range(4):
        for sector in range(0x80,0x100,0x10):
            added = app.tools.counter(after,bank,sector)-app.tools.counter(before,bank,sector)
            assert added == (2 if (bank,sector) in ((0,0x80),(0,0x90)) else 0), (bank,sector,added)
    assert int.from_bytes(after[8:12],'little') == int.from_bytes(before[8:12],'little')+4
    save_banks(run,'restored',final)
    h.cmd(b'Q\r',ending=live.io.REC)
    load(h,service,live.io.SVC)
    h.port_command(1,b'W'+owner+live.io.crc(owner).to_bytes(2,'little'),live.io.SVC)
    assert bytes(h.m.ram[0x200:0x6500]) == owner and bytes(h.m.ram[:0xe0]) == zp
    # Service J is a software restart. The established core runner folds only
    # the previously qualified empty startup drain, retaining the actual boot.
    h.m.rx.extend(b'J')
    app.base.Machine.run(h,lambda:bytes(h.m.tx).endswith(live.io.MON))
    assert h.m.ram[0x7d02] == 3 and h.m.ram[0x7d30] == 0xb0
    assert bytes(h.m.ram[0x200:0x6500]) == owner and bytes(h.m.ram[:0xe0]) == zp
    assert list(map(bytes,h.m.banks)) == final
    return dict(passed=True,cpu=cpu,FLASH_boot=True,RAM_edit_readback=True,flash_edit_readback=True,
        identical_noop=True,Q_to_B3=True,original_images_restored=True,boot_policy_preserved=True,
        owner_RAM_ZP_restored=True,full_countdown_default_B=True,erase_targets=['B0:8','B0:9','B0:9','B0:8'],
        journal_erases=0,original_sequence=int.from_bytes(before[8:12],'little'),
        final_sequence=int.from_bytes(after[8:12],'little'),final_bank_sha256=list(map(live.io.sha,final)))


def main(run):
    live.admission()
    state = live.io.read(run/'state.json'); assert state['capture_passed'] and not state['images_pending']
    assert not (run/'live-model-proof.json').exists()
    banks = source(run); owner = (run/'owner-ram.bin').read_bytes(); zp = (run/'owner-zp.bin').read_bytes()
    assert live.io.sha(owner) == state['owner_ram_sha256'] and live.io.sha(zp) == state['owner_zp_sha256']
    edited = bytearray(banks[0][4096:8192])
    edited[:4] = bytes(v ^ 255 for v in edited[:4])
    live.io.durable(run/'edited-B0-90.bin',edited)
    line = 'F 9000 '+' '.join(f'{v:02X}' for v in edited[:4])
    cases = []
    for cpu in ('65c02','65c816-e'):
        cases.append(execute(run,cpu,banks,owner,zp,bytes(edited),line))
        print('PASS exact fresh-source FLASH install/edit/Q/restore:',cpu,flush=True)
    files = [run/'owner-ram.bin',run/'owner-zp.bin',run/'original-record.bin',run/'edited-B0-90.bin',
        run/'authorization.json',live.BUILD/'bank-monitor-qualification.json',live.BUILD/'bank-monitor-build.json',
        live.BUILD/'payload/bank-monitor-8000.bin',live.BUILD/'payload/ram-installer-offline.bin',
        live.io.SERVICE/'payload/mon-service-load.bin',live.HERE/'bank-monitor-host-tests.json',
        live.HERE/'board_ram_config_2512.py',live.HERE/'bank-monitor.asm',live.HERE/'bank-monitor-entry.asm']
    files += [run/f'source-r{r}-b{n}.bin' for r in (1,2) for n in range(4)]
    files += [run/f'expected-{phase}-b{n}.bin' for phase in ('edited','restored') for n in range(4)]
    proof = dict(passed=True,hardware=False,serial_access=False,board='2512',cases=cases,
        flash_edit_command=line,helper_sha256=live.io.sha(Path(live.__file__).read_bytes()),
        checker_sha256=live.io.sha(Path(__file__).read_bytes()),
        bindings={str(p):live.io.sha(p.read_bytes()) for p in files},
        limits=['No physical power-cut test','Logical settings preserved; four durable erase reservations retained'])
    live.io.save(run/'live-model-proof.json',proof)
    print('PASS exact-source round trip; ready for live install/test/restore',flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run.resolve())
