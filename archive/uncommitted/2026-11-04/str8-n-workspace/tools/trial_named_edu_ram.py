"""2512 only: compressed utility RAM trials, synthetic EDU writes, copy NO."""
import argparse,binascii,json,re,sys,time
from datetime import datetime
from pathlib import Path
import install_2512_native_utilities as d
import nf_opaque as opaque
from named_edu_ram_packet import packet
from trial_edu_settings_ram import record
from serial_test_coordination import drift_pending

t=d.t;Q=t.ROOT/'output/qualification';BUILD=t.ROOT/'BUILD/named-edu-g3-r8'
OUT=Q/'2512-named-EDU-RAM-20261101-r5'
BM=b'BM> ';ST=b'STORAGE> ';EY=b'Save EDU mode? Type YES: ';XY=b'Copy program; source retained. Y to confirm: '


def run(named_only=False,reverse_only=False,negative_only=False,smoke_only=False):
    due=json.loads((Q/'rtc-hourly-controller-last.json').read_text())['next_due']
    assert time.time()+300<datetime.fromisoformat(due.replace('Z','+00:00')).timestamp(),'RTC window; no port opened'
    mf=json.loads((BUILD/'manifest.json').read_text());sy=json.loads((BUILD/'symbols.json').read_text())
    def art(n):
        b=(BUILD/n).read_bytes();assert t.sha(b)==mf['artifacts'][n]['sha256'];return b
    kernel=art('COMPACT-DECODE-6800.bin');bm=art('BM_RAM-2000.bin');sw=art('NAMED-SRAM-WORK-2000.bin')
    # Only the read transport binding changes in the synthetic flash-source case.
    probe=bytearray(sw);at=sy['SW']['MM_X_READ']-0x2000
    assert probe[at+5:at+8]==bytes.fromhex('4C 30 78');probe[at+6:at+8]=bytes.fromhex('00 1A')
    baseline=bytearray(b'\xff'*1024);bn=bytearray(b'\xff'*32);bn[:4]=b'BN\x01\0';bn[4:8]=(1).to_bytes(4,'little')
    bn[8]=4;bn[9:17]=b'2512\0\0\0\0';bn[28:30]=binascii.crc_hqx(bn[:28],65535).to_bytes(2,'little');bn[31]=0
    baseline[:32]=bn;baseline[32:64]=b'owner-fixture-record'.ljust(32,b'\xA5')
    header=b'SR\x01\x3F'+(0x3000).to_bytes(2,'little')+(32).to_bytes(2,'little')+b'XSRC'.ljust(16,b'\0')
    source=(header+bytes(range(32))).ljust(64,b'\xff')
    # Assert every frame before opening the board, including raw loader bounds.
    frames={'EDU':packet(bm,kernel,metadata=baseline),'SW':packet(sw,kernel,storage=True),
            'flash-fixture':packet(bytes(probe),kernel,storage=True,source=source)}
    frames['full']=packet(bm,kernel,metadata=b'\xA5'*1024)
    frames['fault']=packet(bm,kernel,metadata=baseline,fail_after=2)
    bad=bytearray(frames['EDU']);bad[0x5200:0x5204]=b'NOPE';frames['bad-format']=bytes(bad)
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n');(OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    for n,b in frames.items():(OUT/(n+'.bin')).write_bytes(b)
    r=dict(board='2512',passed=False,checks=[],flash_writes=0,journal_writes=0,metadata_flash_writes=0,SRAM_writes=0,
        WORKSPACE_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,owner_RAM_restored=False,owner_ZP_restored=False,
        writer_fixture='CPU5000-53FF; bounded RAM-byte writer1900, never SST programming',source_fixture='Virtual B0:9000 read from CPU1800 only in one case')
    if named_only or reverse_only or negative_only or smoke_only:
        path=Q/('2512-named-EDU-RAM-20261101-r4' if smoke_only else '2512-named-EDU-RAM-20261101-r3' if negative_only else '2512-named-EDU-RAM-20261101-r2' if reverse_only else '2512-named-EDU-RAM-20261101-r1')/'report.json';prior=json.loads(path.read_text())
        assert prior['owner_RAM_restored'] and prior['owner_ZP_restored'] and prior['port_released']
        assert len(prior['checks'])==(7 if smoke_only else 4 if negative_only else 3 if reverse_only else 2)
        old=(t.ROOT/'BUILD/named-edu-g3-r4/BM_RAM-2000.bin').read_bytes()
        if smoke_only:
            spans=set()
            for text in (b'NAME [1-8 characters | CLEAR] (YES required)',b'BASE1 PR05 g1'):
                i=old.index(text);spans.update(range(i,i+len(text)))
            assert len(old)==len(bm) and {i for i in range(len(old)) if old[i]!=bm[i]}<=spans
        else:assert old==bm
        r['checks']=prior['checks'];r['carried_EDU_checks']=dict(report=str(path),sha256=t.sha(path.read_bytes()))
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes();mp=Q/'device-operations/2512.json'
    s=None;ram=zp=prefix=old3=None;borrowed=False;marker=None;oldedu=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(line,tokens=None):
        face=s.command(line,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:40]}.txt').write_bytes(face);return face
    def mon():
        if s.context in (EY,XY):cmd('NO',(BM,ST))
        if s.context in (BM,ST):cmd('Q',(t.MON,))
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def rec():
        if s.context is None:s.link.send(b'\x03\r');s.until((t.MON,t.REC,BM,ST),seconds=12)
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:mon();cmd('Q',(t.REC,))
    def check(n):r['checks'].append(n);save();print('PASS2512 named/EDU '+n,flush=True)
    def load(n,prompt):
        if drift_pending():raise InterruptedError('RTC priority between cases')
        rec();s.load(frames[n],t.sha(frames[n]),prompt)
    save()
    with t.serial_lease('2512-named-transfers-EDU-RAM-only',timeout=60):
      if drift_pending():raise InterruptedError('RTC priority before port open')
      marker=json.loads(mp.read_text());assert not marker['block_snapshot'] and marker['application_ram_restored']
      assert not marker['application_RAM_restore_pending'] and not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.MON,t.REC),seconds=12);mon()
            assert b'g0000000D / MON B' in cmd('VERSION')
            oldedu=s.dump(0x6A20,0x6A20)[0];assert oldedu==1,'Leave owner session OFF unchanged'
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            opaque.durable_file(OUT/'owner-prefix.bin',prefix);opaque.durable_file(OUT/'owner-zp.bin',zp)
            mark(named_edu_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader
            ram=prefix+memory[len(reader):];opaque.durable_file(OUT/'owner-ram.bin',ram)
            old3=s.client.flash(3);assert t.sha(old3)==marker['current_physical_bank_sha256']['B3']
            opaque.durable_file(OUT/'B3-before.bin',old3)
            for bank in (0,1):
                body=(Q/f'2512-named-EDU-RAM-20261101-r2/B{bank}-before.bin').read_bytes() if reverse_only or negative_only or smoke_only else s.client.flash(bank)
                assert t.sha(body)==marker['current_physical_bank_sha256'][f'B{bank}']
                opaque.durable_file(OUT/f'B{bank}-before.bin',body)
            if not named_only and not reverse_only and not negative_only and not smoke_only:
                load('EDU',BM);assert b'EDU ON' in cmd('EDU')
                cmd('EDU SAVE OFF',(EY,));cmd('NO',(BM,));assert b'Saved/default: EDU ON' in cmd('EDU')
                check('RAM-decode-CRC-EDU-query-and-save-NO')
                cmd('EDU SAVE OFF',(EY,));assert b'EDU OFF' in cmd('YES',(BM,))
                assert b'Save EDU mode?' not in cmd('EDU SAVE OFF')
                cmd('EDU SAVE ON',(EY,));assert b'EDU ON' in cmd('YES',(BM,))
                cmd('EDU OFF');assert b'Saved/default: EDU ON' in cmd('EDU');cmd('Q',(t.MON,))
                assert s.dump(0x6A20,0x6A20)==b'\0'
                actual=s.dump(0x5000,0x53FF);expected=bytearray(baseline);expected[64:96]=record(1,0);expected[96:128]=record(2,1)
                assert actual==expected
                (OUT/'metadata-fixture-after.bin').write_bytes(actual);cmd('!M 6A20 01')
                check('commit-last-EDU-OFF-ON-records-exact-no-op-save-and-session-return')
            if not reverse_only and not negative_only and not smoke_only:
                load('flash-fixture',ST)
                cmd('X 0 XSRC P XCOPY',(XY,));assert b'Canceled' in cmd('NO',(ST,))
                cmd('X 0 XSRC S XCOPY',(XY,));cmd('NO',(ST,))
                assert b'Copy failed' in cmd('X 0 ABSENT P XCOPY')
                assert b'X bank NAME' in cmd('X 0 XSRC 0 BAD')
                check('named-flash-to-PROGRAM-P-S-alias-preview-NO-missing-and-syntax')
                cmd('Q',(t.MON,));assert s.dump(0x5B31,0x5B31)==b'\0'
            if smoke_only:
                load('EDU',BM);assert b'EDU [SAVE]' in cmd('?')
                cmd('EDU SAVE OFF',(EY,));cmd('NO',(BM,));assert b'Saved/default: EDU ON' in cmd('EDU')
                cmd('Q',(t.MON,));check('final-candidate-BM-help-identity-and-EDU-save-NO')
            if not negative_only:
                load('SW',ST)
                cmd('X P NFCOPY 0 XBACK',(XY,));assert b'Canceled' in cmd('NO',(ST,))
                assert b'X bank NAME' in cmd('X P NFCOPY 2 BAD')
                check('final-candidate-transfer-CRC-AUTO-NO-and-LED-cleanup' if smoke_only else 'real-PROGRAM-CRC-and-real-blank-flash-AUTO-preview-NO')
                cmd('Q',(t.MON,))
            else:
                for kind in ('bad-format','full','fault'):
                    load(kind,BM)
                    if kind=='bad-format':face=cmd('EDU SAVE OFF')
                    else:cmd('EDU SAVE OFF',(EY,));face=cmd('YES',(BM,))
                    assert b'EDU not saved' in face
                    assert b'Saved/default: EDU ON' in cmd('EDU')
                    cmd('Q',(t.MON,));actual=s.dump(0x5000,0x53FF)
                    expected=bytearray(b'\xA5'*1024 if kind=='full' else baseline)
                    if kind=='fault':expected[64:66]=b'ED'
                    assert actual==expected and s.dump(0x18FF,0x18FF)==bytes([2 if kind=='fault' else 0])
                    (OUT/(kind+'-metadata-after.bin')).write_bytes(actual)
                    check('EDU-'+kind+'-refused-without-committed-record-or-session-change')
            rec();s.service(reader);after=s.client.flash(3);assert after==old3
            opaque.durable_file(OUT/'B3-after.bin',after);r['B3_unchanged']=True
        except BaseException as error:r['error']=repr(error);save();raise
        finally:
          try:
            if borrowed:
                rec();s.service(reader)
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['port_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(named_edu_RAM_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                     block_snapshot=marker['block_snapshot'] if restored else True,final_prompt='REC>',last_named_EDU_RAM_trial=str(OUT/'report.json'))
            save()
    r['passed']=len(r['checks'])==(9 if smoke_only else 7 if negative_only else 4) and r.get('B3_unchanged') and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    save();assert r['passed'];print('PASS2512 named/EDU RAM qualification; REC>; COM4 released',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--named-only',action='store_true');p.add_argument('--reverse-only',action='store_true');p.add_argument('--negative-only',action='store_true');p.add_argument('--smoke-only',action='store_true');a=p.parse_args();run(a.named_only,a.reverse_only,a.negative_only,a.smoke_only)
