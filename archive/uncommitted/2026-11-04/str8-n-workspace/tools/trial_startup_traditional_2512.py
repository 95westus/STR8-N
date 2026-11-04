"""2512 selected startup/VERSION in CPU RAM only; exact owner restoration.

No flash writer, PROGRAM writer, CLOCK SET, trim or PF-ACK path is invoked.
RTC collection owns the shared lease and must have a full bounded window.
"""
import binascii, json, re
from pathlib import Path
import install_named_edu_2512 as ins
from time_prep_ram_packets import symbols
from serial_test_coordination import drift_pending

t=ins.t; d=ins.d; Q=ins.Q
BUILD=t.ROOT/'BUILD/startup-traditional-r2'
OUT=Q/'2512-startup-traditional-RAM-20261101-r1'

def packet():
    mf=json.loads((BUILD/'MON/manifest.json').read_text())
    name,info=next((n,v) for n,v in mf['artifacts'].items() if v['variant']=='RAM')
    body=bytearray((BUILD/'MON'/name).read_bytes());assert t.sha(body)==info['sha256']
    sy=symbols(BUILD/'MON/RAM/mona.map')
    old=bytes.fromhex('64 E2 A9 AC 85 E3');assert body.count(old)==1
    body=body.replace(old,bytes.fromhex('64 E2 A9 30 85 E3'))
    at=sy['MS_GATE']-0x200
    assert body[at:at+20]==bytes.fromhex('DA8D007D2048782008ACA8688D007D2048789860')
    body[at+9]=0x30
    at=sy['MS_EXTENTS']-0x200
    body[at:at+16]=bytes.fromhex('00 20 C0 00 C0 20 C0 00 00 30 00 04 00 34 AA 05')
    result=bytearray(b'\xff'*(0x39AA-0x200));result[:len(body)]=body
    parts=[(BUILD/'RAM/STATUS-text-2000.bin',0x2000),
           (BUILD/'RAM/STATUS-text-20C0.bin',0x20C0),
           (BUILD/'STATUS-RAM.bin',0x3000),
           (BUILD/'RAM/STATUS-details.bin',0x3400)]
    for path,address in parts:
        part=path.read_bytes();assert binascii.crc_hqx(part,65535)==0
        start=address-0x200;assert result[start:start+len(part)]==b'\xff'*len(part)
        result[start:start+len(part)]=part
    # ROM header relocation must retain all existing UI vectors and MI CRC.
    for name,info in mf['artifacts'].items():
        if info['variant']=='RAM':continue
        image=(BUILD/'MON'/name).read_bytes();page=image[3]
        assert t.sha(image)==info['sha256'] and image[72:80]==b'UI\x01\x07PR05'
        assert int.from_bytes(image[18:20],'little')==binascii.crc_hqx(image[:18]+image[32:],65535)
        assert image[46:67]==b'0.1.0-dev BASE1/PR05\0'
        assert image[80:84]==b'NFI1' and image[120:124]==b'RA\x01\x0D'
        assert all(page*256+128<=int.from_bytes(image[i:i+2],'little')<page*256+4096 for i in range(32,46,2))
    return bytes(result)

