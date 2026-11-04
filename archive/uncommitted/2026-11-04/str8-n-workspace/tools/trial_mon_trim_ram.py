"""Test native TIME's live control/trim read in RAM, then restore owner RAM/ZP."""
import argparse,json,re,time
from pathlib import Path
import install_2512_native_utilities as d

t=d.t
MON=t.ROOT/'BUILD/mon-gD-trim-r1'
PATTERN=rb'RTCC: (20\d\d-\d\d-\d\d \d\d:\d\d:\d\d) flags \$([0-9A-F]{2}) trim \$([0-9A-F]{2}) ctrl \$([0-9A-F]{2})'


def run(board,folder):
    folder=Path(folder).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    manifest=json.loads((MON/'manifest.json').read_text())
    name,entry=next((n,a) for n,a in manifest['artifacts'].items() if a['variant']=='RAM')
    image=(MON/name).read_bytes();assert t.sha(image)==entry['sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    markerpath=t.ROOT/f'output/qualification/device-operations/{board}.json'
    r=dict(board=board,passed=False,checks=[],flash_writes=0,F_writes=0,
           RTC_data_writes=0,PF_ACK=0,SRAM_data_writes=0,owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;borrowed=False;ram=zp=prefix=None
    def save():t.save(folder/'report.json',r)
    def mark(**kw):
        m=json.loads(markerpath.read_text());m.update(kw);t.save(markerpath,m)
    def check(label):r['checks'].append(label);save();print('PASS '+board+' '+label,flush=True)
    def rec():
        if s.context==t.CLOCK:s.command('Q',(t.MON,))
        if s.context==t.MON:s.command('Q',(t.REC,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        assert s.context==t.REC
    save()
    with t.serial_lease(board+'-MON-trim-RAM-only',timeout=30):
        marker=json.loads(markerpath.read_text())
        assert not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        with (folder/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12)
                if s.context==t.REC:s.command('B',(t.MON,))
                assert b'g0000000C / MON B' in s.command('VERSION')
                prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
                (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
                mark(mon_trim_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                borrowed=True;rec();t.transport.recovery_usb(s.link);s.service(reader)
                mem=s.client.read(b'M',0x6500);assert mem[:len(reader)]==reader
                ram=prefix+mem[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
                old3=s.client.flash(3);assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
                (folder/'B3-before.bin').write_bytes(old3)
                r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp),journal=t.classify_journal(old3))
                check('fresh-owner-and-current-B3-escrow')
                # Independent existing CLOCK implementation, query only.
                rec();s.command('B',(t.MON,));s.command('R CLOCK',(t.CLOCK,))
                status=s.command('STATUS');(folder/'CLOCK-STATUS.txt').write_bytes(status)
                trim=s.command('TRIM');(folder/'CLOCK-TRIM.txt').write_bytes(trim)
                ref=re.search(rb'Trim\s+([+-]?\d+) steps; coarse (ON|OFF); OSCTRIM \$([0-9A-F]{2})',trim)
                assert ref,trim
                r.update(CLOCK_trim_steps=int(ref[1]),CLOCK_trim_raw=int(ref[3],16),CLOCK_coarse=ref[2].decode())
                rec();s.load(image,t.sha(image),t.MON)
                version=s.command('VERSION');assert b'g0000000D / RAM' in version
                assert b'Board: '+board.encode() in version and b'STATUS tools unavailable' not in version
                readings=[]
                for n in range(3):
                    face=s.command('TIME');(folder/f'TIME-{n}.txt').write_bytes(face)
                    m=re.search(PATTERN,face);assert m and b'/ MON ' not in face,face
                    raw,ctrl=int(m[3],16),int(m[4],16)
                    assert raw==r['CLOCK_trim_raw']
                    assert bool(ctrl&4)==(r['CLOCK_coarse']=='ON')
                    assert (raw&127 if raw&128 else -(raw&127))==r['CLOCK_trim_steps']
                    assert s.dump(0x6AB7,0x6AB8)==bytes((ctrl,raw))
                    readings.append(dict(UTC=m[1].decode(),trim_raw=raw,control_register=ctrl))
                    if n<2:time.sleep(1.1)
                assert readings[-1]['UTC']>readings[0]['UTC']
                assert len({(x['trim_raw'],x['control_register']) for x in readings})==1
                assert s.dump(0,0xDF)==zp
                r['readings']=readings;check('live-TIME-trim-control-raw-bytes-and-independent-CLOCK-agree')
                rec();s.service(reader);assert s.client.flash(3)==old3
                check('golden-F-all-images-boot-wear-and-board-metadata-unchanged')
            finally:
                try:
                    if borrowed:
                        if s.context!=d.SERVICE:rec();s.service(reader)
                        if ram is None:
                            mem=s.client.read(b'M',0x6500);assert mem[:len(reader)]==reader
                            ram=prefix+mem[len(reader):]
                        r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                        s.command('B',(t.MON,));r['owner_RAM_restored']=True
                finally:
                    if s is not None:s.link.close();r['port_released']=True
                    if borrowed:
                        restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                        mark(mon_trim_RAM_worker_active=False,application_RAM_restore_pending=not restored,
                             application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                             last_MON_trim_RAM_trial=str(folder/'report.json'))
                    save()
    r['passed']=len(r['checks'])==3 and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();assert r['passed'];print('PASS '+board+' native trim RAM qualification; port released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True)
    p.add_argument('--out',required=True);a=p.parse_args();run(a.board,a.out)
