"""Check planner, host transports and actual RAM migrator opcodes; no vendor code."""
import hashlib,json,sys,time,uuid
from pathlib import Path
import beta4_migration as migration
import build_v2_beta4_launcher as apps
apps.OUT=apps.ROOT/'BUILD/v2-beta4';apps.configure()
import test_v2_recovery as model
from py65.devices.mpu65c02 import MPU as BaseMPU

ROOT=apps.ROOT;KIT=ROOT/'BUILD/v2-beta4/kit'
REPORT=json.loads((KIT/'migrator.json').read_text());SYM=REPORT['symbols']
PASSED=[]
def done(name):PASSED.append(name);print('PASS '+name,flush=True)
def run(cpu,stop,limit=60000000):
    for _ in range(limit):
        if stop():return
        assert cpu.pc<0x8000,'Migration executed from flash'
        cpu.step()
    raise AssertionError(f'Execution limit at {cpu.pc:04X}; output {bytes(cpu.memory.tx[-180:])!r}')
class Memory(model.Memory):
    def __init__(self,banks):super().__init__(banks);self.id_mode=False;self.id_device=0xb5
    def __getitem__(self,address):
        if self.id_mode and address in (0x8000,0x8001):return 0xbf if address==0x8000 else self.id_device
        return super().__getitem__(address)
    def __setitem__(self,address,value):
        if address==0xd555 and value==0x90 and self.unlock==2:
            self.id_mode=True;self.unlock=0;return
        if self.id_mode and address==0x8000 and value==0xf0:self.id_mode=False;return
        return super().__setitem__(address,value)
    def mutated(self,kind,address,value):
        assert self.bank==3 and address>=0x8000,'Migrator wrote outside B3'
        if kind=='program' and address==0x8003 and value==0x3f:
            assert bytes(self.banks[3][:8192])==migration.maintenance_storage(KIT),'MAINT committed before its entire body matched'
        self.events.append((kind,self.bank,address,value))
class MPU(BaseMPU):
    def step(self):
        if self.pc==0x2001 and self.memory[self.pc]==0xfb:self.pc+=1;return self
        return super().step()
def synthetic_source():
    source=bytearray(b'\xff'*32768)
    for i in range(8):source[i*4096+0x123]=0x30+i
    source[0x7ffc:0x7ffe]=b'\x18\xf8'
    return bytes(source)
def recovery_source():
    old=bytearray(model.Memory().banks[3])
    for offset,generation in ((0x2000,12),(0x3000,11)):
        data=bytearray(old[offset:offset+4096]);data[8:12]=generation.to_bytes(4,'little')
        data[18:20]=migration.crc(data[:18]+data[32:]).to_bytes(2,'little')
        old[offset:offset+4096]=data
    settings=bytearray(migration.default_config());settings[7]=ord('P');settings[8]=0xb0
    settings[9:13]=(11).to_bytes(4,'little');settings[14:]=migration.config_sum(settings)
    old[0x4000:0x4080]=migration.metadata(settings,list(range(32)),7)
    return bytes(old)
def fixture(source,kind='wdc'):
    info,payload,expected=migration.plan(source,KIT,kind)
    temp=ROOT/'BUILD/v2-beta4'/('migration-case-'+uuid.uuid4().hex[:8]);temp.mkdir()
    installer=temp/'installer.s19';installer.write_bytes(payload['installer'])
    cells,entry=migration.read_s19(installer)
    banks=[bytes([0x31+b])*32768 for b in range(3)]+[source]
    memory=Memory(banks)
    for a,v in cells.items():memory.ram[a]=v
    cpu=MPU(memory=memory,pc=entry);memory.cpu=cpu
    return cpu,memory,info,payload,expected
