"""Actual linked instructions through relocated startup/drain and software J3."""
import argparse,json
from pathlib import Path
import test_boot_startup as timing
from build_b13 import ROOT

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True)
    p.add_argument('--cpu',choices=['65c02','65c816-e'],required=True)
    args=p.parse_args();build=args.build.resolve();cpu=args.cpu
    timing.core.GENERATION=json.loads((build/'prototype-report.json').read_bytes())['experimental_generation']
    rows=[]
    def passed(case,**details):
        rows.append(dict(cpu=cpu,case=case,passed=True,**details));print('PASS',cpu,case,flush=True)
    h=timing.StartupMachine(build,cpu)
    timing.check_instruction_timing(type(h.c))
    h.run(lambda:h.c.pc==h.b['BOOT_STARTUP']);timing.seed_software(h)
    h.m.rx.extend(b'SAB0123\r\n'*48);h.m.acia_rx.extend(b'S')
    start=h.c.processorCycles
    h.run(lambda:h.c.pc==h.b['BOOT_USB_WAIT_DONE'])
    usb=h.c.processorCycles-start
    assert 15_980_000<=usb<=16_020_000 and not h.m.input_reads and not h.m.consumed
    assert not h.m.tx and not h.m.acia_tx
    passed('relocated-two-second-USB-quiet-wait',cycles=usb,seconds_at_8MHz=usb/8_000_000)
    usb_done=timing.checkpoint(h)
    h.run(lambda:h.c.pc==h.b['BOOT_DRAIN_BEGIN'])
    assert bytes(h.m.tx)==bytes(h.m.acia_tx)==b'\r\nWAIT...\r\n'
    timing.queue_flags_clear(h);drain_begin=timing.checkpoint(h)
    def active(item):
        # The frozen startup helper predates the six-second chooser.
        item.run(lambda:item.c.pc==item.b['BR_COUNTDOWN'])
        assert item.m.ram[item.b['BR_TICKS']]==6 and item.m.ram[0x7d02]==3
        item.timer_start=item.c.processorCycles
        timing.queue_flags_clear(item)
        assert item.m.ram[item.b['RL_VALID']]==0 and item.m.ram[0xec]==0
        item.preserved()
    def drain(item):
        start=item.c.processorCycles;before=len(item.m.consumed)
        item.run(lambda:item.c.pc==item.b['BOOT_DRAIN_DONE'])
        cycles=item.c.processorCycles-start
        # Original loop 8,000,495 cycles plus the new exit JMP's three cycles.
        assert cycles==8_000_498,(cpu,cycles)
        item.preserved();return cycles,item.m.consumed[before:]
    cycles,discarded=drain(h)
    assert len([e for e in discarded if e[1]==1])==len(b'SAB0123\r\n'*48) and not h.m.rx
    active(h);ready=timing.checkpoint(h)
    passed('stale-input-drained-and-chooser-entered',drain_cycles=cycles,discarded_bytes=len(discarded))
    for scenario in ('idle','64KiB-FT-backlog','continuous-both-ready','paced-ACIA-and-FIFO','FT-output-blocked'):
        item=timing.checkpoint(drain_begin);timing.clear_input(item);item.m.consumed.clear()
        if scenario=='64KiB-FT-backlog':item.m.rx.extend(bytes(range(256))*256)
        elif scenario=='continuous-both-ready':
            item.m.rx.extend(b'S'*65536);item.m.acia_rx.extend(b'B'*65536)
        elif scenario=='paced-ACIA-and-FIFO':
            item.m.rx.extend(bytes(range(256))*2)
            item.m.schedule(2,item.c.processorCycles+100,bytes(range(256))*7+bytes(range(128)),spacing=4167)
        elif scenario=='FT-output-blocked':
            item=timing.checkpoint(usb_done);timing.clear_input(item);item.m.ft_tx_blocked=True
            item.run(lambda:item.c.pc==item.b['BOOT_DRAIN_BEGIN'])
            assert not item.m.tx and bytes(item.m.acia_tx)==b'\r\nWAIT...\r\n'
        elapsed,discarded=drain(item)
        ft=sum(e[1]==1 for e in discarded);acia=sum(e[1]==2 for e in discarded)
        if scenario=='64KiB-FT-backlog':assert ft==32256 and len(item.m.rx)==33280
        elif scenario=='continuous-both-ready':assert ft==acia==32256
        elif scenario=='paced-ACIA-and-FIFO':assert ft==512 and acia==1920
        else:assert ft==acia==0
        passed('balanced-bounded-drain-'+scenario,cycles=elapsed,FT_bytes=ft,ACIA_bytes=acia)
    # Every key dispatch executes against the exact post-drain CPU/stack state.
    for port in (1,2):
        for byte in b'SsAaBb0123\x03':
            item=timing.checkpoint(ready)
            if byte in b'AaBb':
                for sector in (0xa0,0xb0):
                    offset=(sector-0x80)<<8
                    item.m.banks[3][offset:offset+4096]=(build/f'payload/monitor-{sector:02x}-offline-component.bin').read_bytes()
                item.flash=tuple(map(bytes,item.m.banks))
            item.m.schedule(port,item.c.processorCycles+160_000,bytes([byte]))
            result=item.dispatch()
            expected='recovery' if byte in b'Ss\x03' else (0xa0 if byte in b'Aa' else 0xb0) if byte in b'AaBb' else byte-48
            assert result==expected;item.preserved()
            passed(f'post-drain-key-{byte:02x}-port-{port}',result=result)
    item=timing.checkpoint(ready)
    for sector in (0xa0,0xb0):
        offset=(sector-0x80)<<8
        item.m.banks[3][offset:offset+4096]=(build/f'payload/monitor-{sector:02x}-offline-component.bin').read_bytes()
    item.flash=tuple(map(bytes,item.m.banks))
    item.m.acia_rx.extend(b'B');item.run(lambda:bytes(item.m.acia_tx).endswith(b'B3> '))
    item.run(lambda:item.c.pc==item.w['V2W_GETC'])
    item.m.acia_rx.extend(b'J3\r\n');item.run(lambda:item.c.pc==item.b['BOOT_STARTUP'])
    outputs=len(item.m.tx),len(item.m.acia_tx);consumed=len(item.m.consumed);start=item.c.processorCycles
    item.m.schedule(2,start+8_000_000,b'\nS\rA\r0\r')
    item.run(lambda:item.c.pc==item.b['BOOT_USB_WAIT_DONE'])
    assert item.c.processorCycles-start==usb and len(item.m.consumed)==consumed
    assert (len(item.m.tx),len(item.m.acia_tx))==outputs
    item.run(lambda:item.c.pc==item.b['BOOT_DRAIN_BEGIN']);elapsed,discarded=drain(item)
    active(item);assert not item.m.rx and not item.m.acia_rx and not item.m.acia_wire and item.m.acia_latch is None
    item.m.acia_rx.extend(b'S');item.run(lambda:bytes(item.m.acia_tx).endswith(b'REC> '))
    assert item.m.ram[item.b['RL_VALID']]==0;item.preserved()
    passed('actual-MON-B-software-J3-CRLF-stale-input-drain-then-fresh-S',USB_cycles=usb,drain_cycles=elapsed)
    result=dict(passed=True,checks=len(rows),failures=0,hardware=False,serial_access=False,cases=rows,
        timing_model='Linked CPU instructions at nominal 8MHz with documented emulator cycle corrections; no electrical timing claim',
        F_sha256=timing.core.sha((build/'payload/f-offline-component.bin').read_bytes()),
        checker_sha256=timing.core.sha(Path(__file__).read_bytes()))
    timing.core.save(build/f'b13-startup-{cpu}.json',result)

if __name__=='__main__':main()
