"""Read the non-acknowledging VIA guard registers; preserve 64 RAM bytes/ZP.

No ORB read, PREP, flag acknowledgement, SPI clocks, flash or device-data write.
The short RAM printer calls the admitted monitor's quiet-return vector.
"""
import argparse,json,binascii
from pathlib import Path
import install_2512_native_utilities as d
t=d.t

def run(board,folder,b3file):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    b3=Path(b3file).read_bytes();mi=b3[0x3000:0x4000]
    assert len(b3)==32768 and mi[:3]==b'MI\x01'
    assert binascii.crc_hqx(mi[:18]+mi[32:],65535)==int.from_bytes(mi[18:20],'little')
    quiet=int.from_bytes(mi[42:44],'little');assert 0xB080<=quiet<0xC000
    code=bytearray(b'\x78\xd8')
    for address in (0x7FC2,0x7FCB,0x7FCC,0x7FCD,0x7FCE):
        code+=b'\xad'+address.to_bytes(2,'little')+bytes.fromhex('20 7C 7E A9 20 20 6D 7E')
    code+=bytes.fromhex('20 7F 7E 4C')+quiet.to_bytes(2,'little')
    assert len(code)==63;code=code.ljust(64,b'\xea')
    markerpath=t.ROOT/f'output/qualification/device-operations/{board}.json'
    report=dict(board=board,passed=False,flash_writes=0,RTC_writes=0,SRAM_writes=0,
                VIA_writes=0,flag_acknowledgements=0,owner_RAM_restored=False)
    def save():t.save(folder/'report.json',report)
    original=None;before=zp=None;borrowed=False;s=None
    def mark(**kw):
        m=json.loads(markerpath.read_text());m.update(kw);t.save(markerpath,m)
    save()
    with t.serial_lease(board+'-status-bus-guard-readonly',timeout=30):
      marker=json.loads(markerpath.read_text());assert not marker.get('application_RAM_restore_pending')
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);original=s.context
            if original==t.REC:s.command('B',(t.MON,))
            assert s.dump(0xB02A,0xB02B)==quiet.to_bytes(2,'little')
            before=s.dump(0x4000,0x403F);zp=s.dump(0,0xDF)
            (folder/'owner-4000-403F.bin').write_bytes(before);(folder/'owner-zp.bin').write_bytes(zp)
            mark(status_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            s.modify(0x4000,code);assert s.dump(0x4000,0x403F)==code
            out=s.command('G 4000',(t.MON,));(folder/'guard-registers.txt').write_bytes(out)
            import re
            found=re.search(rb'\r?\n([0-9A-F]{2}(?: [0-9A-F]{2}){4}) ',out)
            assert found,out
            values=bytes.fromhex(found[1].decode())
            report['guard_registers']=dict(zip(('DDRB','ACR','PCR','IFR','IER'),values))
            print(board,'guard registers',report['guard_registers'],flush=True)
        finally:
          try:
            if borrowed:
                assert s.context==t.MON
                s.modify(0x4000,before)
                assert s.dump(0x4000,0x403F)==before and s.dump(0,0xDF)==zp
                report.update(owner_RAM_restored=True,owner_ZP_unchanged=True)
            if s is not None and original==t.REC:s.command('Q',(t.REC,))
          finally:
            if s is not None:s.link.close();report['port_released']=True
            if borrowed:mark(status_worker_active=False,application_RAM_restore_pending=not report['owner_RAM_restored'],
                block_snapshot=marker['block_snapshot'] if report['owner_RAM_restored'] else True)
            save()
    report['passed']=report['owner_RAM_restored'] and 'guard_registers' in report;save()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True)
    p.add_argument('--folder',required=True);p.add_argument('--b3',required=True);a=p.parse_args();run(a.board,a.folder,a.b3)
