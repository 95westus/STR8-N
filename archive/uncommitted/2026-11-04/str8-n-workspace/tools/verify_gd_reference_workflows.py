"""Real current-MON operator checks, temporary owner RAM only; no NVM writes.

Baseline boards are deliberately absent. STORE/FLASH setting prompts are
cancelled; only BM writes whose destination is R (CPU RAM) receive Y.
"""
import argparse,binascii,json,re,time
from pathlib import Path
import install_2512_native_utilities as d
from rtc_mon_ui1_gd_trim import parse_time

t=d.t;BM=b'BM> ';CONFIRM=b'WRITE? TYPE Y> ';YES=b'type YES> '
CLOCK_YES=b'Type YES to confirm: '
MONS=tuple(f'B{n}> '.encode() for n in range(4))


def run(board,folder,accepted_from=None):
    folder=Path(folder).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    (folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    markerpath=t.ROOT/f'output/qualification/device-operations/{board}.json'
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    r=dict(board=board,passed=False,checks=[],failures=[],observations={},flash_writes=0,journal_writes=0,
           RTC_SET=0,trim_writes=0,PF_ACK=0,SRAM_data_writes=0,WORKSPACE_writes=0,
           firmware_builds=0,CPU_simulations=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
    accepted=[]
    if accepted_from:
        r['accepted_from']=[]
        for priorpath in accepted_from:
            prior=json.loads(Path(priorpath).read_text())
            assert prior['board']==board and prior['owner_RAM_restored'] and prior['owner_ZP_restored']
            assert all(prior[k]==0 for k in ('flash_writes','journal_writes','SRAM_data_writes','RTC_SET'))
            accepted.extend(prior['checks']);r['accepted_from'].append(str(Path(priorpath).resolve()))
    s=None;borrowed=False;ram=zp=prefix=None;original=None;edu=None;old3=None
    def save():t.save(folder/'report.json',r)
    def mark(**kw):
        m=json.loads(markerpath.read_text());m.update(kw);t.save(markerpath,m)
    def cmd(text,tokens=None):
        # Wide PROGRAM load-only returns directly to the selected-bank MON.
        if tokens and t.MON in tokens:tokens=tuple(dict.fromkeys((*tokens,*MONS)))
        out=s.command(text,tokens)
        label=re.sub('[^A-Za-z0-9_-]','_',text)[:60]
        (folder/f'{s.counter:04d}-{label}.txt').write_bytes(out)
        return out
    def monitor():
        if s.context is None:s.until((*MONS,t.REC),seconds=5)
        if s.context in (YES,CLOCK_YES):
            cmd('NO',(d.FT if s.context==YES else t.CLOCK,))
        if s.context in (BM,CONFIRM,b'Type YES: '):
            if s.context!=BM:cmd('NO',(BM,))
            cmd('Q',MONS)
        if s.context in (d.FT,t.CLOCK,t.WB):cmd('Q',MONS)
        if s.context in (b'B0> ',b'B1> ',b'B2> '):cmd('B3',(t.MON,))
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON,'Unknown state; no blind recovery'
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:monitor();cmd('Q',(t.REC,))
        assert s.context==t.REC
    def step(label,fn):
        if label in accepted:
            r.setdefault('carried_checks',[]).append(label);save();return
        try:
            fn();r['checks'].append(label);print('PASS '+board+' '+label,flush=True)
        except AssertionError as e:
            r['failures'].append(dict(check=label,error=str(e)));print('FAIL '+board+' '+label+': '+str(e)[:160],flush=True)
        save()
    def bmwrite(text):
        # Hard whitelist: no confirmation of a flash destination is possible.
        assert text.startswith(('W R ','C R ')) and (' R ' in text[4:] if text.startswith('C ') else True)
        cmd(text,(CONFIRM,));assert b'VERIFIED' in cmd('Y',(BM,))
    def bmcrc():
        out=cmd('K');m=re.search(rb'CRC16-CCITT-FALSE ([0-9A-F]{4})',out);assert m,out
        return int(m[1],16)
    def bench():
        monitor();out=cmd('MAINT LOAD',(t.WB,t.MON));assert s.context==t.WB and b'g0000000C' in out,out
    def mount():
        cmd('EDU ON');out=cmd('SRAM')
        if b'SSRAM error $01' in out:
            assert b'Disabled CB flags acknowledged; no SPI clocks' in cmd('SRAM PREP')
            r['observations']['disabled_CB_flags_acknowledged']=True;out=cmd('SRAM')
        assert b'SSRAM PROGRAM:' in out,out
        return out
    def raw64(a):
        out=cmd(f'SRAM READ {a>>16} {a&65535:04X}')
        m=re.search(rb'RAW64 ((?:[0-9A-F]{2} ){64})',out);assert m,out
        return bytes.fromhex(m[1].decode())
    save()
    # The driver runs in a yielded background session. This bounded wait
    # preserves RTC priority without blocking conversation or opening a port.
    with t.serial_lease(board+'-reference-feature-verification',timeout=600):
        marker=json.loads(markerpath.read_text())
        assert marker['monitor_generation']=='0000000D' and marker['application_ram_restored']
        assert not marker['application_RAM_restore_pending']
        assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
        with (folder/'serial.jsonl').open('x') as log:
            try:
                s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);original=s.context
                if original==t.REC:cmd('B',(t.MON,))
                face=cmd('VERSION');assert b'g0000000D / MON B' in face
                edu=s.dump(0x6A20,0x6A20)[0]
                prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
                (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
                mark(reference_verify_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True)
                borrowed=True;rec();t.transport.recovery_usb(s.link);s.service(reader)
                memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
                ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
                old3=s.client.flash(3);old2=s.client.flash(2)
                (folder/'B3-before.bin').write_bytes(old3);(folder/'B2-current.bin').write_bytes(old2)
                if t.sha(old3)!=marker['current_physical_bank_sha256']['B3']:
                    # A valid new TZ append changes data, not installed code.
                    # Preserve it and attest every other byte against the last
                    # accepted image. Other drift remains a hard stop.
                    prior=(Path(marker['last_MON_trim_install']).parent/'B3-after.bin').read_bytes()
                    assert t.sha(prior)==marker['current_physical_bank_sha256']['B3']
                    assert old3[:0x1C00]==prior[:0x1C00] and old3[0x2000:]==prior[0x2000:]
                    changes=[]
                    for off in range(0x1C00,0x2000,32):
                        before,after=prior[off:off+32],old3[off:off+32]
                        if before==after:continue
                        assert before==b'\xff'*32 and after[:4]==b'TZ\x01\x00' and after[31]==0
                        assert binascii.crc_hqx(after[:28],65535)==int.from_bytes(after[28:30],'little')
                        changes.append(dict(address=f'{off+0x8000:04X}',kind='TZ',
                            sequence=int.from_bytes(after[4:8],'little'),
                            display_offset_minutes=int.from_bytes(after[8:10],'little',signed=True)))
                    assert changes
                    r['observations']['preexisting_TZ_appends_preserved']=changes
                assert t.sha(old2)==marker['current_physical_bank_sha256']['B2']
                assert old3[-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
                r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp),B2_sha256=t.sha(old2),
                         journal=t.classify_journal(old3),EDU_session_before=edu)
                r['checks'].append('fresh-owner-current-gD-tools-and-golden-F-admission');save()
                rec();monitor()
                def identity():
                    face=cmd('VERSION');assert ('Board: '+board).encode() in face
                    assert b'MONITOR A gen 0000000D VALID' in face and b'MONITOR B gen 0000000D VALID default' in face
                    assert b'RAM $0200-$66FF' in face and b'Battery:' in face and b'FLASH:' in face
                    row=parse_time(cmd('TIME'));r['observations']['TIME_before']=row
                step('VERSION-rich-status-and-live-TIME-trim',identity)
                def core():
                    monitor();data=bytes.fromhex('12 34 56 78 9A BC DE F0')
                    cmd('M 0300 '+data.hex(' ').upper());assert s.dump(0x300,0x307)==data
                    assert b'REFUSED' not in cmd('!M 0307 A5');assert s.dump(0x307,0x307)==b'\xA5'
                    for bank in (0,1,2,3):
                        token=f'B{bank}> '.encode();out=cmd('B'+str(bank),(token,))
                        assert f'Data bank B{bank}'.encode() in out
                        cmd('D 8000 800F')
                    # Validated gD UI quiet vector; no unknown owner code runs.
                    quiet=old3[0x302A:0x302C];assert 0xB080<=int.from_bytes(quiet,'little')<0xC000
                    code=bytes.fromhex('A9 47 20 6D 7E 4C')+quiet
                    cmd('M 0320 '+code.hex(' ').upper());out=cmd('G 0320',(t.MON,));assert b'G' in out
                step('Dump-Modify-force-RAM-bank-select-Go-and-return',core)
                def maps():
                    monitor()
                    for text in ('M1','M2','M3'):assert b'B0' in cmd(text)
                    out=cmd('W');rows=re.findall(rb'^B([0-3]) ((?:[0-9A-F]{6} ){8})',out,re.M)
                    assert len(rows)==4,out
                    counts=[int(v,16) for _,body in rows for v in body.split()]
                    assert counts==r['journal']['counts']
                step('M1-M2-M3-and-all32-W-counters',maps)
                def maint():
                    monitor();out=cmd('R MAINT',(BM,));assert b'BANK MAINT 2.4' in out
                    assert ('Board: '+board).encode() in cmd('NAME')
                    cmd('NAME PVFY',(b'Type YES: ',));cmd('NO',(BM,))
                    assert b'DEFAULT=B' in cmd('BOOT')
                    assert b'B1:8000 2000-42FC 22FD C MAINT' in cmd('TABLE')
                    assert b'B2:B000' in cmd('T 1-2')
                    cmd('N 1000 FF');cmd('P 0 12 34 56');cmd('F 10-1F A5')
                    target=bytearray(b'\xff'*4096);target[:3]=b'\x12\x34\x56';target[16:32]=b'\xA5'*16
                    expected=binascii.crc_hqx(target,65535);assert bmcrc()==expected
                    assert b'12 34 56' in cmd('D 0-1F')
                    for text in ('M1','M2','M3','VERSION','TABLE 1'):cmd(text);assert bmcrc()==expected
                    cmd('R 3 8000-80FF');bmwrite('W R 1300');bmwrite('C R 1300-13BF R 1340')
                    bmwrite('C R 1300-133F R 1500');assert b'MATCH' in cmd('V R 1300-133F R 1500')
                    cmd('N 1 EF');bmwrite('W R 1500');assert b'DIFFERENT AT DEST 1500' in cmd('V R 1300-133F R 1500')
                    for text in ('E 3 F','E 3 C-D','E 2 8','E 1 8-A'):
                        out=cmd(text,(BM,));assert b'WRITE? TYPE Y' not in out
                    cmd('Q',(t.MON,));target=bytearray(old3[:256]);target[64:]=old3[:192]
                    assert s.dump(0x1300,0x13FF)==target
                step('BANK-MAINT-naming-Table-4K-editor-copy-compare-guards-Q',maint)
                def clock():
                    monitor();out=cmd('R CLOCK',(t.CLOCK,));assert b'CLOCK 1.10 / BASE1 g1' in out
                    for text in ('TIME','STATUS','TRIM','HISTORY','STATS','EUI','OFFSET','BATTERY','VERSION'):
                        out=cmd(text);assert b'Invalid command' not in out and b'Services unavailable' not in out,text
                        if text=='STATUS':assert b'RTC registers (raw):' in out and b'Power-fail latched:' in out
                        if text=='TIME':assert b'UTC:' in out and b'Local:' in out
                    assert b'Invalid command/date' in cmd('SET 2026-02-30 12:00:00')
                    for text in ('SET 2028-02-29 12:34:56','OFFSET +00:00','TRIM 1'):
                        cmd(text,(CLOCK_YES,));assert b'Canceled' in cmd('NO',(t.CLOCK,))
                    cmd('Q',(t.MON,));assert parse_time(cmd('TIME'))['trim_raw']==r['observations']['TIME_before']['trim_raw']
                step('CLOCK-detailed-queries-invalid-date-cancelled-settings-and-Q',clock)
                def flash():
                    monitor();cmd('R FLASH',(d.FT,));cmd('VERSION');cmd('BANK 0');cmd('READ 9000')
                    view=cmd('VIEW 000');m=re.search(rb'0000  ([0-9A-F]{2})',view);assert m,view
                    old=int(m[1],16);new=old^0x55;cmd(f'EDIT 000 {new:02X}')
                    assert f'0000  {new:02X}'.encode() in cmd('VIEW 000')
                    cmd('WRITE',(YES,));assert b'Canceled' in cmd('NO',(d.FT,))
                    cmd('READ 9000');assert f'0000  {old:02X}'.encode() in cmd('VIEW 000')
                    cmd('ERASE 9000',(YES,));assert b'Canceled' in cmd('NO',(d.FT,))
                    assert b'DEFAULT=B' in cmd('BOOT')
                    cmd('Q',(t.MON,))
                step('FLASH-read-edit-buffer-cancelled-write-erase-BOOT-and-Q',flash)
                def storage():
                    bench();mount();before=b''.join(raw64(a) for a in range(0,0x240,64))
                    (folder/'PROGRAM-metadata-before.bin').write_bytes(before)
                    table=cmd('TABLE P');r['observations']['PROGRAM_table']=table.decode('ascii')
                    matches=re.findall(rb'^P:[^\r\n]*',table,re.M)
                    assert matches,'No existing PROGRAM record for nonmutating RESTORE check'
                    for text in ('TABLE 1','TABLE','WORK','R EDU','RESTORE SRAM','R WORK'):
                        out=cmd(text);assert b'REFUSED' not in out and b'SSRAM error' not in out,text
                    # Demonstrate Store allocation and live NO, never commit.
                    preview=cmd('STORE P AUTO 0300 0307 PVFY',(YES,t.WB))
                    if s.context==YES:cmd('NO',(t.WB,));r['observations']['STORE_AUTO_preview']='confirmed-live-NO'
                    else:r['observations']['STORE_AUTO_preview']=preview.decode('ascii')
                    # Existing NFCOPY is the admitted8-byte public-HOLD demo.
                    chosen='NFCOPY' if b'NFCOPY' in table else 'CLK'
                    out=cmd('RESTORE P '+chosen+' L',(t.MON,t.WB))
                    assert b'CRC' in out and (b'loaded' in out.lower()),out
                    monitor()
                    if chosen=='NFCOPY':
                        demo=bytes.fromhex('A9 50 20 6D 7E 4C 67 7E');assert s.dump(0x3000,0x3007)==demo
                        out=cmd('RESTORE P NFCOPY',(t.MON,t.REC));assert s.context==t.MON and b'P' in out
                        r['observations']['existing_PROGRAM_run']='NFCOPY public HOLD to MON'
                    else:r['observations']['existing_PROGRAM_run']='No known BASE1 runnable fixture; legacy CLK load-only, not executed'
                    bench();mount();after=b''.join(raw64(a) for a in range(0,0x240,64))
                    assert after==before;cmd('Q',(t.MON,))
                step('EDU-PROGRAM-WORK-Table-Store-preview-Restore-existing-data',storage)
                def batch():
                    monitor()
                    for text in ('BATCH R MAINT;N 10 A5;K;Q','BATCH R CLOCK;TIME;Q','BATCH MAINT;TABLE P;WORK;Q'):
                        out=cmd(text,(t.MON,));assert b'BATCH done' in out and b'BATCH stopped' not in out,text
                    for text in ('BATCH B0;;B1','BATCH R CLOCK BAD;B0','BATCH R EDU OFF;R WORK;B0'):
                        out=cmd(text,(t.MON,));assert (b'BATCH refused' in out or b'BATCH stopped' in out) and b'Data bank B0' not in out,text
                    cmd('EDU ON');cmd('APPS')
                step('BATCH-native-and-storage-return-failure-stop-and-input-validation',batch)
                def apps():
                    monitor();out=cmd('APPS')
                    assert all(x in out for x in (b'CLOCK B2:B000',b'FLASH B2:E000',b'MAINT B1:8000'))
                    refused=cmd('APP PVFYNONE');assert b'not found' in refused.lower() or b'REFUSED' in refused
                    r['observations']['APPS']=out.decode('ascii')
                step('APPS-native-catalogue-and-missing-app-refusal',apps)
                def loader():
                    rec();t.transport.recovery_usb(s.link)
                    s.link.send(b'L\r');s.until((b'SEND BIN\r\n',),seconds=15)
                    s.link.send(b'\x03');out=s.until((t.REC,),seconds=15)
                    assert s.context==t.REC and b'Recovery L A/B 0-3' in out,out
                    s.service(reader);assert s.client.flash(3)==old3
                    r['NVM_verified']=True;r['final_B3_sha256']=t.sha(old3)
                    r['checks'].append('all-images-settings-boot-wear-and-metadata-in-B3-unchanged')
                step('SEND-BIN-startup-CtrlC-cancel-and-normal-BIN-load',loader)
            finally:
                try:
                    if borrowed:
                        if s.context!=d.SERVICE:rec();s.service(reader)
                        if ram is None:
                            memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
                            ram=prefix+memory[len(reader):]
                        r.update(s.client.restore_owner(ram,zp));s.context=t.REC;r['owner_RAM_restored']=True
                        cmd('B',(t.MON,))
                        if edu!=1:cmd(f'!M 6A20 {edu:02X}')
                        if original==t.REC:cmd('Q',(t.REC,))
                finally:
                    if s is not None:s.link.close();r['port_released']=True
                    if borrowed:
                        restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                        fields=dict(reference_verify_worker_active=False,application_RAM_restore_pending=not restored,
                             application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                             last_reference_feature_verification=str(folder/'report.json'))
                        if r.get('NVM_verified'):
                            hashes=marker['current_physical_bank_sha256'].copy();hashes['B3']=r['final_B3_sha256']
                            fields['current_physical_bank_sha256']=hashes
                            changes=r['observations'].get('preexisting_TZ_appends_preserved',[])
                            if changes:fields['display_offset_minutes']=max(changes,key=lambda x:x['sequence'])['display_offset_minutes']
                        mark(**fields)
                    save()
    r['passed']=not r['failures'] and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();print(('PASS ' if r['passed'] else 'REVIEW ')+board+' current workflow verification; owner RAM restored; port released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True)
    p.add_argument('--out',required=True);p.add_argument('--accepted-from',action='append');a=p.parse_args();run(a.board,a.out,a.accepted_from)