def planner():
    source=synthetic_source();info,payload,expected=migration.plan(source,KIT,'wdc')
    assert info['sectors']==[13,12,10,11,14,8,9,15]
    assert expected[:8192]==migration.maintenance_storage(KIT) and info['config']==migration.default_config().hex()
    assert len(payload['transfers'])==8 and all(len(p)==4096 for p in payload['transfers'])
    assert payload['transfers'][5][3]==0xff and expected[3]==0x3f and info['storage_commit_after']==7
    assert migration.plan(expected,KIT,'str8n')[0]['no_change']
    damaged=bytearray(expected);damaged[0x1100]^=1
    repaired,repair_payload,repair_image=migration.plan(bytes(damaged),KIT,'str8n')
    assert 8 in repaired['sectors'] and 9 in repaired['sectors']
    assert repair_payload['transfers'][repaired['sectors'].index(8)][3]==0xff
    assert repair_image[:8192]==migration.maintenance_storage(KIT)
    # Actual legacy firmware fixtures are STR8-N's own images; never stock code.
    for path,name,offset in (
        (ROOT/'BUILD/v2-alpha24/str8n-v2-alpha24-f000-ffff.bin','2.0a24',0x6ff0),
        (ROOT/'BUILD/v2-a24c1/str8n-v2-a24c1-f000-ffff.bin','2.0a24c1',0x7fd0)):
        if not path.exists():continue
        old=bytearray(b'\xff'*32768);old[0x7000:]=path.read_bytes()
        config=bytearray(migration.default_config());config[2]=2;config[14:]=migration.config_sum(config)
        old[offset:offset+16]=config
        description,migrated,counts,sequence=migration.source_settings(bytes(old),'str8n')
        assert description.startswith(name) and migrated==config and counts==[0]*32 and sequence==0
    # A self-consistent recovery source keeps counters/config while clearing preference.
    old=recovery_source()
    description,config,counts,seq=migration.source_settings(old,'str8n')
    info,payload,expected=migration.plan(old,KIT,'str8n')
    assert description=='recovery format 1' and info['erase_counts_before']==counts
    assert 15 not in info['sectors'] and expected[0x7000:]==old[0x7000:]
    for bad,kind in ((bytes(7),'str8n'),(source,'str8n'),(old,'wdc')):
        try:migration.source_settings(bad,kind)
        except ValueError:pass
        else:raise AssertionError('Unsupported source accepted')
    corrupt=bytearray(old);corrupt[0x7123]^=1
    try:migration.source_settings(bytes(corrupt),'str8n')
    except ValueError:pass
    else:raise AssertionError('Corrupt recovery core accepted')
    done('stock/legacy/recovery source plans, retained configuration/counters and refusals')
def linked_success():
    source=synthetic_source();cpu,mem,info,payload,expected=fixture(source)
    original=[bytes(b) for b in mem.banks[:3]]
    mem.rx.extend(b'Y\r');run(cpu,lambda:cpu.pc==SYM['MIG_RECEIVE'] and not mem.rx)
    for i,data in enumerate(payload['transfers']):
        mem.rx.extend(data)
        if i==len(payload['transfers'])-1:run(cpu,lambda:cpu.pc==SYM['MIG_HALT'])
        else:
            old=mem.ram[SYM['MIG_INDEX']]
            run(cpu,lambda:mem.ram[SYM['MIG_INDEX']]>old and cpu.pc==SYM['MIG_RECEIVE'] and not mem.rx)
        print(f'PASS linked migration sector {info["sectors"][i]:X}',flush=True)
    assert b'MIGRATION VERIFIED' in mem.tx,bytes(mem.tx[-300:])
    assert bytes(mem.banks[3])==expected and [bytes(b) for b in mem.banks[:3]]==original
    erases=[(b,a>>12) for kind,b,a,v in mem.events if kind=='erase']
    assert erases==[(3,p) for p in info['sectors']]
    for choice in (b'A\r',b'B\r'):
        cpu,check=model.boot(banks=mem.banks,keys=choice)
        assert b'STR8-N 2.0b4' in check.tx
        assert b'BANK MAINT 1.5' in model.command(cpu,b'R MAINT\r',limit=20000000)
        assert b'B3>' in model.command(cpu,b'Q\r')
    done('unified RAM entry, all guarded writes, F last, other banks unchanged and beta4 A/B boots')
def pending_maintenance():
    source=bytes(model.Memory().banks[3]);cpu,mem,info,payload,expected=fixture(source,'str8n')
    assert info['sectors']==[12,8,9]
    mem.rx.extend(b'Y\r');run(cpu,lambda:cpu.pc==SYM['MIG_RECEIVE'] and not mem.rx)
    for sector,data in zip(info['sectors'],payload['transfers']):
        if sector==9:
            data=bytearray(data);data[15]^=1;mem.rx.extend(data)
            run(cpu,lambda:cpu.pc==SYM['MIG_HALT']);break
        previous=mem.ram[SYM['MIG_INDEX']];mem.rx.extend(data)
        run(cpu,lambda:mem.ram[SYM['MIG_INDEX']]>previous and cpu.pc==SYM['MIG_RECEIVE'] and not mem.rx)
    assert mem.banks[3][3]==0xff and b'REFUSED/FAILED' in mem.tx
    reboot,check=model.boot(banks=mem.banks)
    assert b'SR error' in model.command(reboot,b'R 3 MAINT\r',limit=16000000)
    done('corrupt MAINT continuation remains pending and cannot be restored after reboot')
