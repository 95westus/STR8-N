"""Read-only SRAM/WORK RAM trial; restore owner RAM and yield to RTC collection."""
import argparse,json,re
from pathlib import Path
import install_2512_native_utilities as d
from serial_test_coordination import drift_pending
t=d.t
MENU=b'STORAGE> ';SM=b'SRAM> ';WORK=b'WORK> '
CONFIRM=b'Type FORMAT SRAM: '
MONS=tuple(f'B{n}> '.encode() for n in range(4))
class CollectionDue(Exception):pass

def run(board,out,lease_timeout=30):
    folder=Path(out).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    (folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    build=t.ROOT/'BUILD/sram-work-g1-ram-r2';manifest=json.loads((build/'manifest.json').read_text())
    packet=(build/'STR8N-SRAM-WORK-g00000001-RAM.bin').read_bytes()
    assert t.sha(packet)==manifest['artifacts']['STR8N-SRAM-WORK-g00000001-RAM.bin']['sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    sy=json.loads((build/'symbols.json').read_text());mp=t.ROOT/f'output/qualification/device-operations/{board}.json'
    r=dict(board=board,passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_data_writes=0,
           WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,
           owner_RAM_restored=False,owner_ZP_restored=False,yielded_to_collection=False)
    s=None;borrowed=False;ram=zp=prefix=old3=before=None;origin=None;cleanup=False;meta_pending=False;edu=None
    def save():t.save(folder/'report.json',r)
    def mark(**kw):
        m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def check(label):r['checks'].append(label);save();print('PASS '+board+' '+label,flush=True)
    def boundary():
        if not cleanup and drift_pending():raise CollectionDue('RTC collection requested priority')
    def cmd(text,tokens=None):
        boundary();assert text not in ('UNLOCK','YES','FORMAT SRAM')
        out=s.command(text,tokens)
        label=re.sub('[^A-Za-z0-9_-]','_',text)[:48]
        (folder/f'{s.counter:04d}-{label}.txt').write_bytes(out);return out
    def mon():
        if s.context is None:s.until((*MONS,t.REC,MENU,SM,WORK,t.WB,CONFIRM),seconds=8)
        if s.context==CONFIRM:cmd('NO',(SM,WORK))
        if s.context in (SM,WORK):cmd('Q',(MENU,))
        if s.context==MENU:cmd('Q',MONS)
        if s.context==t.WB:cmd('Q',MONS)
        if s.context in MONS and s.context!=t.MON:cmd('B3',(t.MON,))
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON,'Unknown prompt; no blind recovery'
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def metadata():
        mon();cmd('MAINT LOAD',(t.WB,));cmd('EDU ON')
        mounted=cmd('SRAM')
        if b'SSRAM error $01' in mounted:cmd('SRAM PREP');mounted=cmd('SRAM')
        assert b'SSRAM PROGRAM:' in mounted,mounted
        parts=[]
        for a in range(0,0x800,64):
            data=cmd(f'SRAM READ 0 {a:04X}')
            m=re.search(rb'RAW64 ((?:[0-9A-F]{2} ){64})',data);assert m,data
            parts.append(bytes.fromhex(m[1].decode()))
        cmd('Q',MONS);mon();return b''.join(parts)
    def api(kind,request,expected,pointer=0x300):
        mon();assert s.dump(sy['SW_UNLOCKED'],sy['SW_UNLOCKED'])==b'\0'
        if pointer==0x300:s.modify(pointer,request)
        target=0x2003 if kind=='SRAM' else 0x2006
        code=bytes((0xA9,pointer&255,0xA2,pointer>>8,0x20,target&255,target>>8,
                    0x8D,0x40,0x03,0x08,0x68,0x8D,0x41,0x03,0x4C,sy['SW_RETURN']&255,sy['SW_RETURN']>>8))
        s.modify(0x380,code);boundary();cmd('G 0380',MONS);mon()
        result=s.dump(0x340,0x341);reply=s.dump(0x300,0x31F)
        r.setdefault('API_results',[]).append(dict(kind=kind,op=request[0],pointer=f'{pointer:04X}',status=result[0],carry=result[1]&1,reply_hex=reply.hex()));save()
        assert result[0]==expected and (result[1]&1)==(expected==0),(kind,request[0],result)
        return reply
    def req(op,name='',key='',source=None):
        a=bytearray(32);a[0]=op;a[8:8+len(name)]=name.encode();a[24:24+len(key)]=key.encode()
        if source:a[2:4]=source[0].to_bytes(2,'little');a[4:6]=source[1].to_bytes(2,'little')
        return bytes(a)
    save()
    try:
      with t.serial_lease(board+'-SRAM-WORK-RAM-readonly',timeout=lease_timeout):
        marker=json.loads(mp.read_text())
        assert marker['monitor_generation']=='0000000D' and marker['application_ram_restored']
        assert not marker['application_RAM_restore_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        with (folder/'serial.jsonl').open('x') as log:
          try:
            boundary();s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);origin=s.context
            mon();face=cmd('VERSION');assert b'g0000000D / MON B' in face
            edu=s.dump(0x6A20,0x6A20)[0];r['EDU_session_before']=edu
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
            mark(sram_work_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();t.transport.recovery_usb(s.link);boundary();s.service(reader)
            memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
            old3=s.client.flash(3);assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            assert old3[-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
            (folder/'B3-before.bin').write_bytes(old3)
            r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp));check('fresh-owner-escrow-current-MON-and-golden-F-admitted')
            rec();before=metadata();(folder/'SRAM-metadata-before.bin').write_bytes(before);meta_pending=True
            check('fresh-2K-storage-metadata-captured-read-only')
            rec();boundary();s.load(packet,t.sha(packet),MENU)
            cmd('PREP');cmd('S',(SM,));table=cmd('T');assert b'CLK' in table,table
            cmd('F',(CONFIRM,));cmd('NO',(SM,));cmd('Q',(MENU,))
            cmd('W',(WORK,));capacity=cmd('?');assert b'Programs:' in capacity and b'workspace:' in capacity,capacity
            cmd('F',(CONFIRM,));cmd('NO',(WORK,));cmd('Q',(MENU,));cmd('Q',MONS);mon()
            check('real-SRAM-Table-WORK-capacity-format-cancellation-and-quiet-return')
            api('SRAM',req(0),0)
            api('SRAM',req(0),0x44,pointer=0x1FF0)
            api('SRAM',req(1,'ROTEST',source=(0x1FF0,0x200F)),0x44)
            api('SRAM',req(4,'CLK'),0x4C)
            api('SRAM',req(6),0x44)
            check('SRAM-API-query-pointer-source-key-guards-and-locked-delete')
            capacity=api('WORK',req(0),0)
            assert capacity[21]==4 and capacity[22]==1,capacity
            api('WORK',req(9),0x44)
            api('WORK',req(0),0x44,pointer=0x1FF0)
            api('WORK',req(1),0x49)
            api('WORK',req(6,key='FORMAT!!'),0x4C)
            check('WORK-API-capacity-bounds-SS1-upgrade-gate-and-locked-format')
          except CollectionDue as e:
            r.update(yielded_to_collection=True,deferral=str(e));print('YIELD '+board+' RTC priority; restoring owner RAM',flush=True)
          except Exception as e:
            r['error']=repr(e);raise
          finally:
            cleanup=True
            try:
              if borrowed:
                if meta_pending:
                    try:
                        after=metadata();(folder/'SRAM-metadata-after.bin').write_bytes(after)
                        assert after==before,'Storage metadata changed in read-only trial'
                        check('complete-2K-storage-metadata-unchanged')
                    except Exception as e:
                        r['metadata_verification_error']=repr(e)
                rec();s.service(reader)
                if old3 is not None:
                    final3=s.client.flash(3);r['B3_unchanged']=final3==old3
                    if final3!=old3:r['flash_verification_error']='B3 changed during read-only trial'
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
                mark(sram_work_RAM_worker_active=False,application_RAM_restore_pending=not restored,
                    application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                    last_SRAM_WORK_RAM_trial=str(folder/'report.json'))
              save()
    except TimeoutError as e:
        if not borrowed:r.update(deferral=str(e),board_touched=s is not None)
        else:r['error']=repr(e)
        save();raise
    r['passed']=not r.get('error') and not r.get('metadata_verification_error') and not r['yielded_to_collection'] and len(r['checks'])==6 and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r.get('B3_unchanged',False)
    save();print(('PASS ' if r['passed'] else 'DEFERRED ')+board+' SRAM/WORK RAM read-only trial; port released',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True);p.add_argument('--out',required=True)
    p.add_argument('--lease-timeout',type=int,default=30)
    a=p.parse_args();run(a.board,a.out,a.lease_timeout)
