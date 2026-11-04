"""Close the stopped pre-flash RAM guard without any flash mutation."""
import json,sys,time
from pathlib import Path
import board_opaque_absent_2512 as h
RUN=h.pf.ROOT/'output/qualification/opaque-absent-2512-install-run-restore'

def desired_image():
    first=(RUN/'fresh-RAM-after-service-load-r1.bin').read_bytes();second=(RUN/'fresh-RAM-after-service-load-r2.bin').read_bytes()
    prior=(RUN/'owner-RAM-baseline.bin').read_bytes();loader=(h.prior.BUILD/'payload/mon-service-load.bin').read_bytes()
    assert first==second and len(first)==len(prior)==0x6300 and first[:len(loader)]==loader
    diffs=[i for i in range(len(loader),len(prior)) if first[i]!=prior[i]]
    assert diffs==[0x4d7f-0x200] and prior[diffs[0]]==0x10 and first[diffs[0]]==0x20
    return prior[:len(loader)]+first[len(loader):],first

def main():
    desired,observed=desired_image();state=h.r.read(RUN/'state.json');marker=h.r.read(h.pf.MARKER)
    assert state['phase']=='stopped-preserve-escrow' and not state['opaque_sector_restore_pending']
    assert marker['opaque_install_run']==str(RUN) and marker['application_RAM_restore_pending'] and not marker['recovery_worker_active']
    assert not (RUN/'opaque-install.json').exists()
    h.pf.atomic(RUN/'owner-RAM-preserve-fresh-tail.bin',desired)
    from serial_test_coordination import serial_lease
    from serial.tools.list_ports import comports
    with serial_lease('2512-preflash-RAM-guard-cleanup',timeout=30):
        ports=[p for p in comports() if p.serial_number==h.b.USB];assert len(ports)==1
        with (RUN/'serial-RAM-cleanup.jsonl').open('x') as log:
            link=h.b.wire.Link(ports[0].device,log)
            try:
                # '?' is a non-mutating unknown-command -> menu in this exact
                # RAM service. It cannot request a flash operation.
                start=time.monotonic();raw=bytearray()
                while time.monotonic()-start<1:raw.extend(link.read(4096))
                assert not raw
                link.send(b'?');assert link.until(h.prior.SVC,10)==h.prior.SVC
                assert [h.prior.read_service(link,b'F'+bytes([n]),32768) for n in range(4)]==h.source_banks()
                assert h.prior.read_service(link,b'M',0x6300)==observed
                zp=(RUN/'owner-ZP-baseline.bin').read_bytes()
                for _ in range(2):assert h.prior.read_service(link,b'Z',0xe0)==zp
                h.prior.write_owner_ram(link,desired)
                for _ in range(3):assert h.prior.read_service(link,b'M',0x6300)==desired
                for _ in range(2):assert h.prior.read_service(link,b'Z',0xe0)==zp
                assert [h.prior.read_service(link,b'F'+bytes([n]),32768) for n in range(4)]==h.source_banks()
                h.quit_service(link)
            finally:link.serial.close()
    state.update(phase='closed-before-flash-current-RAM-preserved',application_RAM_restore_pending=False,
        RAM_restored=True,ZP_preserved=True,flash_written=False,serial_released=True,closed_utc=h.b.now(),
        preserved_RAM_change=dict(address='4D7F',prior='10',current='20'),preserved_RAM_sha256=h.r.sha(desired))
    h.pf.save(RUN/'state.json',state)
    restored=h.r.read(RUN/'device-marker-before.json')
    restored.update(last_preservation_report=str(RUN/'state.json'),last_RAM_preservation_receipt=str(RUN/'state.json'),
        reason='Pre-flash RAM guard closed; current 4D7F=20 preserved; full flash unchanged; ready to resume opaque test')
    h.pf.save(h.pf.MARKER,restored)
    print('PASS pre-flash RAM cleanup; current 4D7F=20 retained; flash unchanged; serial released')

if __name__=='__main__':
    if '--self-test' in sys.argv:
        image,current=desired_image();assert image[0x4d7f-0x200]==0x20;assert image[2476:]==current[2476:]
        print('PASS exact captured RAM cleanup preimage and fresh-tail preservation')
    else:main()
