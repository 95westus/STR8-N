"""RAM-only wide Store preview: no SPI data write and no owner-source overlap."""
import argparse,json,re
from pathlib import Path
import install_2512_native_utilities as d
from serial_test_coordination import drift_pending

t=d.t


def packet_for(provider,op,start=0x4700,end=0x66FF):
    request=bytearray(32);request[0]=op
    request[2:4]=start.to_bytes(2,'little');request[4:6]=end.to_bytes(2,'little')
    request[8:16]=b'WIDETEST';request[24:26]=(0x9800).to_bytes(2,'little');request[29]=2
    # The caller is in MON's transient parser area, outside owner RAM and SP.
    stub=bytes.fromhex('A9 D0 A2 69 20 15 6B 8D F0 69 08 68 8D F1 69 4C 67 7E')
    code=bytearray(bytes.fromhex('78 D8 A2 00'));loop=len(code)
    for n in range(13):code.extend(bytes((0xBD,0,3+n,0x9D,0,0x6B+n)))
    code.extend(bytes.fromhex('E8 D0'));code.append((loop-len(code)-1)&255)
    code.extend(bytes.fromhex('A2 1F'));loop=len(code)
    code.extend(bytes.fromhex('BD C0 02 9D 30 6A BD E0 02 9D D0 69 CA 10'))
    code.append((loop-len(code)-1)&255);code.extend(bytes.fromhex('4C 30 6A'))
    assert len(code)<=0xC0 and len(stub)<=32
    return bytes(code).ljust(0xC0,b'\xff')+stub.ljust(32,b'\xff')+request+provider


def run(board,out):
    folder=Path(out).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    (folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    build=t.ROOT/'BUILD/program-sp1-g3-store-r2';manifest=json.loads((build/'manifest.json').read_text())
    provider=(build/manifest['artifact']['filename']).read_bytes();assert t.sha(provider)==manifest['artifact']['sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=t.ROOT/f'output/qualification/device-operations/{board}.json'
    r=dict(board=board,passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_writes=0,WORKSPACE_writes=0,
           RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;borrowed=False;marker=None;ram=zp=prefix=old3=None;origin=None;edu=None
    def save():t.save(folder/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def boundary():
        if drift_pending():raise InterruptedError('Yield to NIST/RTCC')
    def mon():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:s.command('B',(t.MON,))
        if s.context==t.WB:s.command('Q',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();s.command('Q',(t.REC,))
    def check(name):r['checks'].append(name);save();print('PASS '+board+' '+name,flush=True)
    def metadata():
        mon();s.command('MAINT LOAD',(t.WB,));s.command('EDU ON')
        face=s.command('SRAM')
        if b'SSRAM error $01' in face:s.command('SRAM PREP');face=s.command('SRAM')
        assert b'SSRAM PROGRAM:' in face
        result=bytearray()
        for address in range(0,0x800,64):
            face=s.command(f'SRAM READ 0 {address:04X}')
            m=re.search(rb'RAW64 ((?:[0-9A-F]{2} ){64})',face);assert m
            result.extend(bytes.fromhex(m[1].decode()))
        s.command('Q',(t.MON,));return bytes(result)
    def cpu_source():return b''.join(s.dump(a,min(a+1023,0x66FF)) for a in range(0x4700,0x6700,1024))
    def invoke(op,status,start=0x4700,end=0x66FF):
        boundary();rec();data=packet_for(provider,op,start,end)
        (folder/f'op{op}-{start:04X}-{end:04X}.bin').write_bytes(data)
        s.load(data,t.sha(data),t.MON)
        result=s.dump(0x69F0,0x69F1);assert result[0]==status and result[1]&1==(status==0),(op,result)
        r.setdefault('results',[]).append(dict(op=op,start=f'{start:04X}',end=f'{end:04X}',status=result[0],carry=result[1]&1));save()
        assert cpu_source()==ram[0x4500:], 'Store preview overwrote its owner-RAM source'
    save()
    with t.serial_lease(board+'-wide-STORE-readonly-preview',timeout=600):
      boundary();marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      if marker['block_snapshot']:
          assert marker.get('snapshot_block_reason','').startswith('BASE1 read-only RTC sampler qualified;')
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);origin=s.context
            mon();assert b'g0000000D / MON B' in s.command('VERSION');edu=s.dump(0x6A20,0x6A20)[0]
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
            mark(wide_store_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();t.transport.recovery_usb(s.link);s.service(reader)
            memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
            old3=s.client.flash(3);(folder/'B3-before.bin').write_bytes(old3)
            assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            assert old3[-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
            before=metadata();(folder/'SPI-metadata-before.bin').write_bytes(before)
            rec();s.service(reader);s.client.restore_owner(ram,zp);s.context=t.REC;mon()
            if edu!=1:s.command('!M 6A20 01')
            check('fresh-owner-source-and-SPI-directory-escrow')
            invoke(9,0);check('wide-8KiB-preview-preserves-4700-through-66FF-including-old-request')
            invoke(5,0x44);check('legacy-narrow-Store-still-refuses-WB-overlap')
            invoke(9,0x44,0x4700,0x6700);check('wide-Store-refuses-end-outside-owner-RAM')
            after=metadata();(folder/'SPI-metadata-after.bin').write_bytes(after);assert after==before
            check('directory-layout-and-WORK-metadata-unchanged')
        except InterruptedError as e:r['yielded_to_collection']=True;r['deferral']=str(e)
        except Exception as e:r['error']=repr(e);raise
        finally:
          try:
            if borrowed:
                if s.context is None:s.until((t.MON,t.REC),seconds=5)
                rec();s.service(reader)
                if old3 is not None:r['B3_unchanged']=s.client.flash(3)==old3
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
                    ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                if origin==t.MON:
                    mon()
                    if edu!=1:s.command(f'!M 6A20 {edu:02X}')
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(wide_store_RAM_worker_active=False,application_RAM_restore_pending=not restored,
                     application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                     last_wide_STORE_RAM_preview=str(folder/'report.json'))
            save()
    r['passed']=len(r['checks'])==5 and not r.get('error') and not r.get('yielded_to_collection') and r.get('B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();print(('PASS ' if r['passed'] else 'DEFERRED ')+board+' wide STORE preview; port released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=('2512','2609'),required=True)
    p.add_argument('--out',required=True);a=p.parse_args();run(a.board,a.out)
