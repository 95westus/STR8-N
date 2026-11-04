"""Bounded temporary SRAM/WORK positive trial; restore owner RAM and yield to RTC collection."""
import argparse,binascii,json,re
from pathlib import Path
import install_2512_native_utilities as d
from serial_test_coordination import drift_pending
t=d.t
MENU=b'STORAGE> ';SM=b'SRAM> ';WORK=b'WORK> '
CONFIRM=b'Type FORMAT SRAM: ';UNLOCK=b'Type YES: '
MONS=tuple(f'B{n}> '.encode() for n in range(4))
class CollectionDue(Exception):pass

def run(board,out,lease_timeout=30,resume_before=None,verify_after=None,work_only=False):
    folder=Path(out).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    (folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    build=t.ROOT/'BUILD/sram-work-g1-ram-r2';manifest=json.loads((build/'manifest.json').read_text())
    packet=(build/'STR8N-SRAM-WORK-g00000001-RAM.bin').read_bytes()
    assert t.sha(packet)==manifest['artifacts']['STR8N-SRAM-WORK-g00000001-RAM.bin']['sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    pbdir=t.ROOT/'BUILD/SRAM-reader-current-r2'
    pbplan=json.loads((pbdir/'manifest.json').read_text())
    pb=(pbdir/pbplan['filename']).read_bytes()
    assert t.sha(pb)==pbplan['sha256']=='12b4836319b6bf77e6031079c18f856df94bb52779a837c5f05be164040b9126'
    sy=json.loads((build/'symbols.json').read_text());mp=t.ROOT/f'output/qualification/device-operations/{board}.json'
    r=dict(board=board,passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_data_writes=0,
           WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,
           owner_RAM_restored=False,owner_ZP_restored=False,yielded_to_collection=False)
    s=None;borrowed=False;ram=zp=prefix=old3=before=None;origin=None;cleanup=False;meta_pending=False;edu=None;spi_dirty=False
    verify_priority=False
    def save():t.save(folder/'report.json',r)
    def mark(**kw):
        m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def check(label):r['checks'].append(label);save();print('PASS '+board+' '+label,flush=True)
    def boundary():
        if (not cleanup or verify_priority) and drift_pending():raise CollectionDue('RTC collection requested priority')
    def cmd(text,tokens=None):
        boundary();assert text!='FORMAT SRAM'
        if text=='YES':assert s.context==UNLOCK
        out=s.command(text,tokens)
        label=re.sub('[^A-Za-z0-9_-]','_',text)[:48]
        (folder/f'{s.counter:04d}-{label}.txt').write_bytes(out);return out
    def mon():
        if s.context is None:s.until((*MONS,t.REC,MENU,SM,WORK,t.WB,CONFIRM,UNLOCK,t.PB),seconds=8)
        if s.context==t.PB:s.link.send(b'Q');s.until(MONS)
        if s.context==UNLOCK:cmd('NO',(MENU,))
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
    resume=bytearray()
    if resume_before:
        prior_folder=Path(resume_before).resolve();assert prior_folder.is_relative_to(t.ROOT/'output/qualification')
        prior=json.loads((prior_folder/'report.json').read_text())
        assert prior['board']==board
        assert prior['owner_RAM_restored'] and prior['owner_ZP_restored'] and prior['B3_unchanged']
        if (prior_folder/'SRAM-metadata-before.bin').exists():
            assert prior.get('all_test_blocks_restored') and not prior.get('SPI_restoration_error')
            resume.extend((prior_folder/'SRAM-metadata-before.bin').read_bytes())
        else:
            assert prior['SRAM_data_writes']==prior['WORKSPACE_writes']==0
            rows=[json.loads(line) for line in (prior_folder/'serial.jsonl').read_text().splitlines()]
            rx=b''.join(bytes.fromhex(row['hex']) for row in rows if row['direction']=='RX')
            for match in re.findall(rb'D([0-9A-F]{138})\r?\n',rx):
                frame=bytes.fromhex(match.decode())
                if int.from_bytes(frame[:3],'big')!=len(resume):continue
                assert binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big')
                resume.extend(frame[3:-2])
        assert 0<len(resume)<=0x20000
        (folder/'before-resumed-prefix.bin').write_bytes(resume)
        r.update(before_resumed_from=str(prior_folder),before_resumed_bytes=len(resume))
    if work_only:
        assert resume_before and any(v.startswith('positive-SRAM-') for v in prior['checks'])
        r['SRAM_positive_evidence_source']=str(prior_folder/'report.json')
        check('positive-SRAM-carried-forward-from-restored-trial')
    def metadata(use_resume=False):
        mon();cmd('MAINT LOAD',(t.WB,));cmd('EDU ON')
        mounted=cmd('SRAM')
        if b'SSRAM error $01' in mounted:cmd('SRAM PREP');mounted=cmd('SRAM')
        assert b'SSRAM PROGRAM:' in mounted,mounted
        first=cmd('SRAM READ 0 0000');m=re.search(rb'RAW64 ((?:[0-9A-F]{2} ){64})',first);assert m
        independent_header=bytes.fromhex(m[1].decode())
        cmd('Q',MONS);rec();boundary();s.load(pb,t.sha(pb),t.PB)
        prefix=resume if use_resume else bytearray()
        parts=bytearray(prefix)
        # Re-admit every previously read block that this trial could change.
        # Other frames continue the non-mutating snapshot across RTC leases.
        addresses=([a for a in allowed if a<len(prefix)] if prefix else [])+list(range(len(prefix),0x20000,64))
        for a in addresses:
            boundary();fields=a.to_bytes(3,'big')
            s.link.send(b'R'+fields.hex().upper().encode()+b'\r')
            data=s.until((t.PB,));m=re.findall(rb'D([0-9A-F]{138})\r?\n',data);assert len(m)==1,data
            frame=bytes.fromhex(m[0].decode());assert frame[:3]==fields
            assert binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big')
            data=frame[3:-2]
            if a<len(prefix):assert data==prefix[a:a+64],'SRAM changed between read-only capture windows'
            else:assert a==len(parts);parts.extend(data)
            if a==0:assert data==independent_header,'PB read differs from installed read-only path'
            if (a+64)%32768==0:print(f'SRAM capture: {a+64}/131072 bytes',flush=True)
        mon();assert len(parts)==0x20000;return bytes(parts)
    def api(kind,request,expected,pointer=0x300,write=False):
        mon();assert s.dump(sy['SW_UNLOCKED'],sy['SW_UNLOCKED'])==b'\0'
        if pointer==0x300:s.modify(pointer,request)
        target=0x2003 if kind=='SRAM' else 0x2006
        if write:s.modify(sy['SW_UNLOCKED'],b'\x01')
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
    allowed=list(range(0,0xC00,64))+list(range(0x10000,0x10400,64))
    def raw(address,data=None):
        # Test writes are restricted to four backed-up KiB. Restoration only
        # publishes the exact original bytes, never synthesized replacements.
        assert address in allowed and address%64==0
        mon();desc=bytearray(16);desc[0]=2 if data is not None else 1
        desc[2:5]=address.to_bytes(3,'little');desc[5:7]=(0x500).to_bytes(2,'little');desc[7]=64
        if data is not None:
            assert len(data)==64;s.modify(0x500,data)
        s.modify(0x6650,desc);s.modify(sy['SW_UNLOCKED'],b'\x01' if data is not None else b'\0')
        target=sy['SW_TRANSFER'];ret=sy['SW_RETURN']
        code=bytes((0x20,target&255,target>>8,0x8D,0x40,3,0x4C,ret&255,ret>>8))
        s.modify(0x380,code);cmd('G 0380',MONS);mon()
        assert s.dump(0x340,0x340)==b'\0'
        return s.dump(0x500,0x53F)
    def restore_spi():
        nonlocal spi_dirty
        if not spi_dirty:return
        rewritten=[]
        for a in allowed:
            original=before[a:a+64]
            if raw(a)!=original:
                raw(a,original);assert raw(a)==original;rewritten.append(f'{a:05X}')
        spi_dirty=False;r['all_test_blocks_restored']=True
        r.setdefault('restored_blocks_by_phase',[]).append(rewritten)
        mark(SRAM_WORK_SPI_restore_pending=False)
        check('all-4096-temporary-SRAM-bytes-restored-and-read-back')
    def positive_steps():
        nonlocal spi_dirty
        # Qualify only the freshly captured existing SS1/64KiB layout.
        from program_format import inspect
        layout=inspect(before);assert layout['format']=='SS1' and layout['boundary']=='10000'
        assert len(layout['free_slots'])>=3
        pages=[int(p,16) for p in layout['free_pages']]
        assert len(pages)>=2 and all(8<=p<12 for p in pages[:2])
        assert b'PVFY' not in before[:0x240]
        def mut(kind,request,expected=0):return api(kind,request,expected,write=True)
        if not work_only:
            spi_dirty=True;r['all_test_blocks_restored']=False;mark(SRAM_WORK_SPI_restore_pending=True);save()
            r['SRAM_data_writes']='temporary PROGRAM/metadata writes; exact blocks restored'
            def store(data):
                s.modify(0x1000,data)
                a=bytearray(req(1,'PVFY',source=(0x1000,0x1007)));mut('SRAM',bytes(a))
            one=bytes.fromhex('A9 31 20 6D 7E 4C 67 7E');two=bytes.fromhex('A9 32 20 6D 7E 4C 67 7E')
            store(one);store(two);s.modify(0x1000,b'\xA5'*8)
            api('SRAM',req(2,'PVFY'),0);assert s.dump(0x1000,0x1007)==two
            mut('SRAM',req(5));mut('SRAM',req(4,'PVFY'));api('SRAM',req(2,'PVFY'),0x42)
            mut('SRAM',req(5));mut('SRAM',req(6,key='FORMAT!!'))
            check('positive-SRAM-save-latest-restore-reclaim-delete-and-format')
            restore_spi()
        # Restore the original SS1 records before testing its non-destructive
        # upgrade. The WORK payload fixture is confined to10000-103FF.
        spi_dirty=True;r['all_test_blocks_restored']=False;mark(SRAM_WORK_SPI_restore_pending=True);save()
        r['WORKSPACE_writes']='temporary 10000-103FF allowance; 64-byte positive I/O'
        mut('WORK',req(7,key='UPGRADE!'));assert api('WORK',req(0),0)[22]==0
        a=bytearray(32);a[0]=1;a[2:4]=(0xCA01).to_bytes(2,'little');a[18:21]=(256).to_bytes(3,'little')
        handle=bytearray(mut('WORK',bytes(a)))
        claim_address=0x300+32*handle[4]
        block=raw(claim_address&~63);offset=claim_address&63;committed=block[offset:offset+32]
        assert committed[:3]==b'WC\x01' and committed[31]==0xA5
        assert int.from_bytes(committed[12:15],'little')==0x10000
        pattern=bytes(range(64));s.modify(0x500,pattern)
        def io(op,buffer,offset=0,count=64,expected=0,change_owner=False):
            a=handle.copy();a[0]=op;a[12:15]=offset.to_bytes(3,'little');a[15]=count;a[16:18]=buffer.to_bytes(2,'little')
            if change_owner:a[2]^=1
            return mut('WORK',bytes(a),expected)
        io(4,0x500);s.modify(0x580,b'\xA5'*64);io(3,0x580);assert s.dump(0x580,0x5BF)==pattern
        io(3,0x580,expected=0x4B,change_owner=True);io(3,0x580,offset=255,count=2,expected=0x44)
        io(3,0x300,expected=0x44)
        a=handle.copy();a[0]=2;mut('WORK',bytes(a));io(3,0x580,expected=0x4B)
        def resize(units,expected=0):
            a=bytearray(req(5,key='RESIZE!!'));a[21]=units;return mut('WORK',bytes(a),expected)
        resize(3);assert api('WORK',req(0),0)[21]==3
        a=bytearray(32);a[0]=1;a[2:4]=(0xCA02).to_bytes(2,'little');a[18:21]=(256).to_bytes(3,'little')
        conflict=bytearray(mut('WORK',bytes(a)));resize(4,0x4A)
        conflict[0]=2;mut('WORK',bytes(conflict));resize(4)
        # Exercise a surviving fallback header without a physical power cut.
        primary=raw(0);bad=bytearray(primary);bad[63]=0;raw(0,bytes(bad))
        assert api('WORK',req(0),0)[23]==1
        mut('WORK',req(8,key='REPAIR!!'));assert api('WORK',req(0),0)[23]==0
        mut('WORK',req(6,key='FORMAT!!'));mut('SRAM',req(6,key='FORMAT!!'),0x49)
        check('positive-WORK-upgrade-claim-write-read-release-bounds-resize-conflict-repair-and-format')
    save()
    try:
      with t.serial_lease(board+'-SRAM-WORK-RAM-temporary-writes',timeout=lease_timeout):
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
            mark(sram_work_positive_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();t.transport.recovery_usb(s.link);boundary();s.service(reader)
            memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
            old3=s.client.flash(3);assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            assert old3[-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
            (folder/'B3-before.bin').write_bytes(old3)
            r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp));check('fresh-owner-escrow-current-MON-and-golden-F-admitted')
            if verify_after:
                source=Path(verify_after).resolve();assert source.is_relative_to(t.ROOT/'output/qualification')
                prior=json.loads((source/'report.json').read_text())
                assert prior['board']==board and prior['all_test_blocks_restored'] and not prior.get('SPI_restoration_error')
                assert prior['owner_RAM_restored'] and prior['owner_ZP_restored'] and prior['B3_unchanged']
                assert not prior.get('error') and prior['normal_unlock_confirmation_passed']
                assert any(v.startswith('positive-SRAM-') for v in prior['checks']) and any(v.startswith('positive-WORK-') for v in prior['checks'])
                assert old3==(source/'B3-before.bin').read_bytes()
                before=(source/'SRAM-metadata-before.bin').read_bytes();assert len(before)==0x20000
                r['positive_evidence_source']=str(source/'report.json');meta_pending=True
            else:
                if resume_before:assert old3==(prior_folder/'B3-before.bin').read_bytes()
                rec();before=metadata(use_resume=True);(folder/'SRAM-metadata-before.bin').write_bytes(before);meta_pending=True
                check('fresh-complete-131072-byte-SRAM-backup')
                rec();boundary();s.load(packet,t.sha(packet),MENU)
                cmd('PREP');cmd('UNLOCK',(UNLOCK,));cmd('YES',(MENU,));cmd('LOCK',(MENU,));cmd('Q',MONS);mon()
                r['normal_unlock_confirmation_passed']=True
                positive_steps()
          except CollectionDue as e:
            r.update(yielded_to_collection=True,deferral=str(e));print('YIELD '+board+' RTC priority; restoring owner RAM',flush=True)
          except Exception as e:
            r['error']=repr(e);raise
          finally:
            cleanup=True
            try:
              if borrowed:
                if spi_dirty:
                    try:restore_spi()
                    except Exception as e:r['SPI_restoration_error']=repr(e)
                if meta_pending:
                    try:
                        verify_priority=True
                        after=metadata();(folder/'SRAM-metadata-after.bin').write_bytes(after)
                        assert after==before,'Full SRAM differs from the fresh original capture'
                        check('entire-131072-byte-SRAM-exactly-restored')
                        mark(SRAM_WORK_SPI_restore_pending=False)
                    except CollectionDue as e:
                        r.update(yielded_to_collection=True,full_SRAM_verification_pending=True,deferral=str(e))
                    except Exception as e:
                        r['metadata_verification_error']=repr(e)
                    finally:verify_priority=False
                rec();s.service(reader)
                if old3 is not None:
                    final3=s.client.flash(3);r['B3_unchanged']=final3==old3
                    if final3!=old3:r['flash_verification_error']='B3 changed during RAM trial'
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
                mark(sram_work_positive_worker_active=False,application_RAM_restore_pending=not restored,
                    application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored and not spi_dirty else True,
                    last_SRAM_WORK_positive_trial=str(folder/'report.json'))
              save()
    except TimeoutError as e:
        if not borrowed:r.update(deferral=str(e),board_touched=s is not None)
        else:r['error']=repr(e)
        save();raise
    r['passed']=not r.get('error') and not r.get('SPI_restoration_error') and not r.get('metadata_verification_error') and not r['yielded_to_collection'] and len(r['checks'])==(2 if verify_after else 6 if work_only else 7) and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r.get('B3_unchanged',False)
    save();print(('PASS ' if r['passed'] else 'DEFERRED ')+board+' SRAM/WORK temporary-write trial; port released',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True);p.add_argument('--out',required=True)
    p.add_argument('--lease-timeout',type=int,default=30)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--resume-before',help='Continue a restored prior capture; re-admit all allowed blocks')
    mode.add_argument('--verify-after',help='Read-only whole-SRAM comparison after a restored positive trial')
    p.add_argument('--work-only',action='store_true',help='Carry forward the passed SRAM steps from --resume-before')
    a=p.parse_args();run(a.board,a.out,a.lease_timeout,a.resume_before,a.verify_after,a.work_only)
