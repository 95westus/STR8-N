"""Installed copyright DBG: real BRK/register/resume smoke, fresh RAM escrow."""
import argparse
import json
from pathlib import Path
import trial_copyright_2512 as t

m=t.m


def run(out):
    out=Path(out).resolve(); out.mkdir(parents=True,exist_ok=False)
    m.durable(out/'.gitignore',b'*\n'); m.durable(out/'driver.py',Path(__file__).read_bytes())
    marker=m.ROOT/'output/qualification/device-operations/2512.json'
    report=dict(board='2512',passed=False,flash_writes=0,SPI_writes=0,EEPROM_writes=0,checks=[])
    def save():m.save(out/'report.json',report)
    def mark(**kw):
        state=json.loads(marker.read_text()); state.update(kw); m.save(marker,state)
    s=None; ram=zp=None; borrowed=False
    save()
    with t.serial_lease('2512-copyright-DBG-BRK-resume',timeout=45):
        state=json.loads(marker.read_text())
        m.require(not state['block_snapshot'] and not state['application_RAM_restore_pending'],'Pending RAM restoration')
        try:
            s=t.Session(out)
            if s.context==t.REC:s.cmd('B',(t.MON,))
            m.require(b'(c)2026 95west.us/wlp1963; MIT' in s.cmd('VERSION'),'Installed copyright monitor required')
            def dump(a,z):
                return b''.join(m.parse_monitor_dump(s.link.command(f'D {p:04X} {min(z,p+511):04X}',t.MON),p,min(z,p+511))
                                for p in range(a,z+1,512))
            reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
            prefix=dump(0x200,0x1ff+len(reader)); zp=dump(0,0xdf)
            m.durable(out/'owner-prefix.bin',prefix); m.durable(out/'owner-zp.bin',zp)
            hooks=dump(0x7e02,0x7e03)+dump(0x7e67,0x7e69)
            mark(copyright_DBG_worker_active=True,application_RAM_restore_pending=True,application_ram_restored=False,block_snapshot=True)
            borrowed=True; client=s.reader(); mem=client.read(b'M',0x6500)
            m.require(mem[:len(reader)]==reader,'Readback prefix differs')
            ram=prefix+mem[len(reader):]; m.durable(out/'owner-ram.bin',ram)
            before=client.flash(3); m.durable(out/'B3-before.bin',before)
            s.rec(); s.cmd('B',(t.MON,))
            s.cmd('M 1000 A9 2A 00 01 4C 67 7E')
            m.require(dump(0x1000,0x1006)==bytes.fromhex('A9 2A 00 01 4C 67 7E'),'Debug target write differs')
            face=s.cmd('R DBG',(b'Q MON> ',)); m.require(b'Copyright (c)' in face,'DBG copyright missing')
            s.cmd('1000',(b'DBG> ',))
            # DBG first stops at the requested entry. Continue once to execute
            # LDA/BRK, then inspect the actual BRK register capture.
            s.cmd('C',(b'DBG> ',))
            face=s.cmd('R')
            m.require(b'A=2A' in face,'BRK register A is not 2A: '+repr(face))
            report['checks'].append('installed-DBG-real-BRK-and-register-A-2A');save()
            s.cmd('C',(t.MON,))
            m.require(dump(0x7e02,0x7e03)+dump(0x7e67,0x7e69)==hooks,'Debugger hooks not restored')
            report['checks'].append('continue-through-program-HOLD-restores-MON-and-hooks');save()
            client=s.reader(); m.require(client.flash(3)==before,'DBG trial changed B3')
            report['checks'].append('B3-including-F-journals-and-settings-unchanged');save()
            report['passed']=True
        except BaseException as error:
            report['error']=repr(error);save();raise
        finally:
            try:
                if borrowed and s and ram is not None and s.context is not None:
                    if s.context==b'DBG> ':s.cmd('X',(t.MON,))
                    if s.context==b'Q MON> ':s.cmd('Q',(t.MON,))
                    client=s.reader(); report['RAM_cleanup']=client.restore_owner(ram,zp); s.context=t.REC
            finally:
                if s:s.close()
                restored=bool(report.get('RAM_cleanup',{}).get('owner_RAM_restored'))
                if borrowed:mark(copyright_DBG_worker_active=False,application_RAM_restore_pending=not restored,
                                 application_ram_restored=restored,block_snapshot=not restored,final_prompt='REC>' if restored else 'RESTORATION REQUIRED')
                report['port_released']=True;save()
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
