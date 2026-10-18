"""Preserving 2604 bf1 workload adapters; no settings/persistent setters."""
import re
import run_v2_beta35_soak as old
base=old.base
def guards(link,page):
    assert link.dump(0x7D04,0x7D0B)==b'SV\x01\x0f\0\x65\xff\x64'
    assert link.dump(0x7D27,0x7D28)==b'\x01\0'
    assert link.dump(0x7D30,0x7D30)==bytes([page])
    assert link.dump(0x7EF4,0x7EF4)==b'\xba','bf1 BATCH capability missing'
    assert link.dump(0x66AE,0x66AE)==b'\x01','Retained SRAM protection changed'
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
            if cmd=='VERSION':assert b'2.0bf1' in text and b'Board: 2604' in text,text
        return dict(queries=8)
    if group=='batch':return batch(link,out)
    if group in ('asm','led'):return old.workload(link,group,out,plan,sram,iteration,expected)
    return base.unit(link,group,out,plan,sram,iteration)