def linked_recovery():
    source=recovery_source();cpu,mem,info,payload,expected=fixture(source,'str8n')
    assert len(info['sectors'])<8 and 15 not in info['sectors']
    mem.rx.extend(b'Y\r');run(cpu,lambda:cpu.pc==SYM['MIG_RECEIVE'] and not mem.rx)
    for i,data in enumerate(payload['transfers']):
        mem.rx.extend(data)
        if i==len(payload['transfers'])-1:run(cpu,lambda:cpu.pc==SYM['MIG_HALT'])
        else:
            old=mem.ram[SYM['MIG_INDEX']]
            run(cpu,lambda:mem.ram[SYM['MIG_INDEX']]>old and cpu.pc==SYM['MIG_RECEIVE'] and not mem.rx)
        print(f'PASS linked recovery upgrade sector {info["sectors"][i]:X}',flush=True)
    assert b'MIGRATION VERIFIED' in mem.tx and bytes(mem.banks[3])==expected
    assert mem.banks[3][0x7000:]==source[0x7000:]
    snapshot=migration.journal(expected)
    assert snapshot[8:24].hex()==info['config']
    assert model.counts(snapshot)==info['erase_counts_after']
    done('variable-length recovery upgrade preserves F and retains settings/counts')
def linked_refusals():
    source=synthetic_source()
    for mode in ('cancel','wrong-chip','changed-before','changed-during','bad-payload'):
        cpu,mem,info,payload,expected=fixture(source)
        if mode=='cancel':mem.rx.extend(b'N\r')
        else:
            if mode=='wrong-chip':mem.id_device=0xb6
            if mode=='changed-before':mem.banks[3][0x17]^=1
            mem.rx.extend(b'Y\r')
        if mode in ('changed-during','bad-payload'):
            run(cpu,lambda:cpu.pc==SYM['MIG_RECEIVE'] and not mem.rx)
            data=bytearray(payload['transfers'][0])
            if mode=='changed-during':mem.banks[3][0x17]^=1
            else:data[15]^=1
            mem.rx.extend(data)
        run(cpu,lambda:cpu.pc==SYM['MIG_HALT'])
        assert b'REFUSED/FAILED' in mem.tx and not mem.events,mode
    done('cancel, wrong flash, changed source before/during receive and corrupt payload refuse before erase')
def linked_write_failure():
    cpu,mem,info,payload,expected=fixture(synthetic_source())
    before=[bytes(b) for b in mem.banks]
    mem.rx.extend(b'Y\r');run(cpu,lambda:cpu.pc==SYM['MIG_RECEIVE'] and not mem.rx)
    mem.fault='erase_verify';mem.rx.extend(payload['transfers'][0])
    run(cpu,lambda:cpu.pc==SYM['MIG_HALT'])
    assert b'MIGRATION REFUSED/FAILED; HALTED IN RAM' in mem.tx
    assert any(kind=='erase' for kind,bank,address,value in mem.events)
    assert [bytes(b) for b in mem.banks[:3]]==before[:3]
    assert mem.banks[3][0x7000:]==before[3][0x7000:]
    assert cpu.pc<0x8000
    done('flash erase/verify failure halts in RAM, preserving other banks and the old F sector')
def host_protocol():
    class Fake:
        protocol=migration.Link.protocol
        stock_read=migration.Link.stock_read
        stock_load=migration.Link.stock_load
        def __init__(self):self.writes=[];self.replies=[b'\xcc',b'\0',b'\xcc',b'abc',b'\xcc']
        def send(self,data):self.writes.append(data)
        def exact(self,count):
            data=self.replies.pop(0);assert len(data)==count;return data
    fake=Fake();fake.stock_load({0x2000:97,0x2001:98,0x2002:99},0x2000)
    assert fake.writes==[b'\x55\xaa',b'\x02',b'\0\x20\0\x03\0\0abc',
        b'\x55\xaa',b'\x03',b'\0\x20\0\x03\0\0',b'\x55\xaa',b'\x06',b'\0\x20\0']
    fake=Fake();fake.replies[3]=b'abX'
    try:fake.stock_load({0x2000:97,0x2001:98,0x2002:99},0x2000)
    except IOError:pass
    else:raise AssertionError('RAM mismatch executed')
    assert b'\x06' not in fake.writes
    done('stock serial protocol and RAM readback-before-execute gate')
