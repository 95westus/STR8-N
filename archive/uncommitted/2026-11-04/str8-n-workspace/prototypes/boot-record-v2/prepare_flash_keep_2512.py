"""Fresh-source one-sector FLASH installation proof; no board or serial access."""
import argparse
from pathlib import Path
import board_flash_keep_2512 as live
import test_bank_monitor as app
from prepare_bank_monitor_2512 import load


def execute(run,cpu,banks,owner,zp):
    h = app.Machine(live.BUILD,cpu,banks=banks)
    h.m.ram[0x200:0x6500] = owner; h.m.ram[:0xe0] = zp
    h.recovery(); h.cmd(b'C1\r',ending=live.io.REC)
    oi,monitor = h.sy['core/ram-installer'],h.i
    h.i = oi
    load(h,(live.BUILD/'payload/ram-installer-offline.bin').read_bytes(),live.prior.OI)
    image = (live.BUILD/'payload/bank-monitor-8000.bin').read_bytes()
    before = live.io.latest(banks)
    h.m.arm((0,0x80))
    out = h.request(app.tools.frame(bank=0,sector=0x80,body=image,preimage=banks[0][:4096]),image)
    assert b'OK: verified sector' in out and h.m.target_erases == 1
    h.m.assert_preserved()
    final = list(map(bytes,h.m.banks))
    assert final[0][:4096] == image and final[0][4096:] == banks[0][4096:]
    assert final[1:3] == banks[1:3]
    after = live.io.latest(final)
    assert live.prior.policy(before) == live.prior.policy(after)
    assert int.from_bytes(after[8:12],'little') == int.from_bytes(before[8:12],'little')+1
    for bank in range(4):
        for sector in range(0x80,0x100,0x10):
            assert app.tools.counter(after,bank,sector)-app.tools.counter(before,bank,sector) == int((bank,sector)==(0,0x80))
    for offset in (0,0x1000,0x2000,0x3000,0x6000,0x7000):
        assert final[3][offset:offset+4096] == banks[3][offset:offset+4096]
    for n,data in enumerate(final):
        path = run/f'expected-b{n}.bin'
        if path.exists(): assert path.read_bytes() == data, ('CPU postimage differs',n)
        else: live.io.durable(path,data)
    h.cmd(b'Q\r',ending=live.io.REC); h.i = monitor
    out = h.cmd(b'0\r',ending=live.prior.FLASH)
    assert b'FLASH / MAINT - b15 example' in out
    assert b'F addr byte...' in h.cmd(b'?\r')
    out = h.cmd(b'Q\r',ending=live.io.MON)
    assert b'STR8-N 2.0proto b15 B3' in out and h.m.ram[0x7d30] == 0xb0
    h.recovery(); h.cmd(b'C1\r',ending=live.io.REC)
    load(h,(live.io.SERVICE/'payload/mon-service-load.bin').read_bytes(),live.io.SVC)
    h.port_command(1,b'W'+owner+live.io.crc(owner).to_bytes(2,'little'),live.io.SVC)
    assert bytes(h.m.ram[0x200:0x6500]) == owner and bytes(h.m.ram[:0xe0]) == zp
    h.m.rx.extend(b'J')
    app.base.Machine.run(h,lambda:bytes(h.m.tx).endswith(live.io.MON))
    assert h.m.ram[0x7d02] == 3 and h.m.ram[0x7d30] == 0xb0
    assert bytes(h.m.ram[0x200:0x6500]) == owner and bytes(h.m.ram[:0xe0]) == zp
    assert list(map(bytes,h.m.banks)) == final
    return dict(passed=True,cpu=cpu,target='B0:8',FLASH_left_installed=True,
        boot_help_Q_verified=True,boot_policy_preserved=True,owner_RAM_ZP_restored=True,
        final_default_B=True,erase_attempts=1,journal_erases=0,
        original_sequence=int.from_bytes(before[8:12],'little'),final_sequence=int.from_bytes(after[8:12],'little'),
        final_bank_sha256=list(map(live.io.sha,final)))


def main(run):
    live.admission(); state = live.io.read(run/'state.json')
    assert state['capture_passed'] and not state['verification_pending']
    assert not (run/'live-model-proof.json').exists()
    banks = [(run/f'source-r1-b{n}.bin').read_bytes() for n in range(4)]
    assert banks == [(run/f'source-r2-b{n}.bin').read_bytes() for n in range(4)] == live.banks_before()
    owner,zp = (run/'owner-ram.bin').read_bytes(),(run/'owner-zp.bin').read_bytes()
    assert live.io.sha(owner) == state['owner_ram_sha256'] and live.io.sha(zp) == state['owner_zp_sha256']
    assert (run/'original-B0.bin').read_bytes() == banks[0]
    assert (run/'original-B0-80.bin').read_bytes() == banks[0][:4096]
    cases = []
    for cpu in ('65c02','65c816-e'):
        cases.append(execute(run,cpu,banks,owner,zp))
        print('PASS one-sector leave-installed/source-bound model:',cpu,flush=True)
    files = [run/'authorization.json',run/'backup-manifest.json',run/'original-B0.bin',run/'original-B0-80.bin',
        run/'owner-ram.bin',run/'owner-zp.bin',run/'original-record.bin',
        live.BUILD/'payload/bank-monitor-8000.bin',live.BUILD/'payload/ram-installer-offline.bin',
        live.BUILD/'bank-monitor-qualification.json',live.io.SERVICE/'payload/mon-service-load.bin',
        live.HERE/'flash-keep-host-tests.json',live.HERE/'board_bank_monitor_2512.py',
        live.HERE/'board_ram_config_2512.py',live.HERE/'prepare_bank_monitor_2512.py']
    files += [run/f'source-r{r}-b{n}.bin' for r in (1,2) for n in range(4)]
    files += [run/f'expected-b{n}.bin' for n in range(4)]
    live.io.save(run/'live-model-proof.json',dict(passed=True,hardware=False,serial_access=False,
        cases=cases,helper_sha256=live.io.sha(Path(live.__file__).read_bytes()),
        checker_sha256=live.io.sha(Path(__file__).read_bytes()),
        bindings={str(p):live.io.sha(p.read_bytes()) for p in files}))
    print('PASS source-bound keep-installed plan; one B0:8 erase; default B unchanged',flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run',type=Path,required=True)
    main(p.parse_args().run.resolve())
