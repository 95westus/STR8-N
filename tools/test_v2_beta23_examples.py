"""Execute user examples against frozen beta23, including cleanup failures."""
import os
os.environ.setdefault('STR8_RTC_BUILD','output/qualification/beta23-phase1-2026-10-09/frozen/build')
import hashlib,json
from pathlib import Path
from test_v2_status import fresh,boot,layout,snapshot,META
from test_v2_workspace import install as install_work,call as work_call,req as work_request
from test_v2_sram_store import console

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/beta23-examples'
BUILD=json.loads((OUT/'build.json').read_text())

def run(name,cpu,m,fast=False):
    report=BUILD['examples'][name];body=(OUT/name/(name+'.bin')).read_bytes()
    assert hashlib.sha256(body).hexdigest()==report['sha256']
    m.ram[0x2000:0x2000+len(body)]=body;m.fast=fast
    return console(cpu,m,entry=0x2000,limit=60000000)

def machine(off=False,formatted=True):
    cpu,m=fresh(off=off,primary=layout() if formatted else None,secondary=layout() if formatted else None)
    if formatted:
        # Synthetic empty v2 directory/session/claims, not arbitrary committed
        # bytes from the SPI model's address-pattern retention fixture.
        array=m.spi.devices[0].data;array[0x40:0x240]=b'\xff'*0x200;array[0x280:0x800]=b'\xff'*0x580
    boot(cpu);return cpu,m

def work_machine():
    cpu,m=machine();install_work(cpu,m);m.fast=True
    # Explicit initialization of synthetic test storage only: a layout header
    # alone is insufficient without valid retained session management packets.
    assert work_call(cpu,m,work_request(6,key=b'FORMAT!!'))[0]==0
    m.fast=False;return cpu,m

