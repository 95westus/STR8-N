"""Exact-source LED update/program/erase/owner-RAM preservation models."""
import argparse
from pathlib import Path
import board_flash_led_2512 as live
import test_bank_monitor as app
from prepare_bank_monitor_2512 import load


def execute(run,cpu,source,current,owner,zp):
    h = app.Machine(live.BUILD,cpu,banks=source)
    h.m.ram[0x200:0x6500] = current; h.m.ram[:0xe0] = zp
    h.recovery(); h.cmd(b'C1\r',ending=live.io.REC)
    oi,monitor = h.sy['core/ram-installer'],h.i
    h.i = oi
    load(h,(live.BUILD/'payload/ram-installer-offline.bin').read_bytes(),live.wire.OI)
    image = (live.BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    h.m.arm((0,0x80))
    assert b'OK: verified sector' in h.request(app.tools.frame(bank=0,sector=0x80,body=image,preimage=source[0][:4096]),image)
    h.m.assert_preserved(); assert h.m.target_erases == 1
    h.cmd(b'Q\r',ending=live.io.REC); h.i = monitor
    assert b'FLASH / MAINT' in h.cmd(b'0\r',ending=live.wire.FLASH)
    assert h.m.ram[0x7fa0] == 1
    h.m.arm((0,0x90)); busy = []
    h.m.observer = lambda m: busy.append(m.ram[0x7fa0])
    assert b'OK: verified sector' in h.write(b'F 9000 00\r')
    assert h.sector(0,0x90) == b'\0'+b'\xff'*4095 and h.m.ram[0x7fa0] == 1
    assert b'OK: verified sector' in h.write(b'I 9000\r')
    assert h.sector(0,0x90) == source[0][4096:8192] == b'\xff'*4096
    assert h.m.ram[0x7fa0] == 1 and busy and all(v & 0xf0 == 0xf0 for v in busy)
    h.m.assert_preserved(); assert h.m.target_erases == 2
    final = list(map(bytes,h.m.banks))
    assert final[0][:4096] == image and final[0][4096:] == source[0][4096:]
    assert final[1:3] == source[1:3]
    before,after = live.io.latest(source),live.io.latest(final)
    assert live.wire.policy(before) == live.wire.policy(after)
    assert int.from_bytes(after[8:12],'little') == int.from_bytes(before[8:12],'little')+3
    for bank in range(4):
        for sector in range(0x80,0x100,0x10):
            expected = 1 if (bank,sector)==(0,0x80) else 2 if (bank,sector)==(0,0x90) else 0
            assert app.tools.counter(after,bank,sector)-app.tools.counter(before,bank,sector) == expected
    for offset in (0,0x1000,0x2000,0x3000,0x6000,0x7000):
        assert final[3][offset:offset+4096] == source[3][offset:offset+4096]
    for n,data in enumerate(final):
        path = run/f'expected-b{n}.bin'
        if path.exists(): assert path.read_bytes() == data
        else: live.io.durable(path,data)
    h.m.observer = None
    assert b'STR8-N 2.0proto b15' in h.cmd(b'Q\r',ending=live.io.MON)
    h.recovery(); h.cmd(b'C1\r',ending=live.io.REC)
    load(h,(live.io.SERVICE/'payload/mon-service-load.bin').read_bytes(),live.io.SVC)
    h.port_command(1,b'W'+owner+live.io.crc(owner).to_bytes(2,'little'),live.io.SVC)
    h.m.rx.extend(b'J'); app.base.Machine.run(h,lambda:bytes(h.m.tx).endswith(live.io.MON))
    assert bytes(h.m.ram[0x200:0x6500]) == owner and bytes(h.m.ram[:0xe0]) == zp
    assert h.m.ram[0x7d02] == 3 and h.m.ram[0x7d30] == 0xb0
    assert list(map(bytes,h.m.banks)) == final
    return dict(passed=True,cpu=cpu,busy_LED='F0/F1',idle_LED='01',real_program_erase_paths=True,
        user_erased_B0_9_preserved=True,owner_RAM_ZP_restored=True,settings_preserved=True,
        FLASH_left_installed=True,erase_attempts={'B0:8':1,'B0:9':2},C_D_erases=0,
        original_sequence=int.from_bytes(before[8:12],'little'),final_sequence=int.from_bytes(after[8:12],'little'),
        final_bank_sha256=list(map(live.io.sha,final)))


def main(run):
    live.qualify(); state = live.io.read(run/'state.json')
    assert state['capture_passed'] and not state['verification_pending']
    assert not (run/'live-model-proof.json').exists()
    source = [(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert source == [(run/f'source-r2-b{n}.bin').read_bytes() for n in range(4)]
    current,owner,zp = ((run/name).read_bytes() for name in ('current-RAM-before-tools.bin','owner-ram.bin','owner-zp.bin'))
    assert live.io.sha(owner) == state['owner_ram_sha256'] and live.io.sha(zp) == state['owner_zp_sha256']
    cases = []
    for cpu in ('65c02','65c816-e'):
        cases.append(execute(run,cpu,source,current,owner,zp))
        print('PASS exact-source LED update/program/erase/restore',cpu,flush=True)
    files = [run/name for name in ('authorization.json','current-RAM-before-tools.bin','owner-ram.bin',
        'owner-zp.bin','original-record.bin','before-update-B0.bin','current-erased-B0-90.bin')]
    files += [run/f'source-r{r}-b{n}.bin' for r in (1,2) for n in range(4)]
    files += [run/f'expected-b{n}.bin' for n in range(4)]
    files += [live.BUILD/'payload/bank-monitor-8000.bin',live.BUILD/'payload/ram-installer-offline.bin',
        live.BUILD/'bank-monitor-qualification.json',live.BUILD/'bank-monitor-led-tests.json',
        live.io.SERVICE/'payload/mon-service-load.bin',live.HERE/'board_bank_monitor_2512.py',
        live.HERE/'board_ram_config_2512.py',live.HERE/'prepare_bank_monitor_2512.py',
        live.HERE/'flash-led-host-tests.json',live.PREVIOUS/'owner-ram.bin',
        live.OLD_BUILD/'payload/bank-monitor-8000-ram.bin',live.OLD_BUILD/'symbols.json']
    live.io.save(run/'live-model-proof.json',dict(passed=True,hardware=False,serial_access=False,cases=cases,
        helper_sha256=live.io.sha(Path(live.__file__).read_bytes()),checker_sha256=live.io.sha(Path(__file__).read_bytes()),
        bindings={str(p):live.io.sha(p.read_bytes()) for p in files}))
    print('PASS exact-source LED update ready; user B0:9 erase preserved',flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run.resolve())
