"""Read-only native storage route/loader trial; restore RAM and yield to RTC."""
import argparse,json,re
from pathlib import Path
import install_2512_native_utilities as d
from serial_test_coordination import drift_pending
t=d.t
MONS=tuple(f'B{n}> '.encode() for n in range(4));MENU=b'STORAGE> ';SM=b'SRAM> ';WORK=b'WORK> ';YES=b'Type YES: '
class CollectionDue(Exception):pass

def run(board,out,workbench_only=False,carry_from=None):
    folder=Path(out).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification');folder.mkdir(exist_ok=False)
    (folder/'.gitignore').write_text('*\n');(folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    build=t.ROOT/'BUILD/sram-work-g2-native-r1';sw=json.loads((build/'manifest.json').read_text())
    packet=(build/'STR8N-SRAM-WORK-g00000002-RAM.bin').read_bytes()
    assert t.sha(packet)==sw['artifacts']['STR8N-SRAM-WORK-g00000002-RAM.bin']['sha256']
    native=t.ROOT/'BUILD/native-loader-storage-r2';nm=json.loads((native/'manifest.json').read_text())
    svc=t.ROOT/'BUILD/services-gC-storage-r2';sv=json.loads((svc/'manifest.json').read_text())
    name,item=next((n,v) for n,v in sv['artifacts'].items() if v['variant']=='Full tool RAM packet')
    wb=(svc/name).read_bytes();assert t.sha(wb)==item['sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=t.ROOT/f'output/qualification/device-operations/{board}.json'
    r=dict(board=board,passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_writes=0,RTC_writes=0,
           resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False,yielded_to_collection=False)
    s=None;borrowed=False;cleanup=False;ram=zp=prefix=before=old3=None;origin=None;edu=None;marker=None
    def save():t.save(folder/'report.json',r)
    def mark(**values):
        m=json.loads(mp.read_text());m.update(values);t.save(mp,m)
    def check(label):r['checks'].append(label);save();print('PASS '+board+' '+label,flush=True)
    def boundary():
        if not cleanup and drift_pending():raise CollectionDue('RTC collection priority')
    def cmd(line,tokens=None):
        boundary()
        if line=='YES':assert s.context==YES
        output=s.command(line,tokens);(folder/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:42]}.txt').write_bytes(output)
        return output
    def mon():
        if s.context is None:
            s.link.send(b'\r');s.until((*MONS,t.REC,t.WB,MENU,SM,WORK,YES),seconds=12)
        if s.context==YES:cmd('NO',(MENU,))
        if s.context in (SM,WORK):cmd('Q',(*MONS,MENU))
        if s.context in (MENU,t.WB):cmd('Q',MONS)
        if s.context in MONS and s.context!=t.MON:cmd('B3',(t.MON,))
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def metadata():
        mon();cmd('MAINT LOAD',(t.WB,));cmd('EDU ON');face=cmd('SRAM')
        if b'SSRAM error $01' in face:cmd('SRAM PREP');face=cmd('SRAM')
        assert b'SSRAM PROGRAM:' in face
        parts=[]
        for a in range(0,0x800,64):
            raw=cmd(f'SRAM READ 0 {a:04X}');m=re.search(rb'RAW64 ((?:[0-9A-F]{2} ){64})',raw);assert m
            parts.append(bytes.fromhex(m[1].decode()))
        cmd('Q',MONS);mon();return b''.join(parts)
    def load(data,prompt):
        rec();boundary();s.load(data,t.sha(data),prompt)
    if workbench_only:
        source=Path(carry_from).resolve();assert source.is_relative_to(t.ROOT/'output/qualification')
        prior=json.loads((source/'report.json').read_text());assert prior['passed'] and prior['board']==board
        carried=[v for v in prior['checks'] if v not in ('fresh-owner-escrow-current-MON-and-golden-F','new-WB-refuses-old-loader-and-stops-interactive-storage-BATCH')]
        assert len(carried)==4;r['checks'].extend(carried);r['unchanged_RAM_evidence']=str(source/'report.json')
    save()
    with t.serial_lease(board+'-native-storage-RAM-readonly',timeout=600):
      marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (folder/'serial.jsonl').open('x') as log:
        try:
            boundary();s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);origin=s.context
            mon();assert b'g0000000D / MON B' in cmd('VERSION')
            edu=s.dump(0x6A20,0x6A20)[0];prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
            mark(storage_native_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();t.transport.recovery_usb(s.link);boundary();s.service(reader)
            memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
            old3=s.client.flash(3);assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            assert old3[-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes();(folder/'B3-before.bin').write_bytes(old3)
            for bank in (1,2):
                image=s.client.flash(bank);assert t.sha(image)==marker['current_physical_bank_sha256'][f'B{bank}']
                (folder/f'B{bank}-before.bin').write_bytes(image)
            r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp));check('fresh-owner-escrow-current-MON-and-golden-F')
            rec();before=metadata();(folder/'SPI-metadata-before.bin').write_bytes(before)
            if not workbench_only:
                load(packet,MENU);cmd('PREP');cmd('S',(SM,));assert b'CLK' in cmd('T')
                cmd('Q',(MENU,));cmd('W',(WORK,));assert b'workspace:' in cmd('?')
                cmd('Q',(MENU,));cmd('Q',MONS);mon();check('combined-menu-submenu-Q-and-quiet-MON-return')
                # Use the exact library; only the raw caller's route byte differs.
                signature=bytes.fromhex('A9 FF 8D 02 5B');assert packet[:40].count(signature)==1
                at=packet[:40].index(signature)+1
                for route,prompt in ((3,SM),(4,WORK)):
                    data=bytearray(packet);data[at]=route
                    (folder/f'route-{route}-RAM.bin').write_bytes(data)
                    mon();cmd('B1',(b'B1> ',));cmd('Q',(t.REC,));boundary();s.load(bytes(data),t.sha(bytes(data)),prompt)
                    cmd('!',(MENU,));cmd('UNLOCK',(YES,));cmd('YES',(MENU,));cmd('LOCK',(MENU,));cmd('PREP')
                    cmd('S' if route==3 else 'W',(prompt,));cmd('T' if route==3 else '?')
                    cmd('Q',MONS);assert s.context==b'B1> ';mon()
                check('named-SRAM-WORK-route-controls-locking-and-selected-bank-Q')
            load(wb,t.WB);assert b'STR8-N' in cmd('VERSION')
            for line in ('R SRAM BAD','R WORK BAD','RESTORE SRAM BAD'):
                face=cmd(line);assert b'REFUSED: syntax' in face and b'native loader' not in face
            face=cmd('R SRAM');assert b'REFUSED: native loader' in face
            face=cmd('RESTORE WORK');assert b'REFUSED: native loader' in face
            face=cmd('BATCH R WORK;VERSION',(t.WB,*MONS));assert b'REFUSED:' in face and b'STR8-N 0.1.0' not in face
            mon();assert s.dump(0x7DF9,0x7DF9)==b'\0'
            check('new-WB-refuses-old-loader-and-stops-interactive-storage-BATCH')
            if not workbench_only:
                for kind in ('SRAM','WORK'):
                    name=f'NATIVE-LOADER-probe-{kind}-RAM.bin';data=(native/name).read_bytes();assert t.sha(data)==nm['artifacts'][name]['sha256']
                    rec();boundary();s.load(data,t.sha(data),t.MON);s.context=t.MON
                    check('new-loader-'+kind+'-refuses-uninstalled-payload')
        except CollectionDue as error:
            r.update(yielded_to_collection=True,deferral=str(error));print('YIELD '+board+' RTC priority; restoring owner RAM',flush=True)
        except Exception as error:
            r['error']=repr(error);raise
        finally:
          cleanup=True
          try:
            if borrowed:
                if before is not None:
                    try:
                        after=metadata();(folder/'SPI-metadata-after.bin').write_bytes(after);assert after==before
                        r['SPI_metadata_unchanged']=True
                    except Exception as error:r['metadata_error']=repr(error)
                rec();s.service(reader)
                if old3 is not None:r['B3_unchanged']=s.client.flash(3)==old3
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC;r['owner_RAM_restored']=True
                if origin==t.MON:
                    cmd('B',(t.MON,))
                    if edu!=1:cmd(f'!M 6A20 {edu:02X}')
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(storage_native_RAM_worker_active=False,application_RAM_restore_pending=not restored,
                     application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                     last_storage_native_RAM_trial=str(folder/'report.json'))
            save()
    r['passed']=not r.get('error') and not r.get('metadata_error') and not r['yielded_to_collection'] and len(r['checks'])==6 and r.get('B3_unchanged') and r.get('SPI_metadata_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();print(('PASS ' if r['passed'] else 'DEFERRED ')+board+' native storage RAM trial; port released',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--board',choices=['2512','2609'],required=True);p.add_argument('--out',required=True)
    p.add_argument('--workbench-only',action='store_true');p.add_argument('--carry-from')
    a=p.parse_args();run(a.board,a.out,a.workbench_only,a.carry_from)
