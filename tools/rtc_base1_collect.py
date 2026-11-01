"""2512 BASE1 read-only RTC capture through RAM; no MON, reset or NVM writer."""
import argparse,binascii,hashlib,json,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification'
REPO=ROOT/'release/str8nf-v0.2.0';BUILD=ROOT/'BUILD/rtc-base1-2512-20261029'
sys.path[:0]=[str(REPO/'migration-host'),str(REPO/'tools'),str(ROOT/'tools'),str(ROOT/'tmp/migration-python'),str(ROOT/'tmp/phase13-history/tools')]
import nf_migrate_live as live
import nf_provision_live as transport
import nf_recovery as recovery
from serial_test_coordination import serial_lease
from rtc_utc_baseline import ntp_sample,Reference,decoded,iso
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
digest=lambda b:hashlib.sha256(bytes(b)).hexdigest()
crc=lambda b:binascii.crc_hqx(bytes(b),65535)
now=lambda:datetime.now(timezone.utc).isoformat()
PROMPT=b'RTC BASE1 READ ONLY> '
F_SHA='8f4d35ac66730daa773515980983fcf442be3b1bdf1e523d3752ec3615657cc1'
MARK=Q/'device-operations/2512.json'


def save(path,value):
    from installer.common import save as atomic_save
    atomic_save(Path(path),value)


