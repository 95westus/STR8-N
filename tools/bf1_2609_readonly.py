"""Preserving 2609 bf1 workload adapters; no settings/persistent setters."""
import re
import run_v2_beta35_soak as old
base=old.base
def guards(link,page):
    assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
    assert link.dump(0x7D27,0x7D28)==b'\x01\0'
    assert link.dump(0x7D30,0x7D30)==bytes([page])
    assert link.dump(0x7EF4,0x7EF4)==b'\xba','bf1 BATCH capability missing'
    assert link.dump(0x66AE,0x66AE)==b'\x01','Retained SRAM protection changed'

def cpu_mode(link,out,name):
    """Observe prior E and ABI state; SEC/XCE only forces E=1 on an 816."""
    probe=old.ROOT/'tmp/bf1cpu2';meta=base.read_json(probe/'report.json')
    assert meta['passed'] and base.sha((probe/'mode.bin').read_bytes())==meta['binary_sha256']
    assert base.load_image(link,probe/'mode.s19')==meta['binary_sha256']
    text=link.command('G 2000');raw=link.dump(0x2440,0x244d)
    (out/(name+'.txt')).write_bytes(text);(out/(name+'.bin')).write_bytes(raw)
    assert raw[0]==0x16 and raw[1]==1,'65C816 runtime was not in emulation mode: '+raw.hex()
    assert raw[2:6]==bytes(4),'DBR/PBR/direct page must be zero: '+raw.hex()
    assert raw[6]&0x0c==4,'Entry requires IRQ disabled and decimal clear'
    assert raw[7:12]==bytes.fromhex('0117040116') and raw[12]&1 and not raw[12]&8 and raw[13]==0xa5,'CPU/public ABI observation mismatch: '+raw.hex()
    return dict(detected_cpu='65C816',emulation_mode_before_probe=True,dbr=raw[2],pbr=raw[3],direct_page=0,entry_irq_disabled=True,entry_decimal_clear=True,native_monitor_calls_advertised=False,probe_enters_native_mode=False,result_hex=raw.hex())
def clock(link,out,expected):
    text=link.command('R CLOCK',b'CLOCK> ');assert b'CLOCK 1.11' in text,text
    try:
        text+=link.command('STATUS',b'CLOCK> ');raw=bytes.fromhex(re.search(rb'RTC registers \(raw\): ([0-9A-F ]+)',text)[1].decode())
        trim=abs(expected['trim_steps'])|(128 if expected['trim_steps']>0 else 0)
        assert raw[7:9]==bytes([expected['control_register'],trim]),'RTC control/trim changed'
        assert b'Running: yes' in text and b'Backup enabled: yes' in text
        for cmd in ('TIME','EUI','TRIM','OFFSET','HELP'):text+=link.command(cmd,b'CLOCK> ')
        (out/'clock.txt').write_bytes(text)
        return dict(rtc_epoch=base.rtc_epoch(raw),trim=expected['trim_steps'],control=raw[7],clock_version='1.11')
    finally:link.command('Q')
def batch(link,out,*,cancel=False):
    text=base.batch(link,'MAINT;Q;SRAM;Q;WORK;Q;EDU;Q')
    text+=base.batch(link,'R CLOCK;STATUS;Q');assert b'CLOCK 1.11' in text
    text+=base.batch(link,'R 1 CLOCK;TIME;Q')
    for launch,prompt in [('SRAM',b'SRAM> '),('R CLOCK',b'CLOCK> ')]:
        error=link.command('BATCH '+launch+';BOGUS;Q',b'BATCH stopped: command failed');error+=link.until(prompt)
        assert not error.endswith(base.PROMPT),'Queued return consumed after error';text+=error;link.command('Q')
    refused=link.command('BATCH ASM;VERSION',b'BATCH stopped: unsupported');refused+=link.until(base.PROMPT);text+=refused
    if cancel:
        text+=link.command('BATCH MAINT;NAME BFXCHECK;Q',b'Type YES: ');link.send(b'\x1b');text+=link.until(b'BATCH canceled')+link.until(b'BM> ');link.command('Q')
    (out/'batch.txt').write_bytes(text)
    return dict(native_handoffs=True,clock_handoff=True,exact_clock_forms=True,error_stops=True,unsupported_asm_refused=True,native_cancel_tested=cancel)
def workload(link,group,out,plan,sram,iteration,expected):
    if group=='clock':return clock(link,out,expected)
    if group=='monitor':
        for cmd in ('VERSION','TIME','APPS','T','M1','W','C','?'):
            text=link.command(cmd);(out/(cmd.replace('?','help')+'.txt')).write_bytes(text)
            if cmd=='VERSION':assert b'2.0bf1' in text and b'Board: 2609' in text,text
        return dict(queries=8)
    if group=='batch':return batch(link,out)
    if group in ('asm','led'):return old.workload(link,group,out,plan,sram,iteration,expected)
    return base.unit(link,group,out,plan,sram,iteration)