def host_reset_gate():
    """The stock port must be open when physical RESET is requested."""
    from types import SimpleNamespace
    from unittest.mock import patch
    import serial.tools.list_ports
    events=[];source=synthetic_source()
    target=ROOT/'BUILD/v2-beta4'/('reset-gate-'+uuid.uuid4().hex[:8])
    class Fake:
        def __init__(self,port,log,*,stock=False):
            assert stock and port=='MOCK';events.append('open-stock-port')
            self.pending=bytearray()
            self.serial=SimpleNamespace(reset_input_buffer=lambda:events.append('discard-startup'),
                close=lambda:events.append('close'))
        def protocol(self,command):assert command==12;events.append('board-info')
        def exact(self,count):assert count==12;return b'SXB2'+bytes(8)
        def stock_info_after_reset(self,seconds=60):
            assert events==['open-stock-port']
            events.append('probe-armed');return b'SXB2'+bytes(8)
        def stock_read(self,address,count):
            assert address==0x8000 and count==32768;events.append('read-b3');return source
    def answer(prompt):
        if 'Physical board type' in prompt:return 'W65C02SXB'
        raise AssertionError('RESET must be probed while armed, without an Enter delay')
    with patch.object(migration,'Link',Fake),patch('builtins.input',answer),\
         patch.object(serial.tools.list_ports,'comports',return_value=[]),\
         patch.object(sys,'argv',['migrate','--kind','wdc','--port','MOCK','--kit',str(KIT),
             '--out',str(target),'--backup-only']):
        migration.main()
    assert events==['open-stock-port','probe-armed','read-b3','read-b3','close']
    assert (target/'prior-b3.bin').read_bytes()==source and not (target/'installer.s19').exists()
    done('stock CLI opens the stock-profile port and arms RESET probing before the read-only backup')
def host_armed_probe():
    from types import SimpleNamespace
    from unittest.mock import patch
    class Fake:
        stock_info_after_reset=migration.Link.stock_info_after_reset
        def __init__(self):
            self.pending=bytearray();self.writes=[];self.resets=0
            self.serial=SimpleNamespace(in_waiting=1,reset_input_buffer=self.reset)
            # Startup text, a sync acknowledgement, an incomplete INFO reply,
            # then a new acknowledgement and complete identity.
            self.reads=[b'S',b'\xcc',b'SXB2'+bytes(8)]
        def reset(self):self.resets+=1
        def send(self,data):self.writes.append(data)
        def read(self,count):
            data=self.reads.pop(0)
            return data
    # Check a complete packet following non-debugger startup output.
    fake=Fake();fake.reads=[b'S',b'\xcc',b'SXB2'+bytes(8)]
    assert fake.stock_info_after_reset()==b'SXB2'+bytes(8)
    assert fake.writes==[b'\x55\xaa',b'\x55\xaa',b'\x0c'] and fake.resets==2
    class Retry(Fake):
        def __init__(self):super().__init__();self.now=0;self.syncs=0;self.infos=0;self.phase='';self.short_sent=False
        def send(self,data):
            super().send(data)
            if data==b'\x55\xaa':self.syncs+=1;self.phase='sync'
            elif data==b'\x0c':self.infos+=1;self.phase='info'
            else:raise AssertionError('Probe issued a memory/execute command')
        def read(self,count):
            self.now+=.05
            if self.phase=='sync':return b'S' if self.syncs==1 else b'\xcc'
            if self.infos==1:
                if not self.short_sent:self.short_sent=True;return b'SXB'
                self.now+=1.1;return b''
            return b'SXB2'+bytes(8)
        def sleep(self,seconds):self.now+=seconds
    retry=Retry()
    with patch.object(migration.time,'monotonic',side_effect=lambda:retry.now),\
         patch.object(migration.time,'sleep',side_effect=retry.sleep):
        assert retry.stock_info_after_reset()==b'SXB2'+bytes(8)
    assert retry.writes==[b'\x55\xaa',b'\x55\xaa',b'\x0c',b'\x55\xaa',b'\x0c']
    done('armed startup probing ignores startup text and obtains identity without memory/execute commands')
def main():
    for test in (planner,host_protocol,host_reset_gate,host_armed_probe,linked_success,pending_maintenance,linked_recovery,linked_refusals,linked_write_failure):test()
    (ROOT/'BUILD/v2-beta4/migration-test-results.json').write_text(json.dumps(dict(passed=PASSED,
        vendor_firmware_used=False,physical_migration_tested=False,native_816_tested=False),indent=2)+'\n')
if __name__=='__main__':main()