def main():
    checks=[]
    def passed(name):checks.append(name);print('PASS',name,flush=True)
    cpu,m=machine();before=snapshot(m)
    text=run('read-time',cpu,m)
    assert b'UTC 2026-10-08 19:53:15' in text and m.ram[0x3030]==0
    assert bytes(m.ram[0x3000:0x3008])==(2026).to_bytes(2,'little')+bytes((10,8,4,19,53,15))
    assert snapshot(m)==before
    passed('UTC discovery/read/copy/decimal display; no retained writes')
    cpu,m=machine();pattern=bytes((i*13+7)&255 for i in range(16));m.spi.devices[0].data[0x10000:0x10010]=pattern;before=snapshot(m)
    text=run('read-spisram',cpu,m)
    assert b'SRAM READ: 00' in text and bytes(m.ram[0x3100:0x3110])==pattern
    assert m.ram[0x3008:0x300A]==b'\0\x10' and snapshot(m)==before
    passed('SRAM READ uses real bit-level SPI, high address byte and exact completion; no PROBE/write')
    for name in BUILD['examples']:
        cpu,m=machine(off=True);before=snapshot(m);bus=len(m.bus.accesses);frames=len(m.spi.frames)
        reclaimed=bytes(m.ram[0x6500:0x6700])
        text=run(name,cpu,m)
        assert b'80' in text and snapshot(m)==before and len(m.bus.accesses)==bus and len(m.spi.frames)==frames
        assert bytes(m.ram[0x6500:0x6700])==reclaimed
    passed('all three refuse EDU OFF before optional RAM/device access')
    cpu,m=machine();m.bus.devices.pop(0x6F);before=snapshot(m)
    assert b'TIME error: 02' in run('read-time',cpu,m) and snapshot(m)==before
    passed('absent RTC NACK is reported without SET/ACK')
    cpu,m=machine();before=snapshot(m)
    assert b'WORK: 80' in run('work-area',cpu,m) and snapshot(m)==before
    passed('missing WORK library refuses without a claim or data write')
    cpu,m=machine(formatted=False);install_work(cpu,m);before=snapshot(m)
    assert b'WORK: 40' in run('work-area',cpu,m) and snapshot(m)==before
    passed('unformatted storage is reported; example never formats')
    cpu,m=work_machine()
    array=m.spi.devices[0].data;array[0x10000:0x10040]=bytes((i*17+11)&255 for i in range(64));before=snapshot(m)
    text=run('work-area',cpu,m)
    assert b'WORK: 00 operation=00 restore=00 release=00 claim-may-remain=00' in text,text
    assert m.ram[0x3028]==0 and bytes(m.ram[0x3200:0x3240])==before[3][0x10000:0x10040]
    after=snapshot(m);assert after[:3]==before[:3] and after[3][0x800:]==before[3][0x800:]
    passed('real-SPI WORK claim/write/read/verify/restore/release; all payload bytes and flash/RTC/EEPROM preserved')
    cpu,m=work_machine();before=snapshot(m);failed=[False]
    def one_partial_write(op,address,buffer,count):
        if op==2 and address>=0x10000 and not failed[0]:failed[0]=True;return 3,17
        return 0,count
    m.transfer_fault=one_partial_write
    text=run('work-area',cpu,m,fast=True);after=snapshot(m)
    assert failed[0] and b'WORK: 03 operation=03 restore=00 release=00 claim-may-remain=00' in text
    assert after[:3]==before[:3] and after[3][0x800:]==before[3][0x800:] and m.ram[0x3028]==0
    passed('partial WRITE fault: original bytes restored/verified and handle released, primary error retained')
    cpu,m=work_machine();before=snapshot(m);payload_writes=[0]
    def failed_restore(op,address,buffer,count):
        if op==2 and address>=0x10000:
            payload_writes[0]+=1
            if payload_writes[0]>1:return 3,0
        return 0,count
    m.transfer_fault=failed_restore
    text=run('work-area',cpu,m,fast=True)
    assert b'WORK: 03 operation=00 restore=03 release=00 claim-may-remain=01' in text
    assert m.ram[0x3028]==1 and int.from_bytes(m.ram[0x3026:0x3028],'little')!=0
    assert snapshot(m)[:3]==before[:3]
    passed('failed restoration retains the possible claim/handle and reports cleanup failure')
    cpu,m=work_machine();before=snapshot(m);failed=[False]
    def uncertain_claim(op,address,buffer,count):
        if op==1 and count==1 and 0x300<=address<0x380 and m.spi.devices[0].data[address]==0xA5 and not failed[0]:
            failed[0]=True;return 7,0
        return 0,count
    m.transfer_fault=uncertain_claim
    text=run('work-area',cpu,m,fast=True)
    assert failed[0] and b'WORK: 07 operation=07 restore=00 release=00 claim-may-remain=00' in text,text
    assert m.ram[0x3028]==0 and snapshot(m)[:3]==before[:3] and snapshot(m)[3][0x800:]==before[3][0x800:]
    passed('unconfirmed committed CLAIM: returned handle captured and safely released')
    for name in BUILD['examples']:
        cpu,m=machine();before=snapshot(m);m.ram[0x7E60]=0
        body=(OUT/name/(name+'.bin')).read_bytes();m.ram[0x2000:0x2000+len(body)]=body;cpu.pc=0x2000
        target=BUILD['examples'][name]['symbols']['EX_NO_ABI'];bus=len(m.bus.accesses);frames=len(m.spi.frames)
        for _ in range(2000):
            if cpu.pc==target:break
            cpu.step()
        else:raise AssertionError('Missing RA was not refused')
        assert snapshot(m)==before and len(m.bus.accesses)==bus and len(m.spi.frames)==frames
    passed('unverified RAM ABI halts before calling any service or console entry')
    report=dict(passed=True,checks=checks,firmware_artifacts=META['artifacts'],examples={n:v['sha256'] for n,v in BUILD['examples'].items()},board_access=False,hardware_run=False)
    (OUT/'test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
