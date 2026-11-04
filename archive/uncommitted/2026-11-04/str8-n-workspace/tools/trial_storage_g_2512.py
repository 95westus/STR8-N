"""Approved2512 SRAM-manager G/HOLD trial; exactly320 SPI bytes restored."""
import binascii,json,re
from pathlib import Path
import install_named_edu_2512 as ins
from storage_batch_ram_packet import packet
from serial_test_coordination import drift_pending

t=ins.t;d=ins.d;Q=ins.Q
SCOPE=Q/'2512-storage-G-scope-20261101-r1';OUT=Q/'2512-storage-G-20261101-r1'
BUILD=t.ROOT/'BUILD/storage-batch-g4-r1'
SRAM=b'SRAM> ';ST=b'STORAGE> ';PB=t.PB
YES=b'Enable SRAM writes for this RAM session? Type YES: '
BLOCKS=(0x140,0x800,0x840,0x880,0x8C0)


def approved():
    a=json.loads((SCOPE/'approval.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
    assert a['approved'] and a['owner_answer']=='Approve temporary 320-byte PROGRAM G trial'
    assert t.sha((SCOPE/'plan.json').read_bytes())==a['plan_sha256']
    assert t.sha((SCOPE/'review-document.md').read_bytes())==a['review_document_sha256']
    assert p['temporary_PROGRAM_bytes']==320 and [int(x,16) for x in p['write_blocks']]==list(BLOCKS)
    assert p['flash_erases']==p['flash_byte_programs']==p['journal_appends']==0
    f=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==p['golden_F_sha256']==f['sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
    return p


def allocation(meta):
    assert len(meta)==0x240
    free=[];pages=set(range(8));names=[]
    for slot in range(8):
        row=meta[64+slot*64:128+slot*64]
        if row[63]!=0xA5:free.append(slot);continue
        assert row[:4]==b'SP\x01\0' and binascii.crc_hqx(row[:62],65535)==0
        assert row[62]==0 and row[32:60]==b'\0'*28
        name=row[16:32].rstrip(b'\0');names.append(name)
        length=int.from_bytes(row[6:8],'little')
        if row[15]==1:pages.update(range(row[14],row[14]+(length+255)//256))
    assert free and max(free)==4 and 8 not in pages and b'QG4' not in names
    return names


def run(retry=False):
    global OUT
    if retry:
        prior=json.loads((OUT/'report.json').read_text())
        assert prior['owner_RAM_restored'] and prior['owner_ZP_restored'] and prior['SPI_restored'] and prior['port_released']
        assert prior['error'].startswith("AssertionError(b'S QG4 1000 1007 1000")
        prior_folder=OUT;OUT=Q/'2512-storage-G-20261101-r2'
    p=approved();ins.window(360)
    body=(BUILD/'SRAM-WORK-BATCH-2000.bin').read_bytes();assert t.sha(body)==p['candidate_sha256']
    restorer=(t.ROOT/'BUILD/named-edu-restorer-r1/NAMED-EDU-SPI-RESTORER.bin').read_bytes()
    assert t.sha(restorer)==p['restorer_sha256']
    kernel=(t.ROOT/'BUILD/named-edu-g3-r8/COMPACT-DECODE-6800.bin').read_bytes()
    program=bytes.fromhex(p['program_hex']);assert len(program)==8
    frames={'interactive':packet(body,kernel,3,b'',program=program),
            'batch-G-refusal':packet(body,kernel,3,b'G QG4;Q;D 1000',program=program)}
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    for name,b in frames.items():(OUT/(name+'.bin')).write_bytes(b)
    for name in ('approval.json','plan.json','review.json','review-document.md'):(OUT/name).write_bytes((SCOPE/name).read_bytes())
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,flash_erases=0,journal_appends=0,metadata_appends=0,
        WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,CPU_simulations=0,
        owner_RAM_restored=False,owner_ZP_restored=False,SPI_restored=False,SPI_restore_pending=False,
        temporary_PROGRAM_bytes=320,limitation='RAM candidate entry; installed-manager and WB BATCH frontdoor unchanged')
    if retry:
        r['preceding_restored_attempt']=dict(path=str(prior_folder/'report.json'),sha256=t.sha((prior_folder/'report.json').read_bytes()),
            reason='Host expected a dollar sign; actual successful manager reply is SRAM:00. Fixture must be recreated after exact cleanup; candidate unchanged.')
    s=None;ram=zp=prefix=meta=None;borrowed=dirty=False;before={};marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:38]}.txt').write_bytes(face);return face
    def mon():
        if s.context is None:
            s.link.send(b'\x03\r');s.until((t.MON,t.REC,SRAM,ST,YES,PB),seconds=12)
        if s.context==YES:cmd('NO',(ST,))
        if s.context==PB:s.link.send(b'Q');s.until((t.MON,))
        if s.context in (SRAM,ST,t.WB):cmd('Q',(t.MON,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def bench():
        mon();cmd('MAINT LOAD',(t.WB,));cmd('EDU ON')
        face=cmd('SRAM');assert b'SSRAM PROGRAM:' in face,face
        cmd('Q',(t.MON,));rec();s.load(restorer,t.sha(restorer),PB)
    def raw(address,data=None):
        assert s.context==PB and address%64==0
        fields=address.to_bytes(3,'big')
        if data is not None:
            assert address in BLOCKS and len(data)==64 and data==before[address]
            crc=binascii.crc_hqx(fields+data,65535)
            s.link.send(b'W'+(fields+data).hex().upper().encode()+f'{crc:04X}\r'.encode())
            face=s.until((PB,));assert f'O{crc:04X}\r\n'.encode() in face
        s.link.send(b'R'+fields.hex().upper().encode()+b'\r');face=s.until((PB,))
        found=re.findall(rb'D([0-9A-F]{138})\r?\n',face);assert len(found)==1,face
        frame=bytes.fromhex(found[0].decode())
        assert frame[:3]==fields and binascii.crc_hqx(frame[:-2],65535)==int.from_bytes(frame[-2:],'big')
        if data is not None:assert frame[3:-2]==data
        return frame[3:-2]
    def check(name):r['checks'].append(name);save();print('PASS2512 G '+name,flush=True)
    def cleanup_spi():
        nonlocal dirty
        if not dirty:return
        bench();restored=[]
        for addr in BLOCKS:
            if raw(addr)!=before[addr]:raw(addr,before[addr]);restored.append(f'{addr:05X}')
        assert b''.join(raw(a) for a in range(0,0x240,64))==meta
        assert b''.join(raw(a) for a in BLOCKS)==b''.join(before[a] for a in BLOCKS)
        dirty=False;r.update(SPI_restored=True,SPI_restore_pending=False,restored_blocks=restored)
        mark(storage_G_SPI_restore_pending=False)
        check('exact320-SPI-and-full-directory-restored')
    save()
    with t.serial_lease('2512-approved320-PROGRAM-G',timeout=30):
      ins.window(360);marker=json.loads(mp.read_text())
      assert not marker['block_snapshot'] and marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      assert marker['current_physical_bank_sha256']==p['physical_banks_at_preparation']
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'g0000000F / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (OUT/'owner-prefix.bin').write_bytes(prefix);(OUT/'owner-zp.bin').write_bytes(zp)
            mark(storage_G_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500)
            assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):];(OUT/'owner-ram.bin').write_bytes(ram)
            bench();meta=b''.join(raw(a) for a in range(0,0x240,64));names=allocation(meta)
            for addr in BLOCKS:before[addr]=raw(addr)
            assert before[0x140]==meta[0x140:0x180]
            (OUT/'PROGRAM-directory-before.bin').write_bytes(meta)
            (OUT/'SPI320-before.bin').write_bytes(b''.join(before[a] for a in BLOCKS))
            r['retained_names']=[n.decode('ascii') for n in names];check('fresh-slot4-page08-admission-and-preimages')
            if drift_pending():raise InterruptedError('RTC priority before first PROGRAM write')
            rec();s.load(frames['interactive'],t.sha(frames['interactive']),SRAM)
            cmd('!',(ST,));cmd('UNLOCK',(YES,));cmd('YES',(ST,));cmd('S',(SRAM,))
            dirty=True;r['SPI_restore_pending']=True;mark(storage_G_SPI_restore_pending=True);save()
            face=cmd('S QG4 1000 1007 1000');assert re.search(rb'SRAM: 00\r?\n',face),face
            assert b'QG4 1000 0008' in cmd('T')
            face=cmd('G QG4',(t.MON,));assert s.dump(0x18FF,0x18FF)==b'G'
            assert s.dump(0x1000,0x1007)==program
            (OUT/'G-public-HOLD-return.txt').write_bytes(face)
            check('manager-STORE-TABLE-G-marker-and-public-HOLD-MON-return')
            bench();row=raw(0x140);payload=raw(0x800)
            assert row[:4]==b'SP\x01\0' and row[63]==0xA5 and binascii.crc_hqx(row[:62],65535)==0
            assert row[4:10]==bytes.fromhex('00 10 08 00 00 10') and row[14:16]==bytes((8,1))
            assert row[16:32]==b'QG4'.ljust(16,b'\0') and payload[:8]==program
            assert int.from_bytes(row[12:14],'little')==binascii.crc_hqx(program,65535)
            actual=b''.join(raw(a) for a in range(0,0x240,64))
            assert actual[:0x140]==meta[:0x140] and actual[0x180:]==meta[0x180:]
            data=b''.join(raw(a) for a in BLOCKS[1:]);assert data[8:]==b''.join(before[a] for a in BLOCKS[1:])[8:]
            (OUT/'QG4-record.bin').write_bytes(row);check('committed-record-CRC-payload-and-exact-write-boundaries')
            if drift_pending():raise InterruptedError('RTC priority; restoring PROGRAM before yielding')
            rec();log.flush();start=(OUT/'serial.jsonl').stat().st_size
            frame=frames['batch-G-refusal'];s.load(frame,t.sha(frame),b'BATCH stopped\r\n');s.until((SRAM,),seconds=12)
            log.flush()
            with (OUT/'serial.jsonl').open('rb') as capture:
                capture.seek(start);events=[json.loads(line) for line in capture if line.strip()]
            face=b''.join(bytes.fromhex(e['hex']) for e in events if e.get('direction')=='RX')
            (OUT/'BATCH-G-refusal.txt').write_bytes(face)
            assert re.search(rb'SRAM: 4A\r?\n',face) and b'1000:' not in face,face[-1000:]
            cmd('Q',(t.MON,));assert s.dump(0x18FF,0x18FF)==b'\0'
            check('BATCH-G-refused-without-execution-or-tail')
            cleanup_spi()
        except BaseException as e:r['error']=repr(e);save();raise
        finally:
          try:
            if dirty:cleanup_spi()
            if borrowed:
                rec();s.service(reader)
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored'] and not dirty
                mark(storage_G_worker_active=False,storage_G_SPI_restore_pending=dirty,
                    application_RAM_restore_pending=not (r['owner_RAM_restored'] and r['owner_ZP_restored']),
                    application_ram_restored=bool(r['owner_RAM_restored'] and r['owner_ZP_restored']),
                    block_snapshot=marker['block_snapshot'] if restored else True,
                    final_prompt='REC>' if restored else 'RESTORATION REQUIRED',last_storage_G_trial=str(OUT/'report.json'))
            save()
    r['passed']=len(r['checks'])==5 and r['SPI_restored'] and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();assert r['passed'];print('PASS2512 SRAM G; PROGRAM and owner RAM/ZP restored; REC>; COM4 released',flush=True)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--retry',action='store_true');run(p.parse_args().retry)