def inputs():
    marker=read(MARK);receipt=Path(marker['completion_receipt']['path']);r=read(receipt)
    assert sha(receipt)==marker['completion_receipt']['sha256'] and r['passed']
    assert marker['firmware']=='STR8N-F 0.3.0 BASE1 PR05' and marker['current_F_sha256']==F_SHA
    assert marker['application_ram_restored'] and not marker['block_snapshot']
    assert not any(v for k,v in marker.items() if k.endswith('_worker_active'))
    assert not any(marker.get(k) for k in ('application_RAM_restore_pending','physical_reset_pending','owner_application_running'))
    assert marker['final_prompt']=='REC>' and r['original_owner_RAM_ZP_restored_and_verified']
    assert sha(REPO/'src/core/boot-symbols.inc')==r['source_sha256']['src/core/boot-symbols.inc']
    assert sha(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin')==F_SHA
    proof=read(BUILD/'proof.json');image=(BUILD/'2512-RTC-BASE1-RAM.bin').read_bytes()
    assert proof['passed'] and digest(image)==proof['sha256'] and len(image)==1733
    assert digest((BUILD/'sampler.bin').read_bytes())==proof['sampler_sha256']
    assert sha(ROOT/'tools/build_rtc_base1.py')==proof['builder_sha256']
    reader=(REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    assert len(reader)==3078 and digest(reader)==live.READBACK_SHA256
    escrow=Q/'2512-programmer-F-provisioning-20261028-r1/owner-escrow'
    meta,bodies=transport.owner_escrow(escrow,cpu='65c02',usb_serial='A10MQFLCA')
    assert digest(bodies['owner-ram.bin'])==r['RAM_sha256'] and digest(bodies['owner-zp.bin'])==r['ZP_sha256']
    banks=[marker['current_physical_bank_sha256'][f'B{n}'] for n in range(4)]
    assert banks==r['after_bank_sha256']
    return marker,receipt,meta,bodies,proof,image,reader,banks


def collect(folder):
    marker,receipt,escrow,bodies,proof,image,reader,banks=inputs()
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    (folder/'marker-before.json').write_text(json.dumps(marker,indent=2)+'\n')
    (folder/'escrow-authority.json').write_text(json.dumps(escrow,indent=2)+'\n')
    r=dict(board='2512',usb_serial='A10MQFLCA',port='COM4',capture_profile='BASE1-RTC-RAM1',passed=False,
        clock_set_attempted=False,flash_written=False,trim_changed=False,readings=[],reference_samples=[],
        reference_rejections=[],started_utc=now(),client_sha256=proof['sha256'],client_entry=512,
        client_proof=str(BUILD/'proof.json'),client_proof_sha256=sha(BUILD/'proof.json'),
        driver_sha256=sha(__file__),initial_qualified_receipt=str(receipt),initial_qualified_receipt_sha256=sha(receipt),
        RAM_prefix_authority='Previously independently captured original prefix, restored and verified in the latest completed provisioning receipt; remainder/ZP freshly double-read before sampling.',
        mode='BASE1 RAM-only read-only RTC/PF/EUI; original owner RAM/ZP restored; no MON execution',
        clock_advanced=False,application_ram_restored=False,returned_to_original_REC=False)
    class EvidenceClient(recovery.RecoveryClient):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);self.last_read={};self.responses=0
        def read(self,command,count):
            body=super().read(command,count);self.responses+=1;self.last_read[command]=body
            (folder/f'response-{len(list(folder.glob("response-*.bin"))):03d}-{command.hex()}.bin').write_bytes(body)
            return body
    def checkpoint():save(folder/'report.json',r)
    def reference_sample():
        for attempt in range(3):
            try:return ntp_sample('132.163.96.6')
            except (AssertionError,TimeoutError) as e:
                r['reference_rejections'].append(dict(utc=now(),error=repr(e)));checkpoint()
                if attempt==2:raise
                time.sleep(4)
    checkpoint();link=None;client=None;service=False;borrowed=False;owner_ram=None;owner_zp=None
    def mark(**fields):
        m=read(MARK);m.update(fields);save(MARK,m)
    try:
      with serial_lease('drift',timeout=30):
        inputs() # Recheck admission after acquiring the shared lease.
        for n in range(3):
            if n:time.sleep(4)
            r['reference_samples'].append(reference_sample());checkpoint()
        ref=Reference(r['reference_samples']);r['reference_uncertainty_s']=ref.uncertainty
        with (folder/'serial.jsonl').open('x',encoding='utf-8',newline='\n') as log:
          link=transport.RecoveryLink('COM4',log,usb_serial='A10MQFLCA')
          try:
            link.send(b'\r');initial=link.until(live.REC,seconds=15)
            (folder/'initial-REC.txt').write_bytes(initial)
            save(folder/'prompt-admission.json',dict(board='2512',entered_from_REC=True,monitor_selected=False))
            transport.recovery_usb(link)
            mark(one_shot_collection_active=True,application_RAM_restore_pending=True,block_snapshot=True)
            borrowed=True
            recovery.PROMPT=b'RAM SERVICE BASE1> '
            client=EvidenceClient(live.LoggedRecoveryStream(link),timeout=60,progress=lambda s:print(s,flush=True))
            client.load(reader,live.READBACK_SHA256,REC_observed=True);service=True
            initial_ram=client.read(b'M',recovery.RAM_BYTES);repeat=client.read(b'M',recovery.RAM_BYTES)
            zp=client.read(b'Z',recovery.ZP_BYTES);zp_repeat=client.read(b'Z',recovery.ZP_BYTES)
            assert initial_ram==repeat and zp==zp_repeat and initial_ram[:len(reader)]==reader
            owner_ram=bodies['owner-ram.bin'][:len(reader)]+initial_ram[len(reader):];owner_zp=zp
            assert initial_ram[len(reader):]==bodies['owner-ram.bin'][len(reader):] and zp==bodies['owner-zp.bin'],'Owner RAM changed since the declared prefix authority; stop before sampling'
            for name,body in [('initial-reader-ram.bin',initial_ram),('initial-reader-ram-repeat.bin',repeat),('owner-ram-before.bin',owner_ram),('owner-zp-before.bin',owner_zp)]: (folder/name).write_bytes(body)
            for number in (1,2):
                for bank in (3,0,1,2):
                    data=client.flash(bank);(folder/f'flash-before-{number}-b{bank}.bin').write_bytes(data)
                    assert digest(data)==banks[bank]
            assert (folder/'flash-before-1-b3.bin').read_bytes()[-4096:]==(REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
            client.restore_owner(owner_ram,owner_zp);service=False
            transport.recovery_usb(link)
            recovery.PROMPT=PROMPT
            client=EvidenceClient(live.LoggedRecoveryStream(link),timeout=60,progress=lambda s:print(s,flush=True))
            client.load(image,proof['sha256'],REC_observed=True);service=True
            work=bytearray(owner_ram);work[:len(image)]=image
            sampler=(BUILD/'sampler.bin').read_bytes();work[0x1e00:0x1e00+len(sampler)]=sampler
            assert client.read(b'M',recovery.RAM_BYTES)==bytes(work)==client.read(b'M',recovery.RAM_BYTES),'Loaded RAM sampler image did not verify'
            assert client.read(b'Z',recovery.ZP_BYTES)==owner_zp
            print('2512: BASE1 reader, all four flash banks and loaded sampler verified; beginning RTC/NIST samples',flush=True)
            def packet(command,count):
                first=ref.now();client.send(command);client.until(b'@');last=ref.now()
                body=client.exact(count);trailer=client.exact(2);client.until(PROMPT)
                assert crc(body)==int.from_bytes(trailer,'little')
                return body,first,last
            identity,_,_=packet(b'I',7);assert identity[-1]==0
            (folder/'identity.bin').write_bytes(identity)
            r['eui']=':'.join(f'{b:02X}' for b in identity[:6])
            for turn in range(2):
                ee,_,_=packet(b'H',256);assert ee[0]==0
                (folder/f'pf-eeprom-{turn}.bin').write_bytes(ee[128:])
                if turn:break
                for n in range(9):
                    if n:time.sleep(.137+n*.031)
                    data,first,last=packet(b'R',64);(folder/f'read-{n}.bin').write_bytes(data)
                    item=dict(status=data[0],flags=data[1],calendar=list(data[2:10]),raw=list(data[11:20]),outage=list(data[20:28]),evidence_valid=data[28],captured_outage=list(data[48:56]),reference_start_utc=iso(first),reference_end_utc=iso(last),reference_start_unix=first,reference_end_unix=last,bracket_seconds=last-first)
                    assert data[0]==0 and data[1]&7==7,'RTC status/calendar rejected; raw packet retained'
                    rtc=decoded(data);item.update(rtc_utc=iso(rtc),rtc_unix=rtc,rtc_minus_reference_interval_s=[rtc-last-ref.uncertainty,rtc+1-first+ref.uncertainty])
                    r['readings'].append(item);checkpoint()
            r['clock_advanced']=r['readings'][-1]['rtc_unix']>r['readings'][0]['rtc_unix']
            assert r['clock_advanced']
            lo=max(x['rtc_minus_reference_interval_s'][0] for x in r['readings']);hi=min(x['rtc_minus_reference_interval_s'][1] for x in r['readings']);assert lo<=hi
            r.update(rtc_minus_reference_interval_s=[lo,hi],baseline_reference_unix=(r['readings'][-1]['reference_start_unix']+r['readings'][-1]['reference_end_unix'])/2)
            r['baseline_reference_utc']=iso(r['baseline_reference_unix'])
            raw=r['readings'][-1]['raw'];r['control_register']=raw[7];r['trim_steps']=(-(raw[8]&127) if not raw[8]&128 else raw[8]&127)
            r['final_reference_check']=reference_sample();check=r['final_reference_check']
            r['final_reference_difference_s']=check['host_receive_unix']+check['server_minus_host_s']-(ref.best['host_receive_unix']+ref.best['server_minus_host_s']+check['receive_monotonic']-ref.best['receive_monotonic'])
            assert abs(r['final_reference_difference_s'])<=ref.uncertainty+check['estimated_reference_uncertainty_s']
            for number in (1,2):
                for bank in (3,0,1,2):
                    data=client.flash(bank);(folder/f'flash-after-{number}-b{bank}.bin').write_bytes(data)
                    assert data==(folder/f'flash-before-{number}-b{bank}.bin').read_bytes()
            r['acquisition_passed']=True;checkpoint()
          finally:
           try:
            if service and client is not None:
                if owner_ram is None:owner_ram=bodies['owner-ram.bin'];owner_zp=bodies['owner-zp.bin']
                r.update(client.restore_owner(owner_ram,owner_zp));service=False
                # Restore verified within the resident service before its Q.
                r['application_ram_restored']=True;r['returned_to_original_REC']=True
                rx=b''.join(bytes.fromhex(x['hex']) for x in map(json.loads,(folder/'serial.jsonl').read_text().splitlines()) if x['direction']=='RX')
                assert rx.endswith(live.REC)
                (folder/'final-REC.txt').write_bytes(rx[rx.rfind(live.REC):])
                (folder/'owner-ram-restored.bin').write_bytes(client.last_read[b'M']);(folder/'owner-zp-restored.bin').write_bytes(client.last_read[b'Z'])
           finally:
            if link is not None:link.close();link=None;r['port_released']=True
            mark(one_shot_collection_active=False,application_RAM_restore_pending=borrowed and not r['application_ram_restored'],application_ram_restored=r['application_ram_restored'],block_snapshot=marker['block_snapshot'] if r['application_ram_restored'] else True)
      r['passed']=bool(r.get('acquisition_passed') and r['application_ram_restored'] and r.get('port_released'))
      assert r['passed'];r['finished_utc']=now();checkpoint()
      print('PASS 2512 BASE1',r['baseline_reference_utc'],r['rtc_minus_reference_interval_s'],'trim',r['trim_steps'],'RAM/ZP restored; REC>; port released',flush=True)
      return r
    except BaseException as error:
      r.update(passed=False,error=repr(error),traceback=traceback.format_exc(),finished_utc=now());checkpoint();raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--collect',action='store_true');parser.add_argument('--out',type=Path);args=parser.parse_args()
    inputs()
    if not args.collect:print('PASS BASE1 sampler files, qualification and escrow admission; no board port opened');return
    out=args.out or Q/('rtc-base1-2512-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    collect(out)


if __name__=='__main__':main()
