"""Exercise the S19 high-RAM overlay, with fresh RAM escrow and RTC priority."""
import argparse
import json
from pathlib import Path
import install_2512_native_utilities as d
from serial_test_coordination import drift_pending

t=d.t
READY=b'SEND S19 (S0/S1/S9); Ctrl-C cancels\r\n'


def row(kind,address,data=b''):
    raw=bytes([len(data)+3])+address.to_bytes(2,'big')+data
    return b'S'+str(kind).encode()+(raw+bytes([255-(sum(raw)&255)])).hex().upper().encode()+b'\r\n'


def run(board,out):
    folder=Path(out).resolve()
    assert folder.is_relative_to(t.ROOT/'output/qualification')
    folder.mkdir(exist_ok=False);(folder/'.gitignore').write_text('*\n')
    (folder/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    build=t.ROOT/'BUILD/s19-loader-g1-ram-r2'
    manifest=json.loads((build/'manifest.json').read_text())
    packet=(build/'STR8N-S19-RAM.bin').read_bytes()
    assert t.sha(packet)==manifest['artifacts']['STR8N-S19-RAM.bin']['sha256']
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=t.ROOT/f'output/qualification/device-operations/{board}.json'
    report=dict(board=board,passed=False,checks=[],flash_writes=0,journal_writes=0,SRAM_writes=0,
                RTC_SET=0,trim_writes=0,PF_ACK=0,F_rebuilt=False,resets=0,power_cuts=0,
                owner_RAM_restored=False,owner_ZP_restored=False)
    s=None;borrowed=False;ram=zp=prefix=old3=None;marker=None;origin=None;edu=None
    def save():t.save(folder/'report.json',report)
    def mark(**fields):
        m=json.loads(mp.read_text());m.update(fields);t.save(mp,m)
    def boundary():
        if drift_pending():raise InterruptedError('Yield to NIST/RTCC collection')
    def check(name):
        report['checks'].append(name);save();print('PASS '+board+' '+name,flush=True)
    def mon():
        if s.context==d.SERVICE:
            s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:s.command('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context==d.SERVICE:
            s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==t.MON:s.command('Q',(t.REC,))
        assert s.context==t.REC,'Do not guess after a missing prompt'
    def transfer(wire,expected_status):
        boundary();rec();s.load(packet,t.sha(packet),READY)
        s.link.send(wire);face=s.until((t.REC,t.MON),seconds=20)
        (folder/f'transfer-{len(report["checks"]):02d}.txt').write_bytes(face)
        assert expected_status in face,face
        mon()
    save()
    with t.serial_lease(board+'-S19-RAM-qualification',timeout=600):
      boundary();marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      if marker['block_snapshot']:
          assert marker.get('snapshot_block_reason','').startswith('BASE1 read-only RTC sampler qualified;')
      with (folder/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(folder,log,board);s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);origin=s.context
            mon();assert b'g0000000D / MON B' in s.command('VERSION')
            edu=s.dump(0x6A20,0x6A20)[0]
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (folder/'owner-prefix.bin').write_bytes(prefix);(folder/'owner-zp.bin').write_bytes(zp)
            mark(s19_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();t.transport.recovery_usb(s.link);s.service(reader)
            current=s.client.read(b'M',0x6500);assert current[:len(reader)]==reader
            ram=prefix+current[len(reader):];(folder/'owner-ram.bin').write_bytes(ram)
            old3=s.client.flash(3);(folder/'B3-before.bin').write_bytes(old3)
            assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            assert old3[-4096:]==(t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
            check('fresh-owner-RAM-ZP-and-golden-F-escrow')
            transfer(b'\x03',b'S19 stopped $03')
            check('Ctrl-C-at-initial-SEND-S19')
            points={0x0200:bytes(range(32)),0x47F0:bytes(range(48)),0x6400:b'S19-HIGH-OWNER',
                    0x65C0:b'OLD-REQUEST-SPACE',0x66F0:bytes(range(16))}
            wire=row(0,0,b'RAM trial')+b''.join(row(1,a,v) for a,v in points.items())+row(9,0x0200)
            transfer(wire,b'S19 loaded; entry $0200')
            for a,v in points.items():assert s.dump(a,a+len(v)-1)==v
            check('S0-S1-S9-across-4800-through-66FF-and-no-auto-run')
            before=s.dump(0x3000,0x300F)
            bad=bytearray(row(1,0x3000,b'\xE1'*16));bad[-4:-2]=b'00' if bad[-4:-2]!=b'00' else b'01'
            transfer(bytes(bad),b'S19 stopped $02');assert s.dump(0x3000,0x300F)==before
            check('checksum-failure-keeps-record-destination-unchanged')
            transfer(row(1,0x66FF,b'\xDA\xDB'),b'S19 stopped $04')
            assert s.dump(0x66FF,0x66FF)==b'\x0F'
            check('record-crossing-66FF-is-refused-before-copy')
            transfer(row(1,0x3000,b'\xA5'*16)+b'S1133010A5\x03',b'S19 stopped $03')
            assert s.dump(0x3000,0x300F)==b'\xA5'*16
            check('mid-record-Ctrl-C-retains-earlier-checked-record')
            transfer(row(1,0x3010,b'lowercase').lower()+row(9,0x3010).lower(),b'S19 loaded; entry $3010')
            assert s.dump(0x3010,0x3018)==b'lowercase'
            check('lowercase-hex-and-S-prefix')
            transfer(row(2,0x3000,b'\x11'),b'S19 stopped $01')
            check('unsupported-record-type-refused')
        except InterruptedError as error:
            report['yielded_to_collection']=True;report['deferral']=str(error)
            print('YIELD '+board+' S19; restoring owner RAM',flush=True)
        except Exception as error:
            report['error']=repr(error);raise
        finally:
          try:
            if borrowed:
                # Consume a known pending prompt if a host assertion failed;
                # do not send guessed reset/escape sequences to a running tool.
                if s.context is None:s.until((t.MON,t.REC),seconds=5)
                rec();s.service(reader)
                if old3 is not None:report['B3_unchanged']=s.client.flash(3)==old3
                if ram is None:
                    current=s.client.read(b'M',0x6500);assert current[:len(reader)]==reader
                    ram=prefix+current[len(reader):]
                report.update(s.client.restore_owner(ram,zp));s.context=t.REC
                if origin==t.MON:
                    mon()
                    if edu!=1:s.command(f'!M 6A20 {edu:02X}')
          finally:
            if s:s.link.close();report['port_released']=True
            if borrowed:
                restored=report['owner_RAM_restored'] and report['owner_ZP_restored']
                mark(s19_RAM_worker_active=False,application_RAM_restore_pending=not restored,
                     application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                     last_S19_RAM_trial=str(folder/'report.json'))
            save()
    report['passed']=len(report['checks'])==8 and not report.get('error') and not report.get('yielded_to_collection') and report.get('B3_unchanged') and report['owner_RAM_restored'] and report['owner_ZP_restored']
    save();print(('PASS ' if report['passed'] else 'DEFERRED ')+board+' S19 RAM; port released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=('2512','2609'),required=True)
    p.add_argument('--out',required=True);a=p.parse_args();run(a.board,a.out)
