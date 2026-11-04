"""Qualify STORE's pre-WB parser/cancel/provider guard; no SPI data writes."""
import argparse,json
from pathlib import Path
import install_2512_native_utilities as d
from serial_test_coordination import drift_pending
t=d.t
CONFIRM=b'STORE PROGRAM from original RAM; type YES: '


def packet_for(overlay,line):
    text=line.encode()+b'\0';assert len(text)<=41
    stub=bytes.fromhex('A2 80 A0 67 20 08 6D 4C 67 7E')
    code=bytearray(bytes.fromhex('78 D8 A2 00'));loop=len(code)
    for n in range(6):code.extend(bytes((0xBD,0,3+n,0x9D,0,0x6B+n)))
    code.extend(bytes.fromhex('E8 D0'));code.append((loop-len(code)-1)&255)
    code.extend(bytes.fromhex('A2 3F'));loop=len(code)
    code.extend(bytes.fromhex('BD 80 02 9D 80 67 CA 10'));code.append((loop-len(code)-1)&255)
    code.extend(bytes.fromhex('A2 0A'));loop=len(code)
    # Keep the returning caller below6A30: the provider replaces ALL6B00-77FF.
    code.extend(bytes.fromhex('BD C0 02 9D 21 6A CA 10'));code.append((loop-len(code)-1)&255)
    code.extend(bytes.fromhex('4C 21 6A'));assert len(code)<=0x80
    return bytes(code).ljust(0x80,b'\xff')+text.ljust(0x40,b'\xff')+stub.ljust(0x40,b'\xff')+overlay


def run(board,out,finish_guards=None):
    folder=Path(out).resolve();assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n');(folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    build=t.ROOT/'BUILD/store-front-g1-ram-r1';mf=json.loads((build/'manifest.json').read_text())
    overlay=(build/'S19-STORE-6B00.bin').read_bytes();assert t.sha(overlay)==mf['artifacts']['S19-STORE-6B00.bin']['sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=t.ROOT/f'output/qualification/device-operations/{board}.json'
    r=dict(board=board,passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_writes=0,WORKSPACE_writes=0,
           RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False)
    if finish_guards:
        previous=Path(finish_guards).resolve();assert previous.is_relative_to(t.ROOT/'output/qualification')
        carried=json.loads((previous/'report.json').read_text())
        assert carried['board']==board and carried['owner_RAM_restored'] and carried['owner_ZP_restored'] and carried['B3_unchanged']
        assert not carried.get('error') and carried['yielded_to_collection'] and len(carried['checks'])==3
        assert packet_for(overlay,'S P 9800 4700 66FF WIDETEST')==(previous/'case-2.bin').read_bytes()
        r['checks'].extend(carried['checks'][1:]);r['continued_evidence']=str(previous/'report.json')
    s=None;borrowed=False;marker=None;ram=zp=prefix=old3=None;origin=None;edu=None
    def save():t.save(folder/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def boundary():
        if drift_pending():raise InterruptedError('Yield to NIST/RTCC')
    def mon():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:s.command('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==t.MON:s.command('Q',(t.REC,))
        assert s.context==t.REC
    def check(name):r['checks'].append(name);save();print('PASS '+board+' '+name,flush=True)
    def source():return b''.join(s.dump(a,min(a+1023,0x66FF)) for a in range(0x4700,0x6700,1024))
    def invoke(line,expect,reply=None):
        boundary();rec();packet=packet_for(overlay,line)
        (folder/f'case-{len(r["checks"])}.bin').write_bytes(packet)
        s.load(packet,t.sha(packet),CONFIRM if reply is not None else t.MON)
        if reply is not None:
            s.link.send(reply);face=s.until((t.MON,),seconds=25)
        else:
            # load() consumes the prompt; its exact transcript is in serial.jsonl.
            face=b''.join(bytes.fromhex(json.loads(v)['hex']) for v in (folder/'serial.jsonl').read_text().splitlines() if json.loads(v)['direction']=='RX')[-4096:]
        (folder/f'case-{len(r["checks"])}.txt').write_bytes(face);assert expect in face,face
        assert source()==ram[0x4500:],'Frontend overwrote its owner source'
    save()
    with t.serial_lease(board+'-STORE-frontend-readonly',timeout=600):
      boundary();marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);origin=s.context
            mon();assert b'g0000000D / MON B' in s.command('VERSION');edu=s.dump(0x6A20,0x6A20)[0]
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
            mark(store_front_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
            old3=s.client.flash(3);(folder/'B3-before.bin').write_bytes(old3)
            assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            # Prove the flash provider is not the pinned new wide-Store worker.
            old2=s.client.flash(2);(folder/'B2-before.bin').write_bytes(old2)
            provider=(t.ROOT/'BUILD/program-sp1-g3-store-r2/STR8N-PROGRAM-SP1-6B00.bin').read_bytes()
            assert old2[0x1F00:0x2C00]!=provider and old2[0x2BFE:0x2C00]!=provider[-2:]
            s.client.restore_owner(ram,zp);s.context=t.REC;mon()
            if edu!=1:s.command('!M 6A20 01')
            check('fresh-owner-source-and-old-provider-admission')
            if not finish_guards:
                invoke('STORE P AUTO 4700 66FF WIDETEST',b'Canceled; no Store.',b'NO\r')
                check('AUTO-and-NO-preserve-original-large-source')
                invoke('S P 9800 4700 66FF WIDETEST',b'Canceled; no Store.',b'\x03')
                check('explicit-target-and-Ctrl-C-at-confirmation')
            invoke('STORE P AUTO 4700 6700 WIDETEST',b'Use STORE P AUTO|addr start end name')
            check('range-refused-before-confirmation')
            invoke('STORE P AUTO 4700 66FF WIDETEST',b'STORE status $81',b'YES\r')
            check('YES-refuses-old-provider-before-any-SPI-write')
        except InterruptedError as e:r['yielded_to_collection']=True;r['deferral']=str(e)
        except Exception as e:r['error']=repr(e);raise
        finally:
          try:
            if borrowed:
                if s.context is None:s.until((t.MON,t.REC),seconds=5)
                rec();s.service(reader)
                if old3 is not None:r['B3_unchanged']=s.client.flash(3)==old3
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
                if origin==t.MON:
                    mon()
                    if edu!=1:s.command(f'!M 6A20 {edu:02X}')
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(store_front_RAM_worker_active=False,application_RAM_restore_pending=not restored,
                     application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                     last_STORE_front_RAM_trial=str(folder/'report.json'))
            save()
    r['passed']=len(r['checks'])==5 and not r.get('error') and not r.get('yielded_to_collection') and r.get('B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored']
    save();print(('PASS ' if r['passed'] else 'DEFERRED ')+board+' Store frontend; port released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=('2512','2609'),required=True)
    p.add_argument('--out',required=True);p.add_argument('--finish-guards');a=p.parse_args();run(a.board,a.out,a.finish_guards)
