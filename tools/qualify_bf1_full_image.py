"""Offline clean-image composition, boot/fallback and provider qualification."""
import json,hashlib,importlib.util,traceback
from pathlib import Path
from datetime import datetime,timezone
import bf1_offline_recovery_model as harness
ROOT=Path(__file__).resolve().parents[1];Q=ROOT/'output/qualification';IMAGE=Q/'bf1-full-image-2026-10-17-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out=Q/'bf1-full-image-tests-2026-10-17-r2';out.mkdir(exist_ok=False)
    path=ROOT/'release/bf1-prerelease/build_full_image.py';spec=importlib.util.spec_from_file_location('composer',path);composer=importlib.util.module_from_spec(spec);spec.loader.exec_module(composer)
    raw=(IMAGE/'str8n-2.0bf1-firmware.bin').read_bytes();manifest=read(IMAGE/'firmware-layout.json');assert len(raw)==131072 and sha(IMAGE/manifest['filename'])==manifest['sha256']
    reference=read(ROOT/'tmp/bfx5/build-report.json');expected,ranges=composer.compose(ROOT/'tmp/bfx5/payload',reference);assert raw==expected and ranges==manifest['ranges']
    banks=[raw[n*32768:(n+1)*32768] for n in range(4)];checks=[]
    def check(name,**extra):checks.append(dict(name=name,passed=True,**extra));(out/'progress.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS',name,flush=True)
    check('full 128 KiB image deterministic; 19 pinned components admitted, MON A/B and clean defaults included')
    layout=read(ROOT/'release/beta35/layout.json')
    for segment in layout['segments']:
        start=segment['address']-0x8000;data=(ROOT/'tmp/bfx5/payload'/segment['file']).read_bytes()[segment['offset']:segment['offset']+segment['bytes']]
        assert banks[segment['bank']][start:start+len(data)]==data
    assert banks[3][0x2000:0x3000]==(ROOT/'tmp/bfx5/payload/str8n-v2-recovery-slot-a0.bin').read_bytes()
    assert banks[0]==b'\xff'*32768 and banks[1][:0x3000]==b'\xff'*0x3000
    assert banks[3][0x1c00:0x2000]==b'\xff'*1024 and banks[3][0x4080:0x6000]==b'\xff'*(8192-128)
    check('independent logical map, bank order and erased unowned/identity/history ranges')
    original=composer.SEGMENTS
    try:
        composer.SEGMENTS=original+[original[0]]
        try:composer.compose(ROOT/'tmp/bfx5/payload',reference)
        except AssertionError:pass
        else:raise AssertionError('Overlapping full-image segments accepted')
    finally:composer.SEGMENTS=original
    check('overlapping payload range refused')
    bad=json.loads(json.dumps(reference));bad['artifacts']['clock/storage.bin']['sha256']='0'*64
    try:composer.compose(ROOT/'tmp/bfx5/payload',bad)
    except AssertionError:pass
    else:raise AssertionError('Changed input pin accepted')
    check('altered component pin refused')
    harness.setup()
    from test_v2_status import fresh,boot
    from test_v2_sram_store import console
    try:
        for name,mutate,keys,wanted in [('MON-A-default',None,b'',0xa0),('MON-B-operator-selection',None,b'B\r',0xb0),('MON-A-corrupt-fallback-B',0xa0,b'',0xb0),('MON-B-corrupt-retain-A',0xb0,b'',0xa0),('both-monitors-corrupt-recovery','both',b'',None)]:
            cpu,m=fresh();m.fast=True
            for i,bank in enumerate(banks):m.banks[i][:]=bank
            if mutate is not None:
                for page in ((0xa0,0xb0) if mutate=='both' else (mutate,)):m.banks[3][(page-0x80)*256+128]^=1
            before=(bytes(m.bus.ee),bytes(m.bus.rtc_regs),bytes(m.spi.devices[0].data))
            if keys:
                from test_v2_recovery import B
                injected=[False]
                def choice_hook(c):
                    if c.pc==B['BOOT_RECOVERY_WINDOW'] and not injected[0]:m.rx.extend(keys);injected[0]=True
                    return False
                boot(cpu,hook=choice_hook);assert injected[0]
            else:boot(cpu)
            (out/(name+'-boot.txt')).write_bytes(m.tx)
            if wanted is None:assert b'FIXED F RECOVERY' in m.tx
            else:
                assert m.ram[0x7d30]==wanted and m.ram[0x7d01]==2
                text=console(cpu,m,b'VERSION\r');assert b'2.0bf1' in text and (b'Running: MONITOR A' if wanted==0xa0 else b'Running: MONITOR B') in text
                assert m.ram[0x7ef4]==0xba
                (out/(name+'-version.txt')).write_bytes(text)
            assert before==(bytes(m.bus.ee),bytes(m.bus.rtc_regs),bytes(m.spi.devices[0].data))
            check(name,selected_page=wanted,model_processor='W65C02',retained_devices_unchanged=True)
            if mutate is None:
                transcript=b''
                for command in (b'BATCH MAINT;Q\r',b'BATCH R CLOCK;STATUS;Q\r'):
                    text=console(cpu,m,command,limit=35000000);transcript+=text;assert b'BATCH done' in text and text.endswith(b'B3> '),text[-500:]
                assert b'CLOCK 1.11' in transcript
                assert before==(bytes(m.bus.ee),bytes(m.bus.rtc_regs),bytes(m.spi.devices[0].data))
                (out/(name+'-BATCH.txt')).write_bytes(transcript);check(name+' utility/CLOCK BATCH on complete clean image',retained_devices_unchanged=True)
    except BaseException:
        (out/'failure.json').write_text(json.dumps(dict(passed=False,checks=checks,error=traceback.format_exc()),indent=2)+'\n');raise
    shared=Q/'bf1-2609-hardware-2026-10-17/shared-cpu-acceptance.json';assert read(shared)['passed'] and read(shared)['one_firmware_set']
    result=dict(passed=True,cases=len(checks),checks=checks,image_sha256=sha(IMAGE/'str8n-2.0bf1-firmware.bin'),manifest_sha256=sha(IMAGE/'firmware-layout.json'),composer_sha256=sha(path),test_sha256=sha(Path(__file__)),model_processor='W65C02',shared_CPU_hardware_receipt_sha256=sha(shared),CPU_compatibility='Exact unchanged components previously checked on 65C02 and 65C816 E=1 hardware; new clean-layout CPU execution is W65C02 model only',new_full_image_hardware_installation=False,native_816_execution_tested=False,board_access=False,finished_utc=datetime.now(timezone.utc).isoformat())
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS full-image offline qualification',flush=True)
if __name__=='__main__':main()