def run(capture_correction=False,status_continuation=False):
    global OUT
    prior=None
    if capture_correction:
        prior=json.loads((OUT/'report.json').read_text())
        assert prior['owner_RAM_restored'] and prior['owner_ZP_restored'] and prior['COM4_released']
        assert "G 4000" in prior['error'] and "range/entry" in prior['error']
        prior_folder=OUT;OUT=Q/'2512-startup-traditional-RAM-20261101-r2'
    elif status_continuation:
        prior_folder=Q/'2512-startup-traditional-RAM-20261101-r2'
        prior=json.loads((prior_folder/'report.json').read_text())
        assert prior['owner_RAM_restored'] and prior['owner_ZP_restored'] and prior['COM4_released']
        assert prior['error']=='AssertionError()' and len(prior['checks'])==4
        assert (prior_folder/'0009-VERSION_X.txt').read_bytes()==b'VERSION X\r\nSyntax; use ?\r\nB3> '
        help_text=(prior_folder/'0008-_.txt').read_bytes()
        assert all(w in help_text for w in (b'VERSION TIME',b'M1-3 W APPS APP CLOCK FLASH MAINT',b'S/T/R EDU SRAM WORK BATCH'))
        OUT=Q/'2512-startup-traditional-RAM-20261101-r3'
    ins.window(240)
    image=packet()
    freeze=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==freeze['sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in freeze['sources'].items())
    OUT.mkdir(exist_ok=False);(OUT/'.gitignore').write_text('*\n')
    (OUT/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
    (OUT/'candidate.bin').write_bytes(image)
    r=dict(board='2512',passed=False,checks=[],F_writes=0,flash_erases=0,journal_appends=0,
           SPI_data_writes=0,RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,
           owner_RAM_restored=False,owner_ZP_restored=False,CPU_simulations=0,
           candidate_sha256=t.sha(image),F_sha256=freeze['sha256'],
           limitation='RAM MON; installed A/B remain gF. Physical startup and ROM UI binding need installation acceptance.')
    if prior:
        assert prior['candidate_sha256']==t.sha(image)
        r['prior_restored_attempt']=dict(report=str(prior_folder/'report.json'),
            sha256=t.sha((prior_folder/'report.json').read_bytes()),
            correction=('Carry accepted display/V/help/syntax captures; finish TIME/EDU only. Syntax response was correct; host expected REFUSED.'
                        if status_continuation else 'Host captures initial load RX directly; RAM MON correctly refuses G. Firmware unchanged.'))
    if status_continuation:
        r['checks']=prior['checks']+['shared-help-and-VERSION-argument-refusal']
        r['carried_capture_sha256']={n:t.sha((prior_folder/n).read_bytes()) for n in ('startup-capture.txt','0006-VERSION.txt','0007-V.txt','0008-_.txt','0009-VERSION_X.txt')}
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    mp=Q/'device-operations/2512.json';s=None;ram=zp=prefix=None;borrowed=False;marker=None
    def save():t.save(OUT/'report.json',r)
    def mark(**kw):m=json.loads(mp.read_text());m.update(kw);t.save(mp,m)
    def cmd(text,tokens=None):
        face=s.command(text,tokens);(OUT/f'{s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",text)}.txt').write_bytes(face);return face
    def rec():
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:
            assert s.context==t.MON
            cmd('Q',(t.REC,))
    def mon():
        if s.context==d.SERVICE:rec()
        if s.context==t.REC:cmd('B',(t.MON,))
        assert s.context==t.MON
    def check(name):r['checks'].append(name);save();print('PASS2512 presentation '+name,flush=True)
    def face_ok(face):
        for text in (b'STR8-N F 0.3.0  Foundation  gen 00000001',b'Recovery / opaque-image boot',
                     b'STR8-N RAM  gen 00000010',b'Board: 2512',b'RAM $0200-$66FF',b'EDU ON',
                     b'SSRAM: PROGRAM payload 63488 bytes',b'SSRAM: WORKSPACE 65504 bytes',
                     b'RTCC: ',b'(-06:00)',b'FLASH: B2:8 tracked max 604*',b'Battery: within age policy*',
                     b'* Health/prior wear unmeasured; attempts.'):
            assert text in face,(text,face)
    save()
    with t.serial_lease('2512-traditional-startup-RAM-only',timeout=30):
      ins.window(240);marker=json.loads(mp.read_text())
      assert marker['application_ram_restored'] and not marker['application_RAM_restore_pending'] and not marker['block_snapshot']
      assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
      t.save(OUT/'marker-before.json',marker)
      with (OUT/'serial.jsonl').open('x') as log:
        try:
            s=d.Session(OUT,log,'2512');s.link.send(b'\r');s.until((t.REC,t.MON),seconds=12);mon()
            assert b'g0000000F / MON B' in cmd('VERSION')
            prefix=s.dump(0x200,0x1FF+len(reader));zp=s.dump(0,0xDF)
            (OUT/'owner-prefix.bin').write_bytes(prefix);(OUT/'owner-zp.bin').write_bytes(zp)
            mark(startup_presentation_RAM_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
            rec();s.service(reader);memory=s.client.read(b'M',0x6500)
            assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
            (OUT/'owner-ram.bin').write_bytes(ram)
            r.update(owner_RAM_sha256=t.sha(ram),owner_ZP_sha256=t.sha(zp))
            if status_continuation:r['fresh_continuation_escrow']=True;save()
            else:check('fresh-owner-RAM-ZP-escrow')
            rec()
            if drift_pending():raise InterruptedError('RTC priority before candidate load')
            log.flush();capture_offset=log.tell()
            s.load(image,t.sha(image),t.MON)
            if not status_continuation:
                # RecoveryClient consumes the startup prompt. Capture actual RX,
                # never the transmitted BIN's embedded strings. RAM G is refused.
                log.flush()
                events=(OUT/'serial.jsonl').read_bytes()[capture_offset:].decode('utf-8').splitlines()
                rx=b''.join(bytes.fromhex(e['hex']) for e in map(json.loads,events) if e['direction']=='RX')
                first=rx.index(b'\r\nSTR8-N F ')
                startup=rx[first:rx.index(t.MON,first)+len(t.MON)];face_ok(startup)
                assert b'CPU:' not in startup and b'MONITOR A gen ' not in startup and b'BASE1/PR05' not in startup
                (OUT/'startup-capture.txt').write_bytes(startup);check('selected-startup-rich-status-no-duplicate-inventory')
                version=cmd('VERSION');face_ok(version)
                assert b'0.1.0-dev BASE1/PR05 ABI 2' in version and b'CPU: 65C02' in version
                assert b'MONITOR A gen 0000000F VALID' in version and b'MONITOR B gen 0000000F VALID default' in version
                check('VERSION-full-compatibility-CPU-validated-slots')
                assert b'0.1.0-dev BASE1/PR05 ABI 2' in cmd('V');check('V-alias')
                help_text=cmd('?')
                for word in (b'VERSION TIME',b'M1-3 W APPS APP CLOCK FLASH MAINT',b'S/T/R EDU SRAM WORK BATCH'):
                    assert word in help_text,help_text
                assert b'Syntax; use ?' in cmd('VERSION X');check('shared-help-and-VERSION-argument-refusal')
            time_text=cmd('TIME')
            assert b'trim $0C ctrl $80' in time_text and b'Foundation' not in time_text and b'CPU:' not in time_text
            check('concise-live-TIME-retains-current-trim-control')
            cmd('!M 6A20 00');off=cmd('VERSION')
            assert b'EDU OFF' in off and b'SSRAM: --*' in off and b'RTCC: --*' in off
            cmd('!M 6A20 01');face_ok(cmd('VERSION'));check('EDU-unavailable-markers-and-session-reenable')
        except BaseException as error:r['error']=repr(error);save();raise
        finally:
          try:
            if borrowed:
                rec();s.service(reader)
                if ram is None:
                    memory=s.client.read(b'M',0x6500);assert memory[:len(reader)]==reader;ram=prefix+memory[len(reader):]
                r.update(s.client.restore_owner(ram,zp));s.context=t.REC
          finally:
            if s:s.link.close();r['COM4_released']=True
            if borrowed:
                restored=r['owner_RAM_restored'] and r['owner_ZP_restored']
                mark(startup_presentation_RAM_worker_active=False,application_RAM_restore_pending=not restored,
                     application_ram_restored=restored,block_snapshot=marker['block_snapshot'] if restored else True,
                     final_prompt='REC>',last_startup_presentation_RAM_trial=str(OUT/'report.json'))
            save()
    r['passed']=len(r['checks'])==7 and r['owner_RAM_restored'] and r['owner_ZP_restored'];save()
    assert r['passed'];print('PASS2512 Traditional startup RAM; owner restored; REC>; COM4 released',flush=True)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group()
    group.add_argument('--capture-correction',action='store_true');group.add_argument('--status-continuation',action='store_true')
    args=p.parse_args();run(args.capture_correction,args.status_continuation)
